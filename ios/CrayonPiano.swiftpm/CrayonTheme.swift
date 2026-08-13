import SwiftUI
import UIKit

enum NoteName: String, CaseIterable, Hashable {
    case c = "C"
    case cSharp = "C#"
    case d = "D"
    case dSharp = "D#"
    case e = "E"
    case f = "F"
    case fSharp = "F#"
    case g = "G"
    case gSharp = "G#"
    case a = "A"
    case aSharp = "A#"
    case b = "B"

    var french: String {
        switch self {
        case .c: return "Do"
        case .cSharp: return "Do♯"
        case .d: return "Ré"
        case .dSharp: return "Ré♯"
        case .e: return "Mi"
        case .f: return "Fa"
        case .fSharp: return "Fa♯"
        case .g: return "Sol"
        case .gSharp: return "Sol♯"
        case .a: return "La"
        case .aSharp: return "La♯"
        case .b: return "Si"
        }
    }

    var pencil: String {
        switch self {
        case .c: return "Maraschino"
        case .cSharp: return "Cayenne"
        case .d: return "Tangerine"
        case .dSharp: return "Lemon"
        case .e: return "Lime"
        case .f: return "Spring"
        case .fSharp: return "Fern"
        case .g: return "Spindrift"
        case .gSharp: return "Sky"
        case .a: return "Blueberry"
        case .aSharp: return "Grape"
        case .b: return "Magenta"
        }
    }

    /// Canonical macOS Crayons.clr RGB (0...255).
    var rgb: (Int, Int, Int) {
        switch self {
        case .c: return (251, 2, 7)
        case .cSharp: return (128, 0, 2)
        case .d: return (253, 128, 8)
        case .dSharp: return (255, 255, 10)
        case .e: return (128, 255, 8)
        case .f: return (33, 255, 6)
        case .fSharp: return (64, 128, 2)
        case .g: return (102, 255, 204)
        case .gSharp: return (102, 204, 255)
        case .a: return (0, 0, 255)
        case .aSharp: return (128, 0, 255)
        case .b: return (251, 2, 255)
        }
    }

    var uiColor: UIColor {
        let c = rgb
        return UIColor(
            red: CGFloat(c.0) / 255,
            green: CGFloat(c.1) / 255,
            blue: CGFloat(c.2) / 255,
            alpha: 1
        )
    }

    var color: Color { Color(uiColor) }

    var labelColor: Color {
        let c = rgb
        let lum = (0.2126 * Double(c.0) + 0.7152 * Double(c.1) + 0.0722 * Double(c.2)) / 255
        return lum < 0.48 ? Color(red: 0.957, green: 0.937, blue: 0.902) : Color(red: 0.227, green: 0.204, blue: 0.180)
    }

    var hz: Double {
        switch self {
        case .c: return 261.63
        case .cSharp: return 277.18
        case .d: return 293.66
        case .dSharp: return 311.13
        case .e: return 329.63
        case .f: return 349.23
        case .fSharp: return 369.99
        case .g: return 392.00
        case .gSharp: return 415.30
        case .a: return 440.00
        case .aSharp: return 466.16
        case .b: return 493.88
        }
    }

    static func pitchClass(of midi: Int) -> NoteName {
        let names = NoteName.allCases
        return names[((midi % 12) + 12) % 12]
    }
}

enum SceneStyle {
    case stealth
    case studio

    var background: Color {
        switch self {
        case .stealth: return Color(red: 0.071, green: 0.071, blue: 0.078)
        case .studio: return Color(red: 0.937, green: 0.910, blue: 0.863)
        }
    }

    var ink: Color {
        switch self {
        case .stealth: return Color(red: 0.604, green: 0.604, blue: 0.635)
        case .studio: return Color(red: 0.227, green: 0.204, blue: 0.180)
        }
    }

    var muted: Color {
        switch self {
        case .stealth: return Color(red: 0.431, green: 0.431, blue: 0.463)
        case .studio: return Color(red: 0.431, green: 0.404, blue: 0.369)
        }
    }

    var paper: Color {
        switch self {
        case .stealth: return Color(red: 0.094, green: 0.094, blue: 0.110)
        case .studio: return Color(red: 0.969, green: 0.945, blue: 0.910)
        }
    }

    var whiteKey: UIColor {
        switch self {
        case .stealth: return UIColor(red: 0.165, green: 0.165, blue: 0.180, alpha: 1)
        case .studio: return UIColor(red: 0.957, green: 0.937, blue: 0.902, alpha: 1)
        }
    }

    var blackKey: UIColor {
        switch self {
        case .stealth: return UIColor(red: 0.102, green: 0.102, blue: 0.110, alpha: 1)
        case .studio: return UIColor(red: 0.247, green: 0.227, blue: 0.204, alpha: 1)
        }
    }

    var statusBarStyle: UIStatusBarStyle {
        switch self {
        case .stealth: return .lightContent
        case .studio: return .darkContent
        }
    }
}
