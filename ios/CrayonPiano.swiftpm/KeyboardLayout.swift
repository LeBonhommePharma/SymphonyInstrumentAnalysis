import Foundation
import UIKit

enum KeyboardLayoutId: String {
    case us
    case csa
}

enum KeyHighlight: String {
    case idle
    case held
    case need
    case hit
}

enum KeyboardLayout {
    /// Physical KeyboardEvent.code → MIDI. Same on US and Canadian French CSA.
    static let codeToMidi: [String: Int] = [
        "KeyZ": 48, "KeyS": 49, "KeyX": 50, "KeyD": 51, "KeyC": 52,
        "KeyV": 53, "KeyG": 54, "KeyB": 55, "KeyH": 56, "KeyN": 57,
        "KeyJ": 58, "KeyM": 59,
        "KeyQ": 60, "Digit2": 61, "KeyW": 62, "Digit3": 63, "KeyE": 64,
        "KeyR": 65, "Digit5": 66, "KeyT": 67, "Digit6": 68, "KeyY": 69,
        "Digit7": 70, "KeyU": 71, "KeyI": 72, "Digit9": 73, "KeyO": 74,
        "Digit0": 75, "KeyP": 76
    ]

    static let labels: [KeyboardLayoutId: [String: String]] = [
        .us: [
            "KeyZ": "Z", "KeyS": "S", "KeyX": "X", "KeyD": "D", "KeyC": "C",
            "KeyV": "V", "KeyG": "G", "KeyB": "B", "KeyH": "H", "KeyN": "N",
            "KeyJ": "J", "KeyM": "M", "KeyQ": "Q", "Digit2": "2", "KeyW": "W",
            "Digit3": "3", "KeyE": "E", "KeyR": "R", "Digit5": "5", "KeyT": "T",
            "Digit6": "6", "KeyY": "Y", "Digit7": "7", "KeyU": "U", "KeyI": "I",
            "Digit9": "9", "KeyO": "O", "Digit0": "0", "KeyP": "P",
            "Slash": "/", "Backquote": "`", "BracketLeft": "[", "Quote": "'"
        ],
        .csa: [
            "KeyZ": "Z", "KeyS": "S", "KeyX": "X", "KeyD": "D", "KeyC": "C",
            "KeyV": "V", "KeyG": "G", "KeyB": "B", "KeyH": "H", "KeyN": "N",
            "KeyJ": "J", "KeyM": "M", "KeyQ": "Q", "Digit2": "2", "KeyW": "W",
            "Digit3": "3", "KeyE": "E", "KeyR": "R", "Digit5": "5", "KeyT": "T",
            "Digit6": "6", "KeyY": "Y", "Digit7": "7", "KeyU": "U", "KeyI": "I",
            "Digit9": "9", "KeyO": "O", "Digit0": "0", "KeyP": "P",
            "Slash": "é", "Backquote": "/", "BracketLeft": "^", "Quote": "`",
            "IntlBackslash": "ù"
        ]
    ]

    static func highlight(midi: Int, needed: Set<Int>, pressed: Set<Int>) -> KeyHighlight {
        let want = needed.contains(midi)
        let have = pressed.contains(midi)
        if want && have { return .hit }
        if want { return .need }
        if have { return .held }
        return .idle
    }

    static func infer(code: String, key: String) -> KeyboardLayoutId? {
        switch code {
        case "Slash":
            if key == "é" { return .csa }
            if key == "/" { return .us }
        case "Backquote":
            if key == "/" || key == "#" { return .csa }
            if key == "`" || key == "~" { return .us }
        case "BracketLeft":
            if key == "^" { return .csa }
            if key == "[" { return .us }
        case "Quote":
            if key == "`" { return .csa }
            if key == "'" || key == "\"" { return .us }
        case "IntlBackslash":
            if key == "ù" { return .csa }
        default:
            break
        }
        return nil
    }

    static func detect() -> KeyboardLayoutId {
        let langs = Locale.preferredLanguages.joined(separator: " ").lowercased()
        if langs.contains("fr-ca") || langs.contains("fr_ca") { return .csa }
        return .us
    }

    static func midi(forCharacters chars: String) -> Int? {
        let low = chars.lowercased()
        let us: [String: String] = [
            "z": "KeyZ", "s": "KeyS", "x": "KeyX", "d": "KeyD", "c": "KeyC",
            "v": "KeyV", "g": "KeyG", "b": "KeyB", "h": "KeyH", "n": "KeyN",
            "j": "KeyJ", "m": "KeyM", "q": "KeyQ", "2": "Digit2", "w": "KeyW",
            "3": "Digit3", "e": "KeyE", "r": "KeyR", "5": "Digit5", "t": "KeyT",
            "y": "KeyY", "6": "Digit6", "7": "Digit7", "u": "KeyU", "i": "KeyI",
            "9": "Digit9", "o": "KeyO", "0": "Digit0", "p": "KeyP"
        ]
        if let code = us[low] { return codeToMidi[code] }
        if low == "é" { return codeToMidi["Slash"] }
        return nil
    }
}

final class ScoreKeeper {
    var score = 0
    var streak = 0
    var needed: Set<Int> = []
    private var awarded: Set<Int> = []
    static let hitPoints = 10
    static let streakBonus = 1

    func setNeeded(_ midis: Set<Int>) {
        needed = midis
        awarded = awarded.intersection(midis)
        if needed.isEmpty { streak = 0 }
    }

    @discardableResult
    func press(_ midi: Int) -> KeyHighlight {
        if needed.contains(midi) && !awarded.contains(midi) {
            awarded.insert(midi)
            score += Self.hitPoints + streak * Self.streakBonus
            streak += 1
            return .hit
        }
        if needed.contains(midi) { return .hit }
        return .held
    }

    func resetSession() {
        score = 0
        streak = 0
        needed = []
        awarded = []
    }
}

final class ScoreStore {
    static let allTimeKey = "crayon-piano-score-allTime"
    static let sourcesKey = "crayon-piano-score-sources"

    var allTime: Int
    var bestBySource: [String: Int]

    init() {
        allTime = UserDefaults.standard.integer(forKey: Self.allTimeKey)
        bestBySource = (UserDefaults.standard.dictionary(forKey: Self.sourcesKey) as? [String: Int]) ?? [:]
    }

    func best(for source: String) -> Int {
        max(allTime, bestBySource[source] ?? 0)
    }

    @discardableResult
    func record(source: String, score: Int) -> Bool {
        var improved = false
        if score > allTime {
            allTime = score
            improved = true
        }
        let key = source.isEmpty ? "live" : source
        if score > (bestBySource[key] ?? 0) {
            bestBySource[key] = score
            improved = true
        }
        if improved {
            UserDefaults.standard.set(allTime, forKey: Self.allTimeKey)
            UserDefaults.standard.set(bestBySource, forKey: Self.sourcesKey)
        }
        return improved
    }
}
