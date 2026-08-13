import Foundation

enum PitchMath {
    static let midiLo = 36 // C2
    static let midiHi = 96 // C7
    static let a4Ref = 440.0
    static let a4Min = 415.0
    static let a4Max = 466.0
    static let mixedLoHz = 60.0
    static let mixedHiHz = 2500.0

    static let blackPitchClasses: Set<Int> = [1, 3, 6, 8, 10]

    static func isBlack(_ midi: Int) -> Bool {
        blackPitchClasses.contains(((midi % 12) + 12) % 12)
    }

    static func octave(of midi: Int) -> Int {
        midi / 12 - 1
    }

    static func midiToHz(_ midi: Int, concertA: Double) -> Double {
        concertA * pow(2.0, Double(midi - 69) / 12.0)
    }

    static func hzToMidi(_ freq: Double, concertA: Double) -> Double {
        69 + 12 * log2(freq / concertA)
    }

    static func foldedMidi(freq: Double, concertA: Double, fold: Bool) -> Int {
        var m = hzToMidi(freq, concertA: concertA)
        guard m.isFinite else { return -1 }
        if fold {
            while m < Double(midiLo) { m += 12 }
            while m > Double(midiHi) { m -= 12 }
        }
        return Int(m.rounded())
    }

    static func whiteKeyCount() -> Int {
        (midiLo...midiHi).filter { !isBlack($0) }.count
    }
}

struct LitNote: Hashable, Identifiable {
    var midi: Int
    var db: Float
    var freq: Double

    var id: Int { midi }
    var name: NoteName { NoteName.pitchClass(of: midi) }
    var label: String { "\(name.french)\(PitchMath.octave(of: midi))" }
}

struct PeakPickConfig {
    var sensitivity: Double
    var chords: Bool
    var concertA: Double
    var autotune: Bool
    var bands: [(lo: Double, hi: Double)]
    var foldOctaves: Bool
}

struct PeakPickResult {
    var lit: [LitNote]
    var harmonics: Set<Int>
    var chroma: [NoteName: Float]
    var loudest: Float
    var mixPeaks: [SpecPeak]
}
