import Accelerate
import Foundation

/// Live BPM counter — port of scripts/bpm_tracker.py and web/bpm_tracker.js.
/// Contract: piano/dsp_contract.json → "bpm". Same constants, same math:
///
///   front end   2048-point Hann STFT, hop sr/100, bin magnitudes averaged into
///               log bands (6/octave, 30 Hz–8 kHz), log1p(100·m) per band,
///               SuperFlux flux (rise above the 3-band max of the previous frame
///               minus a 0.05 deadband), 1 s running mean removed, rectified
///   tempo       3-tap smoothed envelope, multiplicative tolerant comb
///               r(L)·(1 + ½·max r(2L±1) + ¼·max r(4L±2)) over 8 s, log-Gaussian
///               prior at 128 BPM (σ 0.75 oct), 60–200 BPM, parabolic refine,
///               halving test (max r(L*/2±1) ≥ 0.9·r(L*) → the faster reading)
///   ready       r(L*) ≥ 0.12 AND beat-phase fold collapse 1−H ≥ 0.12
///   display     median of the last 5 estimates
///
/// Foundation + Accelerate only, so `scripts/run_bpm_selftest.swift` can
/// compile it with swiftc outside the app.
enum BpmContract {
    static let onsetHz = 100.0
    static let frame = 2048
    static let windowS = 8.0
    static let minS = 3.0
    static let updateS = 0.25
    static let bpmMin = 60.0
    static let bpmMax = 200.0
    static let priorBpm = 128.0
    static let priorSigmaOct = 0.75
    static let foldBins = 16
    static let combW2 = 0.5
    static let combW4 = 0.25
    static let halfRatio = 0.9
    static let fluxMu = 100.0
    static let fluxLoHz = 30.0
    static let fluxHiHz = 8000.0
    static let bandsPerOctave = 6
    static let meanTauS = 1.0
    static let fluxDeadband = 0.05
    static let readyConfidence = 0.12
    static let readyCollapse = 0.12
    static let medianN = 5
}

struct TempoEstimate {
    var bpm: Double
    var lag: Double
    var confidence: Double
    var collapse: Double
    var phase: Double
    var ready: Bool

    static let notReady = TempoEstimate(bpm: 0, lag: 0, confidence: 0, collapse: 0, phase: 0, ready: false)
}

struct BpmState: Equatable {
    var bpm: Double?
    var confidence: Double
    var collapse: Double
    var phase: Double
    var ready: Bool
    var seconds: Double

    static let idle = BpmState(bpm: nil, confidence: 0, collapse: 0, phase: 0, ready: false, seconds: 0)

    /// ♩ — (idle) · ♩ … (settling) · ♩ 140 (locked). Same strings as the web and TUI.
    func text(active: Bool = true) -> String {
        if !active { return "♩ —" }
        guard ready, let bpm else { return "♩ …" }
        return "♩ \(Int(bpm.rounded()))"
    }
}

enum TempoMath {
    static func prior(bpm: Double) -> Double {
        guard bpm > 0 else { return 0 }
        let z = log2(bpm / BpmContract.priorBpm) / BpmContract.priorSigmaOct
        return exp(-0.5 * z * z)
    }

    /// Biased, energy-normalised autocorrelation r[0...maxLag], r[0] = 1.
    static func autocorrelation(_ x: [Double], maxLag: Int) -> [Double] {
        let n = x.count
        var r = [Double](repeating: 0, count: maxLag + 1)
        var energy = 0.0
        for v in x { energy += v * v }
        guard energy > 0, n > 0 else { return r }
        let top = min(maxLag, n - 1)
        if top >= 0 {
            for lag in 0...top {
                var s = 0.0
                var i = lag
                while i < n {
                    s += x[i] * x[i - lag]
                    i += 1
                }
                r[lag] = s / energy
            }
        }
        return r
    }

    /// (1 − normalised Shannon entropy, phase of the loudest bin) of the beat fold.
    static func foldCollapse(_ env: [Double], lag: Double, bins: Int = BpmContract.foldBins) -> (collapse: Double, phase: Double) {
        let n = env.count
        var total = 0.0
        for v in env { total += v }
        guard total > 0, lag > 0, n > 0 else { return (0, 0) }
        var hist = [Double](repeating: 0, count: bins)
        for i in 0..<n {
            let phase = (Double(i) / lag).truncatingRemainder(dividingBy: 1)
            let b = min(bins - 1, Int(phase * Double(bins)))
            hist[b] += env[i]
        }
        var h = 0.0
        var best = 0
        for b in 0..<bins {
            let p = hist[b] / total
            if p > 0 { h -= p * log(p) }
            if hist[b] > hist[best] { best = b }
        }
        h /= log(Double(bins))
        return (max(0, min(1, 1 - h)), Double(best) / Double(bins))
    }

    /// 3-tap Hann (¼, ½, ¼) with edge hold — widens 10 ms spikes to ~30 ms.
    static func smooth3(_ env: [Double]) -> [Double] {
        let n = env.count
        guard n >= 3 else { return env }
        var out = [Double](repeating: 0, count: n)
        for i in 1..<(n - 1) { out[i] = 0.25 * env[i - 1] + 0.5 * env[i] + 0.25 * env[i + 1] }
        out[0] = 0.75 * env[0] + 0.25 * env[1]
        out[n - 1] = 0.75 * env[n - 1] + 0.25 * env[n - 2]
        return out
    }

    static func estimate(_ envIn: [Double], fps: Double = BpmContract.onsetHz) -> TempoEstimate {
        let n = envIn.count
        var env = [Double](repeating: 0, count: n)
        var sum = 0.0
        for i in 0..<n {
            env[i] = max(0, envIn[i])
            sum += env[i]
        }
        let lagMin = Int((fps * 60 / BpmContract.bpmMax).rounded())
        let lagMax = Int((fps * 60 / BpmContract.bpmMin).rounded())
        guard n >= lagMax + 2, sum > 0 else { return .notReady }
        let smoothed = smooth3(env)
        var mean = 0.0
        for v in smoothed { mean += v }
        mean /= Double(n)
        var x = [Double](repeating: 0, count: n)
        var energy = 0.0
        for i in 0..<n {
            x[i] = smoothed[i] - mean
            energy += x[i] * x[i]
        }
        guard energy > 1e-12 else { return .notReady }
        let top = min(n - 1, 4 * lagMax)
        let r = autocorrelation(x, maxLag: top)
        func near(_ lag: Int, _ tol: Int) -> Double {
            let lo = max(0, lag - tol)
            let hi = min(top, lag + tol)
            guard hi >= lo else { return 0 }
            var m = -Double.infinity
            for l in lo...hi where r[l] > m { m = r[l] }
            return m
        }
        func enhanced(_ lag: Int) -> Double {
            let own = max(0, r[lag])
            var comb = 1.0
            if 2 * lag <= top { comb += BpmContract.combW2 * max(0, near(2 * lag, 1)) }
            if 4 * lag <= top { comb += BpmContract.combW4 * max(0, near(4 * lag, 2)) }
            return own * comb
        }
        // One lag beyond each edge is scored too, so the parabola always has neighbours.
        let lo = max(1, lagMin - 1)
        let hi = min(top, lagMax + 1)
        var score = [Double](repeating: 0, count: hi + 1)
        for lag in lo...hi { score[lag] = enhanced(lag) * prior(bpm: 60 * fps / Double(lag)) }
        var best = lagMin
        for lag in lagMin...lagMax where score[lag] > score[best] { best = lag }
        let half = Int((Double(best) / 2).rounded())
        if half >= lagMin, r[best] > 0, near(half, 1) >= BpmContract.halfRatio * r[best] {
            var pick = max(lagMin, half - 1)
            let upper = min(lagMax, half + 1)
            if upper >= pick {
                for l in pick...upper where r[l] > r[pick] { pick = l }
            }
            best = pick
        }
        var lag = Double(best)
        if best - 1 >= lo, best + 1 <= hi {
            let s0 = score[best - 1]
            let s1 = score[best]
            let s2 = score[best + 1]
            let denom = s0 - 2 * s1 + s2
            if denom < 0 {
                lag = Double(best) + max(-0.5, min(0.5, 0.5 * (s0 - s2) / denom))
            }
        }
        let confidence = max(0, min(1, r[best]))
        let fold = foldCollapse(env, lag: lag)
        let ready = confidence >= BpmContract.readyConfidence && fold.collapse >= BpmContract.readyCollapse
        return TempoEstimate(
            bpm: 60 * fps / lag,
            lag: lag,
            confidence: confidence,
            collapse: fold.collapse,
            phase: fold.phase,
            ready: ready
        )
    }

    /// [(kLo, kHi)] inclusive bin ranges of the log bands that hold ≥ 1 bin.
    /// Same plan as bpm_tracker.band_plan / BPM_TRACKER.bandPlan.
    static func bandPlan(binHz: Double, nBins: Int) -> [(Int, Int)] {
        let kLo = max(1, Int(ceil(BpmContract.fluxLoHz / binHz)))
        let hiHz = min(BpmContract.fluxHiHz, binHz * Double(nBins - 1))
        let kHi = Int(floor(hiHz / binHz))
        var plan: [(Int, Int)] = []
        guard kHi >= kLo else { return plan }
        var cur = -1
        var start = kLo
        for k in kLo...kHi {
            let b = Int(floor(Double(BpmContract.bandsPerOctave) * log2(Double(k) * binHz / BpmContract.fluxLoHz)))
            if b != cur {
                if cur >= 0 { plan.append((start, k - 1)) }
                cur = b
                start = k
            }
        }
        if cur >= 0, kHi >= start { plan.append((start, kHi)) }
        return plan
    }

    /// Mean linear magnitude per band, log-compressed: ln(1 + 100·m_b).
    static func bandLogmag(_ mag: [Double], plan: [(Int, Int)]) -> [Double] {
        var out = [Double](repeating: 0, count: plan.count)
        for (i, range) in plan.enumerated() {
            var s = 0.0
            for k in range.0...range.1 { s += mag[k] }
            out[i] = log1p(BpmContract.fluxMu * (s / Double(range.1 - range.0 + 1)))
        }
        return out
    }

    /// SuperFlux-style flux between two log-magnitude frames.
    static func flux(_ logmag: [Double], prev: [Double]) -> Double {
        let n = min(logmag.count, prev.count)
        var flux = 0.0
        for k in 0..<n {
            var pm = prev[k]
            if k > 0, prev[k - 1] > pm { pm = prev[k - 1] }
            if k < n - 1, prev[k + 1] > pm { pm = prev[k + 1] }
            let d = logmag[k] - pm - BpmContract.fluxDeadband
            if d > 0 { flux += d }
        }
        return flux
    }
}

/// PCM in, onset strength out — one value per 1/onsetHz second. Mirrors
/// bpm_tracker.OnsetFrontEnd; not thread-safe on its own (BpmTracker locks).
final class OnsetFrontEnd {
    let sampleRate: Double
    let frame: Int
    let hop: Int
    private let plan: [(Int, Int)]
    private let alpha: Double
    private let window: [Float]
    private let log2n: vDSP_Length
    private let fftSetup: FFTSetup
    private var real: [Float]
    private var imag: [Float]
    private var magnitudes: [Float]
    private var buffer: [Float] = []
    private var prev: [Double]?
    private var mean = 0.0
    private var primed = false

    init(sampleRate: Double, frame: Int = BpmContract.frame) {
        self.sampleRate = sampleRate
        self.frame = frame
        hop = max(1, Int((sampleRate / BpmContract.onsetHz).rounded()))
        // Packed real FFT: bins 1…N/2−1 are plain; bin N/2 (Nyquist) is not read.
        plan = TempoMath.bandPlan(binHz: sampleRate / Double(frame), nBins: frame / 2)
        alpha = 1 / (BpmContract.meanTauS * BpmContract.onsetHz)
        // Symmetric Hann, (N−1) denominator, same as numpy.hanning.
        var w = [Float](repeating: 0, count: frame)
        for i in 0..<frame {
            w[i] = Float(0.5 - 0.5 * cos(2 * Double.pi * Double(i) / Double(frame - 1)))
        }
        window = w
        log2n = vDSP_Length(log2(Double(frame)))
        guard let setup = vDSP_create_fftsetup(log2n, FFTRadix(kFFTRadix2)) else {
            fatalError("Unable to create FFT setup")
        }
        fftSetup = setup
        real = [Float](repeating: 0, count: frame / 2)
        imag = [Float](repeating: 0, count: frame / 2)
        magnitudes = [Float](repeating: 0, count: frame / 2)
    }

    deinit {
        vDSP_destroy_fftsetup(fftSetup)
    }

    func reset() {
        buffer.removeAll(keepingCapacity: true)
        prev = nil
        mean = 0
        primed = false
    }

    func push(_ samples: [Float]) -> [Double] {
        guard !samples.isEmpty else { return [] }
        buffer.append(contentsOf: samples)
        var out: [Double] = []
        var offset = 0
        while buffer.count - offset >= frame {
            out.append(onset(Array(buffer[offset..<(offset + frame)])))
            offset += hop
        }
        if offset > 0 { buffer.removeFirst(offset) }
        return out
    }

    private func onset(_ frameSamples: [Float]) -> Double {
        var windowed = [Float](repeating: 0, count: frame)
        vDSP_vmul(frameSamples, 1, window, 1, &windowed, 1, vDSP_Length(frame))
        real.withUnsafeMutableBufferPointer { rp in
            imag.withUnsafeMutableBufferPointer { ip in
                var split = DSPSplitComplex(realp: rp.baseAddress!, imagp: ip.baseAddress!)
                windowed.withUnsafeBufferPointer { wp in
                    wp.baseAddress!.withMemoryRebound(to: DSPComplex.self, capacity: frame / 2) { complex in
                        vDSP_ctoz(complex, 2, &split, 1, vDSP_Length(frame / 2))
                    }
                }
                vDSP_fft_zrip(fftSetup, &split, 1, log2n, FFTDirection(FFT_FORWARD))
                vDSP_zvmags(&split, 1, &magnitudes, 1, vDSP_Length(frame / 2))
            }
        }
        // vDSP_fft_zrip is 2× the DFT; m = 4·|X|/N puts a full-scale Hann sine at 1.
        let scale = 2.0 / Double(frame)
        var mag = [Double](repeating: 0, count: frame / 2)
        for k in 1..<(frame / 2) { mag[k] = sqrt(Double(max(magnitudes[k], 0))) * scale }
        let logmag = TempoMath.bandLogmag(mag, plan: plan)
        guard let previous = prev else {
            prev = logmag
            return 0
        }
        let flux = TempoMath.flux(logmag, prev: previous)
        prev = logmag
        if !primed {
            mean = flux
            primed = true
        } else {
            mean += (flux - mean) * alpha
        }
        return max(0, flux - mean)
    }
}

/// Push contiguous PCM from the audio tap; read `snapshot()` on the display tick.
final class BpmTracker: @unchecked Sendable {
    private let lock = NSLock()
    private var front: OnsetFrontEnd
    private var ring: [Double]
    private var count = 0
    private var lastUpdate = 0
    private var estimates: [TempoEstimate] = []
    private var state = BpmState.idle
    let fps = BpmContract.onsetHz

    init(sampleRate: Double = 44100) {
        front = OnsetFrontEnd(sampleRate: sampleRate)
        ring = [Double](repeating: 0, count: Int((BpmContract.windowS * BpmContract.onsetHz).rounded()))
    }

    func reset() {
        lock.lock()
        defer { lock.unlock() }
        front.reset()
        for i in ring.indices { ring[i] = 0 }
        count = 0
        lastUpdate = 0
        estimates.removeAll()
        state = .idle
    }

    func push(_ samples: [Float], sampleRate: Double) {
        lock.lock()
        defer { lock.unlock() }
        if sampleRate != front.sampleRate {
            front = OnsetFrontEnd(sampleRate: sampleRate)
        }
        let onsets = front.push(samples)
        guard !onsets.isEmpty else { return }
        pushOnsetsLocked(onsets)
    }

    func pushOnsets(_ values: [Double]) {
        lock.lock()
        defer { lock.unlock() }
        pushOnsetsLocked(values)
    }

    private func pushOnsetsLocked(_ values: [Double]) {
        let size = ring.count
        for v in values {
            ring[count % size] = v
            count += 1
        }
        if Double(count - lastUpdate) >= BpmContract.updateS * fps, Double(count) >= BpmContract.minS * fps {
            lastUpdate = count
            update()
        }
    }

    private func window() -> [Double] {
        let size = ring.count
        let m = min(count, size)
        var out = [Double](repeating: 0, count: m)
        for i in 0..<m { out[i] = ring[(count - m + i) % size] }
        return out
    }

    private func update() {
        let est = TempoMath.estimate(window(), fps: fps)
        estimates.append(est)
        if estimates.count > BpmContract.medianN { estimates.removeFirst(estimates.count - BpmContract.medianN) }
        let ready = estimates.filter(\.ready).map(\.bpm).sorted()
        var bpm: Double?
        if !ready.isEmpty {
            let mid = ready.count / 2
            bpm = ready.count % 2 == 1 ? ready[mid] : 0.5 * (ready[mid - 1] + ready[mid])
        }
        state = BpmState(
            bpm: bpm,
            confidence: est.confidence,
            collapse: est.collapse,
            phase: est.phase,
            ready: est.ready && !ready.isEmpty,
            seconds: Double(count) / fps
        )
    }

    func snapshot() -> BpmState {
        lock.lock()
        defer { lock.unlock() }
        return state
    }
}

/// Deterministic test signal — same recipe as bpm_tracker.synth_beat / synthBeat:
/// a 909-style kick every beat (160→50 Hz sweep with a click), hats on the off-beats, a pad.
enum BpmSelfTest {
    static func synthBeat(sampleRate sr: Double, seconds: Double, bpm: Double, hats: Bool = true, pad: Bool = true) -> [Float] {
        let n = Int(sr * seconds)
        var out = [Double](repeating: 0, count: n)
        let beat = 60 / bpm
        func burst(_ t0: Double, length: Double, decay: Double, amp: Double, freqs: [(Double, Double)]) {
            let i0 = Int((t0 * sr).rounded())
            let i1 = min(n, i0 + Int(length * sr))
            guard i1 > i0 else { return }
            for i in i0..<i1 {
                let t = Double(i - i0) / sr
                var sig = 0.0
                for (f, a) in freqs { sig += a * sin(2 * Double.pi * f * t) }
                out[i] += amp * exp(-t / decay) * sig
            }
        }
        func kick(_ t0: Double) {
            let i0 = Int((t0 * sr).rounded())
            let i1 = min(n, i0 + Int(0.25 * sr))
            guard i1 > i0 else { return }
            var phase = 0.0
            for i in i0..<i1 {
                let t = Double(i - i0) / sr
                let freq = 50 + 110 * exp(-t / 0.04)
                phase += 2 * Double.pi * freq / sr
                let body = sin(phase) * exp(-t / 0.09)
                let click = exp(-t / 0.003) * (sin(2 * Double.pi * 1800 * t) + 0.6 * sin(2 * Double.pi * 4100 * t))
                out[i] += 0.8 * body + 0.25 * click
            }
        }
        var t0 = 0.0
        while t0 < seconds {
            kick(t0)
            if hats { burst(t0 + beat / 2, length: 0.06, decay: 0.02, amp: 0.12, freqs: [(6000, 1), (9300, 0.7)]) }
            t0 += beat
        }
        if pad {
            for i in 0..<n { out[i] += 0.1 * sin(2 * Double.pi * 220 * Double(i) / sr) }
        }
        var peak = 0.0
        for v in out { peak = max(peak, abs(v)) }
        let g = 0.9 / (peak > 0 ? peak : 1)
        return out.map { Float($0 * g) }
    }

    static func track(_ audio: [Float], sampleRate: Double, chunk: Int = 4800) -> BpmState {
        let tracker = BpmTracker(sampleRate: sampleRate)
        var i = 0
        while i < audio.count {
            tracker.push(Array(audio[i..<min(audio.count, i + chunk)]), sampleRate: sampleRate)
            i += chunk
        }
        return tracker.snapshot()
    }

    /// Throws a description on the first failure; returns a one-line summary.
    static func run() throws -> String {
        struct Failure: Error, CustomStringConvertible {
            let description: String
        }
        func expect(_ name: String, _ state: BpmState, want: Double, tol: Double, minConf: Double) throws {
            guard state.ready, let bpm = state.bpm else { throw Failure(description: "\(name): tracker never locked \(state)") }
            if abs(bpm - want) > tol { throw Failure(description: "\(name): \(bpm) BPM, wanted \(want) ± \(tol)") }
            if state.confidence < minConf { throw Failure(description: "\(name): confidence \(state.confidence) < \(minConf)") }
        }
        var env = [Double](repeating: 0, count: 800)
        for i in stride(from: 0, to: 800, by: 50) { env[i] = 1 }
        let est = TempoMath.estimate(env)
        if !est.ready || abs(est.bpm - 120) > 0.5 || est.collapse < 0.85 {
            throw Failure(description: "impulse envelope should read 120 BPM with a collapsed fold, got \(est)")
        }
        if TempoMath.estimate([Double](repeating: 0, count: 800)).ready {
            throw Failure(description: "flat envelope must not be ready")
        }
        let sr = 48000.0
        try expect("140 BPM kick+hats+pad", track(synthBeat(sampleRate: sr, seconds: 10, bpm: 140), sampleRate: sr), want: 140, tol: 1.5, minConf: 0.25)
        try expect("90 BPM kicks only", track(synthBeat(sampleRate: sr, seconds: 12, bpm: 90, hats: false), sampleRate: sr), want: 90, tol: 1.5, minConf: 0.25)
        try expect("172 BPM kick+hats", track(synthBeat(sampleRate: sr, seconds: 10, bpm: 172), sampleRate: sr), want: 172, tol: 2, minConf: 0.2)
        try expect("44.1 kHz 128 BPM", track(synthBeat(sampleRate: 44100, seconds: 10, bpm: 128), sampleRate: 44100), want: 128, tol: 1.5, minConf: 0.25)
        try expect("64 BPM", track(synthBeat(sampleRate: sr, seconds: 12, bpm: 64), sampleRate: sr), want: 64, tol: 1.5, minConf: 0.25)
        try expect("138 BPM", track(synthBeat(sampleRate: sr, seconds: 10, bpm: 138), sampleRate: sr), want: 138, tol: 1.5, minConf: 0.25)
        try expect("198 BPM", track(synthBeat(sampleRate: sr, seconds: 10, bpm: 198), sampleRate: sr), want: 198, tol: 2, minConf: 0.25)
        let n = Int(sr * 6)
        var tone = [Float](repeating: 0, count: n)
        var chord = [Float](repeating: 0, count: n)
        for i in 0..<n {
            let t = Double(i) / sr
            tone[i] = Float(0.3 * sin(2 * Double.pi * 220 * t))
            chord[i] = Float(0.2 * (sin(2 * Double.pi * 130.8 * t) + sin(2 * Double.pi * 155.6 * t) + sin(2 * Double.pi * 196 * t)))
        }
        if track(tone, sampleRate: sr).ready { throw Failure(description: "a steady 220 Hz tone must not lock a tempo") }
        if track(chord, sampleRate: sr).ready { throw Failure(description: "a held chord must not lock a tempo") }
        if track([Float](repeating: 0, count: n), sampleRate: sr).ready { throw Failure(description: "silence must not lock a tempo") }
        let tracker = BpmTracker(sampleRate: sr)
        if tracker.snapshot().text() != "♩ …" || tracker.snapshot().text(active: false) != "♩ —" {
            throw Failure(description: "text idle/settling contract")
        }
        tracker.push(synthBeat(sampleRate: sr, seconds: 8, bpm: 140), sampleRate: sr)
        if tracker.snapshot().text() != "♩ 140" { throw Failure(description: "text locked contract, got \(tracker.snapshot().text())") }
        tracker.reset()
        if tracker.snapshot() != .idle { throw Failure(description: "reset must forget the previous song") }
        return "BpmTracker.swift: 140 / 90 / 172 / 128 BPM locked, tones and silence stay quiet"
    }
}
