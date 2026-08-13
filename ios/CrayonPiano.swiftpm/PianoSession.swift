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
    @Published var isStealth = true
    @Published var sensitivity: Double = 0.58
    @Published var chordsOn = true
    @Published var unmute = false
    @Published var autotune = true
    @Published var selectedTracks: Set<String> = Set(MusicianTrack.all.map(\.id))
    @Published var statusLine = "Touche le clavier · Tap keys"
    @Published var hint = "Aucun port · No server · Tap, listen, or replay the built-in demo"

    var scene: SceneStyle { isStealth ? .stealth : .studio }

    var isTous: Bool { selectedTracks.count == MusicianTrack.all.count }

    var activeTracks: [MusicianTrack] {
        MusicianTrack.all.filter { selectedTracks.contains($0.id) }
    }

    var trackLabel: String {
        if isTous { return "Pistes / Tracks: Tous / All" }
        return "Pistes / Tracks: " + activeTracks.map(\.french).joined(separator: " + ")
    }

    var tuneLine: String {
        let cents = 1200 * log2(concertA / PitchMath.a4Ref)
        if !autotune {
            return String(format: "La / A = 440 Hz (verrouillé / locked) · estimé %.0f Hz", concertA)
        }
        if mode == .idle {
            return "La / A ≈ 440 Hz · Auto-accord en attente / waiting"
        }
        if !tuneReady {
            return "La / A ≈ 440 Hz · écoute le La… / listening for A…"
        }
        let rounded = Int(cents.rounded())
        let sign = rounded > 0 ? "+" : ""
        let phrase: String
        let a = abs(cents)
        if a < 4 {
            phrase = "pile / in tune"
        } else if cents > 0 {
            phrase = a < 15 ? "un peu trop haut / a bit sharp" : "trop haut / sharp"
        } else {
            phrase = a < 15 ? "un peu trop bas / a bit flat" : "trop bas / flat"
        }
        return String(format: "La / A ≈ %.0f Hz · %@%d cents · %@", concertA, sign, rounded, phrase)
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
            statusLine = "Micro / Mic — live"
            hint = "Le piano suit le micro · Follows the device input"
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
        statusLine = "Touche le clavier · Tap keys"
        hint = "Aucun port · No server · Tap, listen, or replay the built-in demo"
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
            statusLine = "Démo intégrée / Built-in demo (pas de serveur / no server)"
            hint = "Même FFT que le micro · Same peak-picker as live"
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
            statusLine = "Démo intégrée / Built-in demo — stop"
            hint = "Aucun port · No server · Tap, listen, or replay the built-in demo"
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
        selectedTracks = Set(MusicianTrack.all.map(\.id))
        analyzer.reset()
    }

    func toggleTrack(_ id: String) {
        if isTous {
            selectedTracks = [id]
        } else if selectedTracks.contains(id) {
            selectedTracks.remove(id)
            if selectedTracks.isEmpty {
                selectedTracks = Set(MusicianTrack.all.map(\.id))
            }
        } else {
            selectedTracks.insert(id)
        }
        analyzer.reset()
    }

    func noteOn(_ midi: Int) {
        pressed.insert(midi)
        ensureTone(midi)
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        let name = NoteName.pitchClass(of: midi)
        statusLine = "\(name.french)\(PitchMath.octave(of: midi)) · \(name.pencil) · ~\(Int(PitchMath.midiToHz(midi, concertA: concertA).rounded())) Hz"
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
        let bands: [(lo: Double, hi: Double)] = tous
            ? [(PitchMath.mixedLoHz, PitchMath.mixedHiHz)]
            : activeTracks.map { ($0.loHz, $0.hiHz) }
        let config = PeakPickConfig(
            sensitivity: sensitivity,
            chords: chordsOn,
            concertA: autotune ? analyzer.concertA : PitchMath.a4Ref,
            autotune: autotune,
            bands: bands,
            foldOctaves: !tous
        )
        let result = analyzer.analyze(samples: samples, sampleRate: sampleRate, now: now, config: config)
        lit = result.lit
        harmonics = result.harmonics
        chroma = result.chroma
        concertA = autotune ? analyzer.concertA : PitchMath.a4Ref
        tuneReady = analyzer.tuneReady
        if let top = result.lit.first {
            statusLine = "\(top.name.pencil) · \(Int(top.freq.rounded())) Hz"
        }
    }

    private func clearSpectrum() {
        lit = []
        harmonics = []
        chroma = [:]
        tuneReady = false
        concertA = PitchMath.a4Ref
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
        "Autorise le micro dans Réglages → Piano-crayon. / Allow the mic in Settings. (\(error.localizedDescription))"
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

