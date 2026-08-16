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
        let raw = chars
        let low = chars.lowercased()
        for layoutId in ["us", "csa"] {
            for key in DualBoards.layout(layoutId).keys where key.kind == "char" {
                if key.base == raw || key.base.lowercased() == low {
                    return DualNoteMap.midi(for: key.kid)
                }
            }
        }
        return DualNoteMap.midi(for: chars)
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
