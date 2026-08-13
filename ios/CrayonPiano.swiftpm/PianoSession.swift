import AVFoundation
import Combine
import Foundation
import UIKit

@MainActor
final class PianoSession: ObservableObject {
    enum Mode {
        case idle
        case live
        case replay
    }

    @Published var mode: Mode = .idle
    @Published var lit: [LitNote] = []
    @Published var harmonics: Set<Int> = []
    @Published var pressed: Set<Int> = []
    @Published var chroma: [NoteName: Float] = [:]
    @Published var concertA: Double = PitchMath.a4Ref
    @Published var tuneReady = false
    @Published var errorMessage: String?
    @Published var sampleTime: Double = 0
    @Published var sampleDuration: Double = 0
    @Published var scrubbing = false

    /// Symmetric amplitude peaks for the DAW-style waveform track.
    private(set) var wavePeaks: [Float] = []
    let peaksPerSec: Double = 240
    @Published var sceneChoice: SceneStyle = SceneStyle.preferred() {
        didSet { UserDefaults.standard.set(sceneChoice.rawValue, forKey: "crayon-theme") }
    }
    @Published var chordsOn = true
    @Published var unmute = false
    @Published var autotune = true
    @Published var liveTracks: [LiveTrack] = []
    @Published var selectedTrackId: Int?
    @Published var statusLine = "Touche le clavier"
    @Published var hint = ""
    @Published var specDb: [Float] = []
    @Published var specBinHz: Double = 0
    @Published var specClusters: [SpectralCluster] = []

    var scene: SceneStyle { sceneChoice }

    var isTous: Bool { selectedTrackId == nil || liveTracks.isEmpty }

    var trackLabel: String { "\(liveTracks.count)" }

    var tuneLine: String {
        if !autotune {
            return "440"
        }
        if mode == .idle || !tuneReady {
            return "440"
        }
        return String(Int(concertA.rounded()))
    }

    private let engine = AVAudioEngine()
    private let player = AVAudioPlayerNode()
    private let replayMixer = AVAudioMixerNode()
    private let tapMixer = AVAudioMixerNode()
    private let analyzer = SpectrumAnalyzer(fftSize: 4096)
    private var demoBuffer: AVAudioPCMBuffer?
    private var replayStartHost: TimeInterval = 0
    private var replayOffset: Double = 0
    private var clockTimer: Timer?
    private var voices: [Int: Voice] = [:]
    private var didInstallTap = false
    private var nextTrackId = 1
    private var lastLabelAt: Double = 0
    private var labelBusy = false

    private struct Voice {
        let osc: AVAudioSourceNode
    }

    init() {
        engine.attach(player)
        engine.attach(replayMixer)
        engine.attach(tapMixer)
        let format = AVAudioFormat(standardFormatWithSampleRate: 44100, channels: 1)!
        engine.connect(player, to: replayMixer, format: format)
        engine.connect(replayMixer, to: tapMixer, format: format)
        engine.connect(tapMixer, to: engine.mainMixerNode, format: format)
        replayMixer.outputVolume = 0
        tapMixer.outputVolume = 1
        demoBuffer = Self.makeDemoBuffer(format: format)
        sampleDuration = Double(demoBuffer?.frameLength ?? 0) / 44100
        wavePeaks = Self.computePeaks(demoBuffer, peaksPerSec: peaksPerSec)
    }

    /// Live playback position, valid while playing, scrubbing, or paused.
    func currentSampleTime() -> Double {
        if scrubbing { return sampleTime }
        if mode == .replay {
            return min(sampleDuration, replayOffset + (ProcessInfo.processInfo.systemUptime - replayStartHost))
        }
        return sampleTime
    }

    func beginScrub() {
        scrubbing = true
    }

    func scrub(toTime t: Double) {
        let clamped = max(0, min(sampleDuration, t))
        replayOffset = clamped
        sampleTime = clamped
    }

    func endScrub() {
        scrubbing = false
        if mode == .replay { startReplay() }
    }

    func toggleListen() {
        switch mode {
        case .live:
            stopLive()
        case .idle, .replay:
            startLive()
        }
    }

    func toggleReplay() {
        switch mode {
        case .replay:
            stopReplay(keepScrub: true)
        case .idle, .live:
            startReplay()
        }
    }

    func startLive() {
        errorMessage = nil
        if mode == .replay { stopReplay(keepScrub: true) }
        do {
            try configureSession()
            try startEngineIfNeeded()
            tapMixer.removeTap(onBus: 0)
            installInputTap()
            analyzer.reset()
            mode = .live
            statusLine = "live"
            hint = ""
        } catch {
            mode = .idle
            errorMessage = micError(error)
        }
    }

    func stopLive() {
        engine.inputNode.removeTap(onBus: 0)
        didInstallTap = false
        mode = .idle
        clearSpectrum()
        statusLine = ""
        hint = ""
    }

    func startReplay() {
        errorMessage = nil
        if mode == .live { stopLive() }
        do {
            try configureSession()
            try startEngineIfNeeded()
            guard let demoBuffer else { return }
            analyzer.reset()
            replayMixer.outputVolume = unmute ? 0.28 : 0
            if replayOffset >= sampleDuration - 0.05 { replayOffset = 0 }
            player.stop()
            if let sliced = Self.slice(demoBuffer, from: replayOffset) {
                player.scheduleBuffer(sliced, at: nil, options: []) { [weak self] in
                    Task { @MainActor in
                        guard let self, self.mode == .replay else { return }
                        self.replayOffset = self.sampleDuration
                        self.stopReplay(keepScrub: true)
                    }
                }
            }
            player.play()
            replayStartHost = ProcessInfo.processInfo.systemUptime
            mode = .replay
            statusLine = "démo"
            hint = ""
            startClock()
            installMixerTap()
        } catch {
            mode = .idle
            errorMessage = error.localizedDescription
        }
    }

    func stopReplay(keepScrub: Bool) {
        if mode == .replay {
            replayOffset = keepScrub ? sampleNow() : 0
        }
        player.stop()
        clockTimer?.invalidate()
        clockTimer = nil
        tapMixer.removeTap(onBus: 0)
        if mode == .replay { mode = .idle }
        if mode == .idle {
            clearSpectrum()
            statusLine = ""
            hint = ""
            if !keepScrub { sampleTime = 0 }
        }
    }

    func seekReplay(fraction: Double) {
        replayOffset = sampleDuration * min(1, max(0, fraction))
        sampleTime = replayOffset
        if mode == .replay {
            startReplay()
        }
    }

    func applyUnmute() {
        replayMixer.outputVolume = (mode == .replay && unmute) ? 0.28 : 0
    }

    func selectAllTracks() {
        selectedTrackId = nil
        analyzer.reset()
    }

    func toggleTrack(_ id: Int) {
        selectedTrackId = selectedTrackId == id ? nil : id
        analyzer.reset()
    }

    func noteOn(_ midi: Int) {
        pressed.insert(midi)
        ensureTone(midi)
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        let name = NoteName.pitchClass(of: midi)
        statusLine = "\(name.french)\(PitchMath.octave(of: midi))"
    }

    func noteOff(_ midi: Int) {
        pressed.remove(midi)
        fadeOut(midi)
    }

    func setPressed(_ midis: Set<Int>) {
        let added = midis.subtracting(pressed)
        let removed = pressed.subtracting(midis)
        for m in added { noteOn(m) }
        for m in removed { noteOff(m) }
    }

    private func ensureTone(_ midi: Int) {
        if voices[midi] != nil { return }
        do { try startEngineIfNeeded() } catch { return }
        let freq = PitchMath.midiToHz(midi, concertA: autotune ? concertA : PitchMath.a4Ref)
        let phasor = TonePhasor()
        let twoPi = 2.0 * Double.pi
        let src = AVAudioSourceNode { _, _, frameCount, audioBufferList -> OSStatus in
            let abl = UnsafeMutableAudioBufferListPointer(audioBufferList)
            let sr = 44100.0
            for frame in 0..<Int(frameCount) {
                let sample = 0.18 * sin(phasor.phase) + 0.07 * sin(phasor.phase2)
                phasor.phase += twoPi * freq / sr
                phasor.phase2 += twoPi * freq * 2 / sr
                if phasor.phase > twoPi { phasor.phase -= twoPi }
                if phasor.phase2 > twoPi { phasor.phase2 -= twoPi }
                for buf in abl {
                    let ptr = buf.mData?.assumingMemoryBound(to: Float.self)
                    ptr?[frame] = Float(sample)
                }
            }
            return noErr
        }
        engine.attach(src)
        let format = AVAudioFormat(standardFormatWithSampleRate: 44100, channels: 1)
        engine.connect(src, to: engine.mainMixerNode, format: format)
        voices[midi] = Voice(osc: src)
    }

    private func fadeOut(_ midi: Int) {
        guard let voice = voices.removeValue(forKey: midi) else { return }
        engine.detach(voice.osc)
    }

    private func configureSession() throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .measurement, options: [.defaultToSpeaker, .allowBluetoothHFP, .mixWithOthers])
        try session.setActive(true)
    }

    private func startEngineIfNeeded() throws {
        if !engine.isRunning {
            try configureSession()
            try engine.start()
        }
    }

    private func installInputTap() {
        let input = engine.inputNode
        input.removeTap(onBus: 0)
        let format = input.outputFormat(forBus: 0)
        input.installTap(onBus: 0, bufferSize: 2048, format: format) { [weak self] buffer, _ in
            self?.consume(buffer, sampleRate: format.sampleRate)
        }
        didInstallTap = true
    }

    private func installMixerTap() {
        tapMixer.removeTap(onBus: 0)
        let format = AVAudioFormat(standardFormatWithSampleRate: 44100, channels: 1)
        tapMixer.installTap(onBus: 0, bufferSize: 2048, format: format) { [weak self] buffer, _ in
            self?.consume(buffer, sampleRate: 44100)
        }
    }

    nonisolated private func consume(_ buffer: AVAudioPCMBuffer, sampleRate: Double) {
        guard let channel = buffer.floatChannelData?[0] else { return }
        let frames = Int(buffer.frameLength)
        let samples = Array(UnsafeBufferPointer(start: channel, count: frames))
        let now = ProcessInfo.processInfo.systemUptime
        Task { @MainActor [weak self] in
            self?.process(samples: samples, sampleRate: sampleRate, now: now)
        }
    }

    private func process(samples: [Float], sampleRate: Double, now: Double) {
        guard mode == .live || mode == .replay else { return }
        let tous = isTous
        var bands: [(lo: Double, hi: Double)] = [(PitchMath.mixedLoHz, PitchMath.mixedHiHz)]
        if !tous, let id = selectedTrackId, let t = liveTracks.first(where: { $0.id == id }) {
            bands = (1...8).map { n in
                let f = t.f0 * Double(n)
                return (f * 0.97, f * 1.03)
            }
        }
        let config = PeakPickConfig(
            sensitivity: 0.58,
            chords: chordsOn,
            concertA: autotune ? analyzer.concertA : PitchMath.a4Ref,
            autotune: autotune,
            bands: bands,
            foldOctaves: !tous
        )
        let result = analyzer.analyze(samples: samples, sampleRate: sampleRate, now: now, config: config)
        let clustered = DensityCluster.cluster(peaks: result.mixPeaks)
        syncClusters(clustered, now: now)
        specDb = analyzer.lastDb
        specBinHz = analyzer.lastBinHz
        specClusters = clustered
        lit = result.lit
        harmonics = result.harmonics
        chroma = result.chroma
        concertA = autotune ? analyzer.concertA : PitchMath.a4Ref
        tuneReady = analyzer.tuneReady
        if let top = result.lit.first {
            statusLine = "\(top.name.french)\(PitchMath.octave(of: top.midi))"
        }
        maybeLabel(now: now)
    }

    private func syncClusters(_ clusters: [SpectralCluster], now: Double) {
        var used = Set<Int>()
        for c in clusters {
            var best: Int?
            var bestCost = 0.45
            for (idx, t) in liveTracks.enumerated() {
                if used.contains(t.id) { continue }
                let lf = abs(log2(c.f0 / t.f0))
                if lf < bestCost {
                    bestCost = lf
                    best = idx
                }
            }
            if let idx = best {
                used.insert(liveTracks[idx].id)
                liveTracks[idx].f0 = liveTracks[idx].f0 * 0.55 + c.f0 * 0.45
                liveTracks[idx].db = c.db
                liveTracks[idx].harm = c.harm
                liveTracks[idx].energy = min(1, Double((c.db + 80) / 50))
                liveTracks[idx].lastSeen = now
            } else {
                let t = LiveTrack(
                    id: nextTrackId,
                    f0: c.f0,
                    db: c.db,
                    harm: c.harm,
                    energy: min(1, Double((c.db + 80) / 50)),
                    born: now,
                    lastSeen: now
                )
                nextTrackId += 1
                liveTracks.append(t)
                used.insert(t.id)
            }
        }
        for i in liveTracks.indices where !used.contains(liveTracks[i].id) {
            liveTracks[i].energy *= 0.72
        }
        liveTracks.removeAll { now - $0.lastSeen > 1.4 || $0.energy < 0.04 }
        if let id = selectedTrackId, !liveTracks.contains(where: { $0.id == id }) {
            selectedTrackId = nil
        }
    }

    private func maybeLabel(now: Double) {
        guard !labelBusy, !liveTracks.isEmpty, now - lastLabelAt > 1.6 else { return }
        lastLabelAt = now
        labelBusy = true
        let snapshot = liveTracks
        Task { @MainActor in
            let rows = await ClusterLabeler.label(snapshot)
            for row in rows {
                if let i = liveTracks.firstIndex(where: { $0.id == row.id }) {
                    if row.source == "fm" || liveTracks[i].label.isEmpty {
                        liveTracks[i].label = row.name
                        liveTracks[i].labelSource = row.source
                    }
                }
            }
            for i in liveTracks.indices where liveTracks[i].label.isEmpty {
                let h = ClusterLabeler.heuristic(liveTracks[i])
                if !h.isEmpty {
                    liveTracks[i].label = h
                    liveTracks[i].labelSource = "heuristic"
                }
            }
            labelBusy = false
        }
    }

    private func clearSpectrum() {
        lit = []
        harmonics = []
        chroma = [:]
        tuneReady = false
        concertA = PitchMath.a4Ref
        liveTracks = []
        selectedTrackId = nil
        specDb = []
        specBinHz = 0
        specClusters = []
        analyzer.reset()
    }

    private func startClock() {
        clockTimer?.invalidate()
        clockTimer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self, self.mode == .replay else { return }
                self.sampleTime = self.sampleNow()
            }
        }
    }

    private func sampleNow() -> Double {
        min(sampleDuration, replayOffset + (ProcessInfo.processInfo.systemUptime - replayStartHost))
    }

    private func micError(_ error: Error) -> String {
        "Autorise le micro dans Réglages."
    }

    private static func makeDemoBuffer(format: AVAudioFormat) -> AVAudioPCMBuffer? {
        let sr = format.sampleRate
        let dur = 8.0
        let n = AVAudioFrameCount(sr * dur)
        guard let buf = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: n) else { return nil }
        buf.frameLength = n
        guard let data = buf.floatChannelData?[0] else { return nil }
        for i in 0..<Int(n) { data[i] = 0 }

        func addTone(_ freq: Double, start: Double, length: Double, amp: Float) {
            let i0 = Int(start * sr)
            let i1 = min(Int(n), Int((start + length) * sr))
            guard i1 > i0 else { return }
            for i in i0..<i1 {
                let t = Double(i) / sr - start
                let env = Float(min(1, t / 0.05) * exp(-t / (length * 0.8)))
                var s: Float = 0
                s += 1.0 * sinf(Float(2 * Double.pi * freq * t))
                s += 0.5 * sinf(Float(2 * Double.pi * freq * 2 * t))
                s += 0.25 * sinf(Float(2 * Double.pi * freq * 3 * t))
                data[i] += amp * env * s
            }
        }

        addTone(65.41, start: 0, length: 8, amp: 0.35)
        addTone(196.00, start: 0.5, length: 3, amp: 0.25)
        addTone(261.63, start: 3.5, length: 3, amp: 0.25)
        let chords: [(Double, [Double])] = [
            (0.5, [329.63, 415.30, 493.88]),
            (2.5, [349.23, 440.00, 523.25]),
            (4.5, [392.00, 493.88, 587.33]),
            (6.5, [329.63, 415.30, 493.88])
        ]
        for (start, freqs) in chords {
            for f in freqs { addTone(f, start: start, length: 1.8, amp: 0.18) }
        }
        addTone(1046.50, start: 1.0, length: 0.3, amp: 0.08)
        addTone(1318.51, start: 5.0, length: 0.3, amp: 0.08)

        var peak: Float = 0.0001
        for i in 0..<Int(n) { peak = max(peak, abs(data[i])) }
        let g = 0.9 / peak
        for i in 0..<Int(n) { data[i] *= g }
        return buf
    }

    private static func computePeaks(_ buffer: AVAudioPCMBuffer?, peaksPerSec: Double) -> [Float] {
        guard let buffer, let data = buffer.floatChannelData?[0] else { return [] }
        let n = Int(buffer.frameLength)
        let sr = buffer.format.sampleRate
        guard n > 0, sr > 0 else { return [] }
        let buckets = max(1, Int(ceil(Double(n) / sr * peaksPerSec)))
        let per = Double(n) / Double(buckets)
        var peaks = [Float](repeating: 0, count: buckets)
        var mx: Float = 0.0001
        for b in 0..<buckets {
            let s = Int(Double(b) * per)
            let e = min(n, Int(Double(b + 1) * per))
            var m: Float = 0
            var i = s
            while i < e {
                let v = abs(data[i])
                if v > m { m = v }
                i += 1
            }
            peaks[b] = m
            if m > mx { mx = m }
        }
        let norm = 0.94 / mx
        for i in 0..<buckets { peaks[i] *= norm }
        return peaks
    }

    private static func slice(_ buffer: AVAudioPCMBuffer, from offset: Double) -> AVAudioPCMBuffer? {
        let sr = buffer.format.sampleRate
        let start = min(Int(buffer.frameLength), max(0, Int(offset * sr)))
        let remaining = Int(buffer.frameLength) - start
        guard remaining > 0 else { return nil }
        guard let out = AVAudioPCMBuffer(pcmFormat: buffer.format, frameCapacity: AVAudioFrameCount(remaining)) else {
            return nil
        }
        out.frameLength = AVAudioFrameCount(remaining)
        if let src = buffer.floatChannelData?[0], let dst = out.floatChannelData?[0] {
            dst.update(from: src.advanced(by: start), count: remaining)
        }
        return out
    }
}

private final class TonePhasor: @unchecked Sendable {
    var phase: Double = 0
    var phase2: Double = 0
}

