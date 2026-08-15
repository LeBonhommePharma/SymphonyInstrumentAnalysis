import Foundation

let maxFingers = 10
let clusterEps = 1.20
let boardGap = 18.0

struct DualKey: Hashable {
    var kid: String
    var row: Double
    var col: Double
    var w: Double
    var h: Double
    var kind: String
    var base: String
    var shift: String
    var altgr: String
    var dead: String
    var shiftDead: String
    var code: String
}

struct DualLayout {
    var id: String
    var name: String
    var nameFr: String
    var x0: Double
    var keys: [DualKey]

    func key(_ kid: String) -> DualKey? { keys.first { $0.kid == kid } }
    func key(code: String) -> DualKey? { keys.first { $0.code == code } }

    func center(_ key: DualKey) -> (Double, Double) {
        (x0 + key.col + key.w / 2, key.row + key.h / 2)
    }
}

struct HeldDual: Hashable {
    var board: String
    var kid: String
}

enum DualBoards {
    static let us = makeUS()
    static let csa = makeCSA()
    static var layouts: [String: DualLayout] { ["us": us, "csa": csa] }

    static func layout(_ id: String) -> DualLayout { layouts[id] ?? us }

    static func point(_ held: HeldDual) -> (Double, Double) {
        let board = layout(held.board)
        guard let key = board.key(held.kid) else { return (0, 0) }
        return board.center(key)
    }

    static func cluster(_ held: [HeldDual]) -> [[HeldDual]] {
        guard !held.isEmpty else { return [] }
        let pts = held.map(point)
        let labels = clusterPoints(pts)
        var buckets: [Int: [HeldDual]] = [:]
        for (key, lab) in zip(held, labels) {
            buckets[lab, default: []].append(key)
        }
        return buckets.keys.sorted().compactMap { buckets[$0] }
    }

    static func canAccept(_ held: [HeldDual], incoming: HeldDual) -> Bool {
        if held.contains(incoming) { return true }
        let before = cluster(held).count
        let after = cluster(held + [incoming]).count
        if after <= maxFingers { return true }
        return after <= before
    }

    private static func clusterPoints(_ points: [(Double, Double)]) -> [Int] {
        let n = points.count
        var labels = Array(repeating: -1, count: n)
        func dist(_ a: (Double, Double), _ b: (Double, Double)) -> Double {
            hypot(a.0 - b.0, a.1 - b.1)
        }
        func neighbors(_ i: Int) -> [Int] {
            (0..<n).filter { dist(points[i], points[$0]) <= clusterEps }
        }
        var cid = 0
        for i in 0..<n where labels[i] == -1 {
            labels[i] = cid
            var seed = neighbors(i)
            var s = 0
            while s < seed.count {
                let j = seed[s]
                s += 1
                if labels[j] == -1 {
                    labels[j] = cid
                    for k in neighbors(j) where !seed.contains(k) { seed.append(k) }
                }
            }
            cid += 1
        }
        return labels
    }

    private static func k(
        _ kid: String, _ row: Double, _ col: Double, _ w: Double = 1,
        kind: String = "char", base: String = "", shift: String = "",
        altgr: String = "", dead: String = "", shiftDead: String = "", h: Double = 1
    ) -> DualKey {
        DualKey(
            kid: kid, row: row, col: col, w: w, h: h, kind: kind,
            base: base, shift: shift, altgr: altgr, dead: dead, shiftDead: shiftDead, code: kid
        )
    }

    private static func makeUS() -> DualLayout {
        DualLayout(id: "us", name: "US", nameFr: "É.-U.", x0: 0, keys: [
            k("Backquote", 0, 0, base: "`", shift: "~"),
            k("Digit1", 0, 1, base: "1", shift: "!"), k("Digit2", 0, 2, base: "2", shift: "@"),
            k("Digit3", 0, 3, base: "3", shift: "#"), k("Digit4", 0, 4, base: "4", shift: "$"),
            k("Digit5", 0, 5, base: "5", shift: "%"), k("Digit6", 0, 6, base: "6", shift: "^"),
            k("Digit7", 0, 7, base: "7", shift: "&"), k("Digit8", 0, 8, base: "8", shift: "*"),
            k("Digit9", 0, 9, base: "9", shift: "("), k("Digit0", 0, 10, base: "0", shift: ")"),
            k("Minus", 0, 11, base: "-", shift: "_"), k("Equal", 0, 12, base: "=", shift: "+"),
            k("Backspace", 0, 13, 2, kind: "backspace", base: "⌫"),
            k("Tab", 1, 0, 1.5, kind: "tab", base: "⇥"),
            k("KeyQ", 1, 1.5, base: "q", shift: "Q"), k("KeyW", 1, 2.5, base: "w", shift: "W"),
            k("KeyE", 1, 3.5, base: "e", shift: "E"), k("KeyR", 1, 4.5, base: "r", shift: "R"),
            k("KeyT", 1, 5.5, base: "t", shift: "T"), k("KeyY", 1, 6.5, base: "y", shift: "Y"),
            k("KeyU", 1, 7.5, base: "u", shift: "U"), k("KeyI", 1, 8.5, base: "i", shift: "I"),
            k("KeyO", 1, 9.5, base: "o", shift: "O"), k("KeyP", 1, 10.5, base: "p", shift: "P"),
            k("BracketLeft", 1, 11.5, base: "[", shift: "{"), k("BracketRight", 1, 12.5, base: "]", shift: "}"),
            k("Backslash", 1, 13.5, 1.5, base: "\\", shift: "|"),
            k("CapsLock", 2, 0, 1.75, kind: "caps", base: "⇪"),
            k("KeyA", 2, 1.75, base: "a", shift: "A"), k("KeyS", 2, 2.75, base: "s", shift: "S"),
            k("KeyD", 2, 3.75, base: "d", shift: "D"), k("KeyF", 2, 4.75, base: "f", shift: "F"),
            k("KeyG", 2, 5.75, base: "g", shift: "G"), k("KeyH", 2, 6.75, base: "h", shift: "H"),
            k("KeyJ", 2, 7.75, base: "j", shift: "J"), k("KeyK", 2, 8.75, base: "k", shift: "K"),
            k("KeyL", 2, 9.75, base: "l", shift: "L"),
            k("Semicolon", 2, 10.75, base: ";", shift: ":"), k("Quote", 2, 11.75, base: "'", shift: "\""),
            k("Enter", 2, 12.75, 2.25, kind: "enter", base: "⏎"),
            k("ShiftLeft", 3, 0, 2.25, kind: "shift", base: "⇧"),
            k("KeyZ", 3, 2.25, base: "z", shift: "Z"), k("KeyX", 3, 3.25, base: "x", shift: "X"),
            k("KeyC", 3, 4.25, base: "c", shift: "C"), k("KeyV", 3, 5.25, base: "v", shift: "V"),
            k("KeyB", 3, 6.25, base: "b", shift: "B"), k("KeyN", 3, 7.25, base: "n", shift: "N"),
            k("KeyM", 3, 8.25, base: "m", shift: "M"),
            k("Comma", 3, 9.25, base: ",", shift: "<"), k("Period", 3, 10.25, base: ".", shift: ">"),
            k("Slash", 3, 11.25, base: "/", shift: "?"),
            k("ShiftRight", 3, 12.25, 2.75, kind: "shift", base: "⇧"),
            k("ControlLeft", 4, 0, 1.5, kind: "ctrl", base: "ctrl"),
            k("AltLeft", 4, 1.5, 1.5, kind: "alt", base: "alt"),
            k("Space", 4, 3, 9, kind: "space", base: " "),
            k("AltRight", 4, 12, 1.5, kind: "alt", base: "alt"),
            k("ControlRight", 4, 13.5, 1.5, kind: "ctrl", base: "ctrl")
        ])
    }

    private static func makeCSA() -> DualLayout {
        DualLayout(id: "csa", name: "Canadian French", nameFr: "Canadien français", x0: boardGap, keys: [
            k("Backquote", 0, 0, base: "/", shift: "\\", altgr: "|"),
            k("Digit1", 0, 1, base: "1", shift: "!"), k("Digit2", 0, 2, base: "2", shift: "@"),
            k("Digit3", 0, 3, base: "3", shift: "#"), k("Digit4", 0, 4, base: "4", shift: "$"),
            k("Digit5", 0, 5, base: "5", shift: "%"), k("Digit6", 0, 6, base: "6", shift: "?"),
            k("Digit7", 0, 7, base: "7", shift: "&", altgr: "{"), k("Digit8", 0, 8, base: "8", shift: "*", altgr: "}"),
            k("Digit9", 0, 9, base: "9", shift: "(", altgr: "["), k("Digit0", 0, 10, base: "0", shift: ")", altgr: "]"),
            k("Minus", 0, 11, base: "-", shift: "_"), k("Equal", 0, 12, base: "=", shift: "+"),
            k("Backspace", 0, 13, 2, kind: "backspace", base: "⌫"),
            k("Tab", 1, 0, 1.5, kind: "tab", base: "⇥"),
            k("KeyQ", 1, 1.5, base: "q", shift: "Q"), k("KeyW", 1, 2.5, base: "w", shift: "W"),
            k("KeyE", 1, 3.5, base: "e", shift: "E", altgr: "€"), k("KeyR", 1, 4.5, base: "r", shift: "R"),
            k("KeyT", 1, 5.5, base: "t", shift: "T"), k("KeyY", 1, 6.5, base: "y", shift: "Y"),
            k("KeyU", 1, 7.5, base: "u", shift: "U"), k("KeyI", 1, 8.5, base: "i", shift: "I"),
            k("KeyO", 1, 9.5, base: "o", shift: "O"), k("KeyP", 1, 10.5, base: "p", shift: "P"),
            k("BracketLeft", 1, 11.5, base: "^", shift: "¨", dead: "circ", shiftDead: "uml"),
            k("BracketRight", 1, 12.5, base: "¸", shift: "ˇ", dead: "cedilla"),
            k("Enter", 1, 13.5, 1.5, kind: "enter", base: "⏎", h: 2),
            k("CapsLock", 2, 0, 1.75, kind: "caps", base: "⇪"),
            k("KeyA", 2, 1.75, base: "a", shift: "A"), k("KeyS", 2, 2.75, base: "s", shift: "S"),
            k("KeyD", 2, 3.75, base: "d", shift: "D"), k("KeyF", 2, 4.75, base: "f", shift: "F"),
            k("KeyG", 2, 5.75, base: "g", shift: "G"), k("KeyH", 2, 6.75, base: "h", shift: "H"),
            k("KeyJ", 2, 7.75, base: "j", shift: "J"), k("KeyK", 2, 8.75, base: "k", shift: "K"),
            k("KeyL", 2, 9.75, base: "l", shift: "L"),
            k("Semicolon", 2, 10.75, base: ";", shift: ":"), k("Quote", 2, 11.75, base: "è", shift: "È"),
            k("Backslash", 2, 12.75, 0.75, base: "à", shift: "À"),
            k("ShiftLeft", 3, 0, 1.25, kind: "shift", base: "⇧"),
            k("IntlBackslash", 3, 1.25, base: "ù", shift: "Ù"),
            k("KeyZ", 3, 2.25, base: "z", shift: "Z"), k("KeyX", 3, 3.25, base: "x", shift: "X"),
            k("KeyC", 3, 4.25, base: "c", shift: "C"), k("KeyV", 3, 5.25, base: "v", shift: "V"),
            k("KeyB", 3, 6.25, base: "b", shift: "B"), k("KeyN", 3, 7.25, base: "n", shift: "N"),
            k("KeyM", 3, 8.25, base: "m", shift: "M"),
            k("Comma", 3, 9.25, base: ",", shift: "'"), k("Period", 3, 10.25, base: ".", shift: "."),
            k("Slash", 3, 11.25, base: "é", shift: "É"),
            k("ShiftRight", 3, 12.25, 2.75, kind: "shift", base: "⇧"),
            k("ControlLeft", 4, 0, 1.5, kind: "ctrl", base: "ctrl"),
            k("AltLeft", 4, 1.5, 1.5, kind: "alt", base: "alt"),
            k("Space", 4, 3, 7.5, kind: "space", base: " "),
            k("AltRight", 4, 10.5, 2.25, kind: "altgr", base: "alt gr"),
            k("ControlRight", 4, 12.75, 2.25, kind: "ctrl", base: "ctrl")
        ])
    }
}

final class DualTypeState {
    var shift = false
    var caps = false
    var altgr = false
    var dead = ""
    var text = ""

    private let deadMap: [String: [String: String]] = [
        "circ": ["a": "â", "e": "ê", "i": "î", "o": "ô", "u": "û", "A": "Â", "E": "Ê", "I": "Î", "O": "Ô", "U": "Û"],
        "uml": ["a": "ä", "e": "ë", "i": "ï", "o": "ö", "u": "ü", "A": "Ä", "E": "Ë", "I": "Ï", "O": "Ö", "U": "Ü"],
        "cedilla": ["c": "ç", "C": "Ç"]
    ]

    func apply(_ key: DualKey) -> String {
        switch key.kind {
        case "shift": shift = true; return ""
        case "caps": caps.toggle(); return ""
        case "altgr": altgr = true; return ""
        case "backspace":
            if !dead.isEmpty { dead = ""; return "" }
            if !text.isEmpty { text.removeLast() }
            return ""
        case "enter": text += "\n"; return "\n"
        case "tab": text += "\t"; return "\t"
        case "space": text += " "; return " "
        default: break
        }
        let deadId = shift ? key.shiftDead : key.dead
        if !deadId.isEmpty && !altgr {
            dead = deadId
            return ""
        }
        var ch = glyph(key)
        if !dead.isEmpty {
            if let combo = deadMap[dead]?[ch] { ch = combo }
            dead = ""
        }
        text += ch
        return ch
    }

    func release(_ key: DualKey) {
        if key.kind == "shift" { shift = false }
        if key.kind == "altgr" { altgr = false }
    }

    private func glyph(_ key: DualKey) -> String {
        if key.kind == "space" { return " " }
        if key.kind != "char" { return "" }
        if altgr && !key.altgr.isEmpty { return key.altgr }
        let upper = shift != (caps && key.base.rangeOfCharacter(from: .letters) != nil)
        return upper ? (key.shift.isEmpty ? key.base.uppercased() : key.shift) : key.base
    }
}

final class FingerGate {
    var pointers: [Int: HeldDual] = [:]
    var extras: [HeldDual] = []

    var held: [HeldDual] { Array(pointers.values) + extras }
    var clusters: [[HeldDual]] { DualBoards.cluster(held) }

    func down(pointer: Int, key: HeldDual) -> Bool {
        if pointers[pointer] != nil {
            pointers[pointer] = key
            return true
        }
        if pointers.count < maxFingers {
            pointers[pointer] = key
            return true
        }
        if DualBoards.canAccept(held, incoming: key) {
            extras.append(key)
            return true
        }
        return false
    }

    func up(pointer: Int) {
        pointers.removeValue(forKey: pointer)
        extras = extras.filter { held.contains($0) }
    }
}
