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
    @Published var boundPressed: Set<Int> = []
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
        didSet {
            UserDefaults.standard.set(sceneChoice.rawValue, forKey: "crayon-theme")
            if !sceneAuto {
                UserDefaults.standard.set(sceneChoice.rawValue, forKey: "crayon-theme-manual")
            }
        }
    }
    @Published var chordsOn = true
    @Published var unmute = false
    @Published var autotune = true
    @Published var liveTracks: [LiveTrack] = []
    @Published var selectedTrackIds: Set<Int> = []
    @Published var typedText = ""
    @Published var fingerCaption = "0 touche · 0 groupe"
    @Published var kbLayout: String = DualBoards.normalize(
        UserDefaults.standard.string(forKey: "crayon-kb-layout")
    ) {
        didSet {
            let next = DualBoards.normalize(kbLayout)
            if next != kbLayout {
                kbLayout = next
                return
            }
            if oldValue != kbLayout {
                UserDefaults.standard.set(kbLayout, forKey: "crayon-kb-layout")
                releaseDualHolds()
            }
        }
    }
    let fingerGate = FingerGate()
    let typeState = DualTypeState()
    private var trackEnergyHist: [Int: [Float]] = [:]
    let histLen = 240
    @Published var statusLine = "Touche le clavier"
    @Published var hint = ""
    @Published var scoreValue = 0
    @Published var bestScore = 0
    @Published var layoutId: KeyboardLayoutId = KeyboardLayout.detect()
    let scoreKeeper = ScoreKeeper()
    let scoreStore = ScoreStore()
    @Published var sceneAuto = UserDefaults.standard.object(forKey: "crayon-theme-auto") as? Bool ?? true {
        didSet { UserDefaults.standard.set(sceneAuto, forKey: "crayon-theme-auto") }
    }
    let specBus = SpectrumBus()

    var scene: SceneStyle { sceneChoice }

    var isTous: Bool { selectedTrackIds.isEmpty || liveTracks.isEmpty }

    var trackLabel: String { "\(liveTracks.count)" }

    var waveStackHeight: CGFloat {
        min(280, CGFloat(max(1, liveTracks.count)) * 36)
    }

    func trackIsOn(_ id: Int) -> Bool { isTous || selectedTrackIds.contains(id) }

    func energyHist(for id: Int) -> [Float] { trackEnergyHist[id] ?? [] }

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
    private let displayPulse = DisplayPulse()
    private var mixerTapOn = false
    private var histClock: TimeInterval = 0
    private let waveWindowSec: Double = 6
    private var voices: [Int: Voice] = [:]
    private var didInstallTap = false
    private var nextTrackId = 1
    private var lastLabelAt: Double = 0
    private var labelBusy = false
    private var voiceOrder: [Int] = []
    private var lastAutoSceneAt: TimeInterval = 0
    private var lastAutoStyle: SceneStyle?
    private var brightnessObserver: NSObjectProtocol?
    private var lastClusters: [SpectralCluster] = []
    private var lastPeaks: [SpecPeak] = []

    private struct Voice {
        let osc: AVAudioSourceNode
        let phasor: TonePhasor
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
        brightnessObserver = NotificationCenter.default.addObserver(
            forName: UIScreen.brightnessDidChangeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.considerAmbient() }
        }
        considerAmbient()
        displayPulse.onTick = { [weak self] in
            Task { @MainActor in
                self?.onDisplayTick()
            }
        }
    }

    func pickScene(_ style: SceneStyle) {
        sceneAuto = false
        sceneChoice = style
    }

    func enableSceneAuto() {
        sceneAuto = true
        lastAutoSceneAt = 0
        considerAmbient()
    }

    func considerAmbient() {
        guard sceneAuto else { return }
        let now = ProcessInfo.processInfo.systemUptime
        let next = SceneStyle.fromAmbient(
            brightness: UIScreen.main.brightness,
            interface: UITraitCollection.current.userInterfaceStyle
        )
        if next == sceneChoice {
            lastAutoStyle = next
            return
        }
        if lastAutoStyle == next, now - lastAutoSceneAt < 8 { return }
        if now - lastAutoSceneAt < 12, lastAutoStyle != nil { return }
        lastAutoSceneAt = now
        lastAutoStyle = next
        sceneChoice = next
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
        armDisplayPulse()
    }

    func scrub(toTime t: Double) {
        let clamped = max(0, min(sampleDuration, t))
        replayOffset = clamped
        sampleTime = clamped
    }

    func endScrub() {
        scrubbing = false
        if mode == .replay { startReplay() }
        armDisplayPulse()
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
            mixerTapOn = false
            installInputTap()
            analyzer.reset()
            mode = .live
            statusLine = "live"
            hint = ""
            armDisplayPulse()
        } catch {
            mode = .idle
            errorMessage = micError(error)
        }
    }

    func persistScore(source: String) {
        if scoreKeeper.score > 0 {
            scoreStore.record(source: source, score: scoreKeeper.score)
        }
        bestScore = scoreStore.best(for: source)
        scoreKeeper.resetSession()
        scoreValue = 0
    }

    func handleHardwareCharacters(_ chars: String, down: Bool) {
        if let guessed = KeyboardLayout.infer(code: "", key: chars) {
            layoutId = guessed
        }
        guard let midi = KeyboardLayout.midi(forCharacters: chars) else { return }
        if down { noteOn(midi) } else { noteOff(midi) }
    }

    func stopLive() {
        persistScore(source: "live")
        engine.inputNode.removeTap(onBus: 0)
        didInstallTap = false
        mode = .idle
        clearSpectrum()
        statusLine = ""
        hint = ""
        if !voices.isEmpty { ensureMixerTap() }
        armDisplayPulse()
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
            installMixerTap()
            armDisplayPulse()
        } catch {
            mode = .idle
            errorMessage = error.localizedDescription
        }
    }

    func stopReplay(keepScrub: Bool) {
        persistScore(source: "demo")
        if mode == .replay {
            replayOffset = keepScrub ? sampleNow() : 0
        }
        player.stop()
        tapMixer.removeTap(onBus: 0)
        mixerTapOn = false
        if mode == .replay { mode = .idle }
        if mode == .idle {
            clearSpectrum()
            statusLine = ""
            hint = ""
            if !keepScrub { sampleTime = 0 }
        }
        if !voices.isEmpty { ensureMixerTap() }
        armDisplayPulse()
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
        selectedTrackIds = []
        analyzer.reset()
    }

    func toggleTrack(_ id: Int) {
        if isTous {
            selectedTrackIds = [id]
        } else if selectedTrackIds.contains(id) {
            selectedTrackIds.remove(id)
        } else {
            selectedTrackIds.insert(id)
        }
        analyzer.reset()
    }

    var layoutHint: String {
        kbLayout == "csa"
            ? "Canadien français · Z=Do3 · D=Do4 · Q=La4"
            : "US · Z=Do3 · D=Do4 · Q=La4"
    }

    func clearTyped() {
        typeState.text = ""
        typeState.dead = ""
        typedText = ""
    }

    func releaseDualHolds() {
        for held in fingerGate.held {
            if let spec = DualBoards.layout(held.board).key(held.kid) {
                typeState.release(spec)
            }
        }
        fingerGate.clear()
        fingerCaption = Self.caption(for: fingerGate)
        publishSpatialTracks()
        syncBoundNotes()
    }

    @discardableResult
    func hardwareDown(code: String?) -> Bool {
        guard let code, let spec = DualBoards.layout(kbLayout).key(code: code) else { return false }
        dualDown(pointer: DualHID.pointer(for: code), board: kbLayout, kid: spec.kid)
        return true
    }

    @discardableResult
    func hardwareUp(code: String?) -> Bool {
        guard let code else { return false }
        dualUp(pointer: DualHID.pointer(for: code))
        return DualBoards.layout(kbLayout).key(code: code) != nil
    }

    func dualDown(pointer: Int, board: String, kid: String) {
        let key = HeldDual(board: board, kid: kid)
        if fingerGate.at(pointer) == key { return }
        if fingerGate.at(pointer) != nil { return }
        let already = fingerGate.held.contains(key)
        guard fingerGate.down(pointer: pointer, key: key) else { return }
        if !already, let spec = DualBoards.layout(board).key(kid) {
            _ = typeState.apply(spec)
            typedText = typeState.text
        }
        fingerCaption = Self.caption(for: fingerGate)
        publishSpatialTracks()
        syncBoundNotes()
        armDisplayPulse()
    }

    func dualUp(pointer: Int) {
        if let held = fingerGate.at(pointer), let spec = DualBoards.layout(held.board).key(held.kid) {
            typeState.release(spec)
        }
        fingerGate.up(pointer: pointer)
        fingerCaption = Self.caption(for: fingerGate)
        publishSpatialTracks()
        syncBoundNotes()
        armDisplayPulse()
    }

    private static func caption(for gate: FingerGate) -> String {
        let n = gate.held.count
        let g = gate.clusters.count
        let nt = n <= 1 ? "\(n) touche" : "\(n) touches"
        let ng = g <= 1 ? "\(g) groupe" : "\(g) groupes"
        return "\(nt) · \(ng)"
    }

    private func publishSpatialTracks() {
        guard mode == .idle else { return }
        let now = ProcessInfo.processInfo.systemUptime
        let groups = fingerGate.clusters
        var next: [LiveTrack] = []
        for members in groups {
            let pts = members.map { DualBoards.point($0) }
            let cx = pts.map(\.0).reduce(0, +) / Double(max(1, pts.count))
            let glyphs = members.compactMap { DualBoards.layout($0.board).key($0.kid)?.base }.joined()
            let midis = members.compactMap { DualNoteMap.midi(for: $0.kid) }
            let midi0 = midis.min()
            let concert = autotune ? concertA : PitchMath.a4Ref
            let f0 = midi0.map { PitchMath.midiToHz($0, concertA: concert) }
                ?? (110 * pow(2, (cx.truncatingRemainder(dividingBy: 12)) / 12))
            let label = midi0.map { DualNoteMap.labelFr($0) + " · " + glyphs } ?? glyphs
            var t = LiveTrack(
                id: nextTrackId,
                f0: f0,
                db: -12,
                harm: 0.4,
                energy: 1,
                born: now,
                lastSeen: now,
                label: label,
                labelSource: "keys"
            )
            if let existing = liveTracks.first(where: { abs(($0.f0) - t.f0) < 8 }) {
                t.id = existing.id
                t.born = existing.born
            } else {
                nextTrackId += 1
            }
            next.append(t)
        }
        liveTracks = next
        selectedTrackIds = selectedTrackIds.filter { id in liveTracks.contains { $0.id == id } }
        pushHist()
    }

    private func pushHist() {
        for t in liveTracks {
            if trackEnergyHist[t.id]?.count != histLen {
                trackEnergyHist[t.id] = Array(repeating: 0, count: histLen)
            }
        }
        let ids = Set(liveTracks.map(\.id))
        trackEnergyHist = trackEnergyHist.filter { ids.contains($0.key) }
    }

    func noteOn(_ midi: Int) {
        pressed.insert(midi)
        scoreKeeper.press(midi)
        scoreValue = scoreKeeper.score
        syncSounding()
    }

    func noteOff(_ midi: Int) {
        pressed.remove(midi)
        syncSounding()
    }

    func setPressed(_ midis: Set<Int>) {
        pressed = midis
        syncSounding()
    }

    func syncBoundNotes() {
        boundPressed = Set(fingerGate.held.compactMap { DualNoteMap.midi(for: $0.kid) })
        syncSounding()
    }

    var keyBinds: [Int: String] {
        var out: [Int: String] = [:]
        for midi in PitchMath.midiLo...PitchMath.midiHi {
            if let glyph = DualNoteMap.glyph(midi: midi, layoutId: kbLayout) {
                out[midi] = glyph
            }
        }
        return out
    }

    private func syncSounding() {
        let want = pressed.union(boundPressed)
        let have = Set(voices.keys)
        for midi in want.subtracting(have) {
            if voices.count >= 96, let oldest = voiceOrder.first {
                fadeOut(oldest)
            }
            ensureTone(midi)
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            let name = NoteName.pitchClass(of: midi)
            statusLine = "\(name.french)\(PitchMath.octave(of: midi))"
        }
        for midi in have.subtracting(want) {
            fadeOut(midi)
        }
        publishHeld()
        armDisplayPulse()
    }

    private func ensureTone(_ midi: Int) {
        if let existing = voices[midi] {
            existing.phasor.releasing = false
            existing.phasor.target = 1
            return
        }
        do { try startEngineIfNeeded() } catch { return }
        ensureMixerTap()
        let freq = PitchMath.midiToHz(midi, concertA: autotune ? concertA : PitchMath.a4Ref)
        let phasor = TonePhasor()
        let twoPi = 2.0 * Double.pi
        let src = AVAudioSourceNode { _, _, frameCount, audioBufferList -> OSStatus in
            let abl = UnsafeMutableAudioBufferListPointer(audioBufferList)
            let sr = 44100.0
            for frame in 0..<Int(frameCount) {
                if phasor.releasing {
                    phasor.amp += (0 - phasor.amp) * 0.004
                } else {
                    phasor.amp += (phasor.target - phasor.amp) * 0.012
                }
                let sample = (0.18 * sin(phasor.phase) + 0.07 * sin(phasor.phase2)) * Double(phasor.amp)
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
        engine.connect(src, to: tapMixer, format: format)
        voices[midi] = Voice(osc: src, phasor: phasor)
        voiceOrder.append(midi)
    }

    private func fadeOut(_ midi: Int) {
        guard let voice = voices.removeValue(forKey: midi) else { return }
        voiceOrder.removeAll { $0 == midi }
        voice.phasor.releasing = true
        let osc = voice.osc
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 90_000_000)
            if voices[midi] == nil {
                engine.detach(osc)
            }
        }
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
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            self?.consume(buffer, sampleRate: format.sampleRate)
        }
        didInstallTap = true
    }

    private func ensureMixerTap() {
        if mixerTapOn || mode == .live { return }
        installMixerTap()
    }

    private func installMixerTap() {
        tapMixer.removeTap(onBus: 0)
        let format = AVAudioFormat(standardFormatWithSampleRate: 44100, channels: 1)
        tapMixer.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            self?.consume(buffer, sampleRate: 44100)
        }
        mixerTapOn = true
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
        guard mode == .live || mode == .replay || !voices.isEmpty else { return }
        let tous = isTous
        var bands: [(lo: Double, hi: Double)] = [(PitchMath.mixedLoHz, PitchMath.mixedHiHz)]
        if !tous {
            let chosen = liveTracks.filter { selectedTrackIds.contains($0.id) }
            bands = chosen.flatMap { t in
                (1...8).map { n in
                    let f = t.f0 * Double(n)
                    return (f * 0.97, f * 1.03)
                }
            }
            if bands.isEmpty { bands = [(PitchMath.mixedLoHz, PitchMath.mixedHiHz)] }
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
        lastClusters = clustered
        lastPeaks = result.mixPeaks
        syncClusters(clustered, now: now)
        publishSpectrum(clusters: clustered, peaks: result.mixPeaks)
        lit = result.lit
        scoreKeeper.setNeeded(Set(result.lit.map(\.midi)))
        for midi in pressed.union(boundPressed) { scoreKeeper.press(midi) }
        scoreValue = scoreKeeper.score
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
        selectedTrackIds = selectedTrackIds.filter { id in liveTracks.contains { $0.id == id } }
        pushHist()
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
        selectedTrackIds = []
        lastClusters = []
        lastPeaks = []
        specBus.clear()
        analyzer.reset()
    }

    private func publishSpectrum(clusters: [SpectralCluster], peaks: [SpecPeak]) {
        var marks: [SpecMark] = []
        var seen = Set<Int>()
        for c in clusters {
            let midi = PitchMath.foldedMidi(freq: c.f0, concertA: concertA, fold: false)
            let name = NoteName.pitchClass(of: midi)
            marks.append(SpecMark(f: c.f0, db: c.db, name: name, kind: .cluster))
            seen.insert(midi)
        }
        for midi in pressed {
            let f = PitchMath.midiToHz(midi, concertA: concertA)
            let db = lookupDb(f)
            marks.append(SpecMark(f: f, db: db, name: NoteName.pitchClass(of: midi), kind: .held))
        }
        for p in peaks.prefix(64) {
            let midi = PitchMath.foldedMidi(freq: p.f, concertA: concertA, fold: false)
            if seen.contains(midi) { continue }
            marks.append(SpecMark(f: p.f, db: p.db, name: NoteName.pitchClass(of: midi), kind: .peak))
        }
        specBus.update(db: analyzer.lastDb, binHz: analyzer.lastBinHz, marks: marks)
    }

    private func lookupDb(_ f: Double) -> Float {
        let bins = analyzer.lastDb
        let binHz = analyzer.lastBinHz
        guard bins.count > 2, binHz > 0 else { return -24 }
        let i = min(bins.count - 1, max(1, Int((f / binHz).rounded())))
        return max(-48, bins[i])
    }

    private func publishHeld() {
        publishSpectrum(clusters: lastClusters, peaks: lastPeaks)
    }

    private func onDisplayTick() {
        tickDisplay(now: ProcessInfo.processInfo.systemUptime)
        armDisplayPulse()
    }

    func tickDisplay(now: TimeInterval) {
        let cols = histLen
        let secPerCol = waveWindowSec / Double(max(1, cols))
        if histClock == 0 { histClock = now }
        var shifts = Int((now - histClock) / secPerCol)
        if shifts < 1 {
            for t in liveTracks {
                if var h = trackEnergyHist[t.id], !h.isEmpty {
                    h[h.count - 1] = Float(t.energy)
                    trackEnergyHist[t.id] = h
                }
            }
            return
        }
        if shifts > cols { shifts = cols }
        histClock += Double(shifts) * secPerCol
        for t in liveTracks {
            var h = trackEnergyHist[t.id] ?? Array(repeating: Float(0), count: cols)
            if h.count != cols { h = Array(repeating: 0, count: cols) }
            if shifts >= cols {
                h = Array(repeating: Float(t.energy), count: cols)
            } else {
                h.removeFirst(shifts)
                h.append(contentsOf: repeatElement(Float(t.energy), count: shifts))
            }
            trackEnergyHist[t.id] = h
        }
        let ids = Set(liveTracks.map(\.id))
        trackEnergyHist = trackEnergyHist.filter { ids.contains($0.key) }
    }

    private func wantsDisplayPulse() -> Bool {
        mode != .idle || scrubbing || !pressed.isEmpty || !fingerGate.held.isEmpty || !liveTracks.isEmpty
    }

    private func armDisplayPulse() {
        if wantsDisplayPulse() {
            displayPulse.start()
        } else {
            displayPulse.stop()
            histClock = 0
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
    var amp: Float = 0
    var target: Float = 1
    var releasing = false
}

