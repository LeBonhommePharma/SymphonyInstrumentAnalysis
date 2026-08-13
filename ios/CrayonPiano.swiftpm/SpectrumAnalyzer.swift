import Accelerate
import Foundation

/// Ports the crayon-piano AnalyserNode peak-picker (same gates as `web/keyboard.html`).
final class SpectrumAnalyzer {
    let fftSize: Int
    private var window: [Float]
    private var real: [Float]
    private var imag: [Float]
    private var magnitudes: [Float]
    private var dbSpectrum: [Float]
    private var smooth: [Float]
    private let log2n: vDSP_Length
    private let fftSetup: FFTSetup
    private var centsWindow: [(t: Double, cents: Double)] = []
    private(set) var concertA: Double = PitchMath.a4Ref
    private(set) var tuneReady = false

    init(fftSize: Int = 4096) {
        self.fftSize = fftSize
        log2n = vDSP_Length(log2(Double(fftSize)))
        guard let setup = vDSP_create_fftsetup(log2n, FFTRadix(kFFTRadix2)) else {
            fatalError("Unable to create FFT setup")
        }
        fftSetup = setup
        window = [Float](repeating: 0, count: fftSize)
        vDSP_hann_window(&window, vDSP_Length(fftSize), Int32(vDSP_HANN_NORM))
        real = [Float](repeating: 0, count: fftSize / 2)
        imag = [Float](repeating: 0, count: fftSize / 2)
        magnitudes = [Float](repeating: 0, count: fftSize / 2)
        dbSpectrum = [Float](repeating: -120, count: fftSize / 2)
        let nKeys = PitchMath.midiHi - PitchMath.midiLo + 1
        smooth = [Float](repeating: -120, count: nKeys)
    }

    deinit {
        vDSP_destroy_fftsetup(fftSetup)
    }

    func reset() {
        smooth = smooth.map { _ in -120 }
        centsWindow.removeAll()
        concertA = PitchMath.a4Ref
        tuneReady = false
    }

    func lockConcertA(_ locked: Bool) {
        if locked {
            concertA = PitchMath.a4Ref
        }
    }

    func analyze(
        samples: [Float],
        sampleRate: Double,
        now: Double,
        config: PeakPickConfig
    ) -> PeakPickResult {
        let n = min(samples.count, fftSize)
        guard n > 16 else {
            return PeakPickResult(lit: [], harmonics: [], chroma: [:], loudest: -120, mixPeaks: [])
        }

        var windowed = [Float](repeating: 0, count: fftSize)
        samples.prefix(n).enumerated().forEach { windowed[$0.offset] = $0.element }
        vDSP_vmul(windowed, 1, window, 1, &windowed, 1, vDSP_Length(fftSize))

        real.withUnsafeMutableBufferPointer { rp in
            imag.withUnsafeMutableBufferPointer { ip in
                var split = DSPSplitComplex(realp: rp.baseAddress!, imagp: ip.baseAddress!)
                windowed.withUnsafeBufferPointer { wp in
                    wp.baseAddress!.withMemoryRebound(to: DSPComplex.self, capacity: fftSize / 2) { complex in
                        vDSP_ctoz(complex, 2, &split, 1, vDSP_Length(fftSize / 2))
                    }
                }
                vDSP_fft_zrip(fftSetup, &split, 1, log2n, FFTDirection(FFT_FORWARD))
                vDSP_zvmags(&split, 1, &magnitudes, 1, vDSP_Length(fftSize / 2))
            }
        }

        var nyquistScale: Float = 1.0 / Float(fftSize)
        vDSP_vsmul(magnitudes, 1, &nyquistScale, &magnitudes, 1, vDSP_Length(fftSize / 2))
        var minMag: Float = 1e-12
        vDSP_vdbcon(magnitudes, 1, &minMag, &dbSpectrum, 1, vDSP_Length(fftSize / 2), 1)

        let binHz = sampleRate / Double(fftSize)
        if config.autotune {
            updateConcertPitch(binHz: binHz, now: now)
        }

        var mixPeaks: [SpecPeak] = []
        let mix0 = max(2, Int(40.0 / binHz))
        let mix1 = min(dbSpectrum.count - 2, Int(ceil(5000.0 / binHz)))
        if mix1 > mix0 {
            var floorSamples: [Float] = []
            let step = max(1, (mix1 - mix0) / 72)
            var fi = mix0
            while fi <= mix1 {
                floorSamples.append(dbSpectrum[fi])
                fi += step
            }
            floorSamples.sort()
            let floor = floorSamples.isEmpty ? Float(-90) : floorSamples[floorSamples.count / 2]
            let minDb = max(Float(-78), floor + 10)
            for i in mix0...mix1 {
                let db = dbSpectrum[i]
                if db < minDb { continue }
                if db > dbSpectrum[i - 1] && db >= dbSpectrum[i + 1]
                    && db > dbSpectrum[i - 2] && db >= dbSpectrum[i + 2] {
                    let denom = dbSpectrum[i - 1] - 2 * db + dbSpectrum[i + 1]
                    let delta: Float = denom != 0 ? 0.5 * (dbSpectrum[i - 1] - dbSpectrum[i + 1]) / denom : 0
                    let pf = (Double(i) + Double(delta)) * binHz
                    if pf >= 40 && pf <= 5000 {
                        mixPeaks.append(SpecPeak(f: pf, db: db))
                    }
                }
            }
            mixPeaks.sort { $0.db > $1.db }
            if mixPeaks.count > 36 { mixPeaks = Array(mixPeaks.prefix(36)) }
        }

        let a = config.autotune ? concertA : config.concertA
        let scanLo = config.bands.map(\.lo).min() ?? PitchMath.mixedLoHz
        let scanHi = config.bands.map(\.hi).max() ?? PitchMath.mixedHiHz
        let i0 = max(2, Int(scanLo / binHz))
        let i1 = min(dbSpectrum.count - 2, Int(ceil(scanHi / binHz)))
        let nKeys = PitchMath.midiHi - PitchMath.midiLo + 1
        var score = [Float](repeating: -120, count: nKeys)

        func inBands(_ freq: Double) -> Bool {
            config.bands.contains { freq >= $0.lo && freq <= $0.hi }
        }

        var peaks: [(freq: Double, db: Float)] = []
        if i1 > i0 {
            for i in i0...i1 {
                let freq = Double(i) * binHz
                if !inBands(freq) { continue }
                let db = dbSpectrum[i]
                if db > dbSpectrum[i - 1] && db >= dbSpectrum[i + 1]
                    && db > dbSpectrum[i - 2] && db >= dbSpectrum[i + 2] {
                    let denom = dbSpectrum[i - 1] - 2 * db + dbSpectrum[i + 1]
                    let delta: Float = denom != 0 ? 0.5 * (dbSpectrum[i - 1] - dbSpectrum[i + 1]) / denom : 0
                    let pf = (Double(i) + Double(delta)) * binHz
                    if inBands(pf) {
                        peaks.append((pf, db))
                    }
                }
                let midi = PitchMath.foldedMidi(freq: freq, concertA: a, fold: config.foldOctaves)
                if midi >= PitchMath.midiLo && midi <= PitchMath.midiHi {
                    let idx = midi - PitchMath.midiLo
                    if db > score[idx] { score[idx] = db }
                }
            }
        }
        peaks.sort { $0.db > $1.db }
        for peak in peaks {
            let midi = PitchMath.foldedMidi(freq: peak.freq, concertA: a, fold: config.foldOctaves)
            if midi < PitchMath.midiLo || midi > PitchMath.midiHi { continue }
            let idx = midi - PitchMath.midiLo
            if peak.db + 2 > score[idx] { score[idx] = peak.db + 2 }
        }

        var loudest: Float = -120
        for i in 0..<nKeys {
            smooth[i] = 0.62 * smooth[i] + 0.38 * score[i]
            if smooth[i] > loudest { loudest = smooth[i] }
        }

        let sens = config.sensitivity
        let absGate = Float(-48 - sens * 36)
        let relDb = Float(10 + sens * 18)
        let gate = max(absGate, loudest - relDb)
        let maxN = config.chords ? 8 : 1

        var candidates: [LitNote] = []
        for i in 0..<nKeys {
            let s = smooth[i]
            if s < gate { continue }
            let left = i > 0 ? smooth[i - 1] : -999
            let right = i < nKeys - 1 ? smooth[i + 1] : -999
            if s >= left && s >= right {
                let midi = i + PitchMath.midiLo
                candidates.append(LitNote(midi: midi, db: s, freq: PitchMath.midiToHz(midi, concertA: a)))
            }
        }
        candidates.sort { $0.db > $1.db }
        let lit = Array(candidates.prefix(maxN))
        let litSet = Set(lit.map(\.midi))

        var harmonics = Set<Int>()
        for note in lit {
            for g in [note.midi + 12, note.midi - 12, note.midi + 7, note.midi - 7] {
                if g >= PitchMath.midiLo && g <= PitchMath.midiHi && !litSet.contains(g) {
                    harmonics.insert(g)
                }
            }
        }

        var chroma: [NoteName: Float] = [:]
        for name in NoteName.allCases { chroma[name] = -120 }
        for i in 0..<nKeys {
            let name = NoteName.pitchClass(of: i + PitchMath.midiLo)
            chroma[name] = max(chroma[name] ?? -120, smooth[i])
        }

        return PeakPickResult(lit: lit, harmonics: harmonics, chroma: chroma, loudest: loudest, mixPeaks: mixPeaks)
    }

    private func updateConcertPitch(binHz: Double, now: Double) {
        let i0 = max(2, Int(80.0 / binHz))
        let i1 = min(dbSpectrum.count - 2, Int(ceil(1400.0 / binHz)))
        guard i1 > i0 else { return }

        var samples: [Float] = []
        let step = max(1, (i1 - i0) / 72)
        var i = i0
        while i <= i1 {
            samples.append(dbSpectrum[i])
            i += step
        }
        samples.sort()
        let floor = samples.isEmpty ? Float(-90) : samples[samples.count / 2]
        let minDb = max(Float(-72), floor + 8)

        var peaks: [(freq: Double, db: Float)] = []
        for idx in i0...i1 {
            let db = dbSpectrum[idx]
            if db < minDb { continue }
            if db > dbSpectrum[idx - 1] && db >= dbSpectrum[idx + 1]
                && db > dbSpectrum[idx - 2] && db >= dbSpectrum[idx + 2] {
                let denom = dbSpectrum[idx - 1] - 2 * db + dbSpectrum[idx + 1]
                let delta: Float = denom != 0 ? 0.5 * (dbSpectrum[idx - 1] - dbSpectrum[idx + 1]) / denom : 0
                let freq = (Double(idx) + Double(delta)) * binHz
                if freq >= 80 && freq <= 1400 {
                    peaks.append((freq, db))
                }
            }
        }
        peaks.sort { $0.db > $1.db }
        peaks = Array(peaks.prefix(16))

        var funds: [(freq: Double, db: Float)] = []
        for p in peaks.sorted(by: { $0.freq < $1.freq }) {
            var harmonic = false
            for f in funds {
                let n = (p.freq / f.freq).rounded()
                if n < 2 || n > 8 { continue }
                let cents = 1200 * log2(p.freq / (n * f.freq))
                if abs(cents) < 35 {
                    harmonic = true
                    break
                }
            }
            if !harmonic { funds.append(p) }
        }

        var votes: [Double] = []
        for p in funds {
            let midi = PitchMath.hzToMidi(p.freq, concertA: PitchMath.a4Ref).rounded()
            let expected = PitchMath.midiToHz(Int(midi), concertA: PitchMath.a4Ref)
            if expected <= 0 { continue }
            let cents = 1200 * log2(p.freq / expected)
            if cents.isFinite && abs(cents) <= 90 {
                votes.append(cents)
            }
        }
        if votes.count >= 2 {
            let med = Self.median(votes)
            centsWindow.append((now, med))
            centsWindow.removeAll { now - $0.t > 2.2 }
        }
        if centsWindow.count >= 8 {
            let med = Self.median(centsWindow.map(\.cents))
            let clamped = min(100, max(-100, med))
            let target = PitchMath.a4Ref * pow(2.0, clamped / 1200)
            let alpha = centsWindow.count >= 24 ? 0.12 : 0.05
            concertA += alpha * (target - concertA)
            concertA = min(PitchMath.a4Max, max(PitchMath.a4Min, concertA))
            tuneReady = true
        }
    }

    private static func median(_ values: [Double]) -> Double {
        guard !values.isEmpty else { return 0 }
        let s = values.sorted()
        let mid = s.count / 2
        if s.count % 2 == 1 { return s[mid] }
        return 0.5 * (s[mid - 1] + s[mid])
    }
}
