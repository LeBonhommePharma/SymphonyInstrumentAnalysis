import SwiftUI
import UIKit

struct PianoKeyboardView: UIViewRepresentable {
    var lit: [LitNote]
    var harmonics: Set<Int>
    var pressed: Set<Int>
    var scene: SceneStyle
    var onPressed: (Set<Int>) -> Void

    func makeUIView(context: Context) -> PianoBoardView {
        let view = PianoBoardView()
        view.onPressed = onPressed
        view.apply(lit: lit, harmonics: harmonics, pressed: pressed, scene: scene)
        return view
    }

    func updateUIView(_ uiView: PianoBoardView, context: Context) {
        uiView.onPressed = onPressed
        uiView.apply(lit: lit, harmonics: harmonics, pressed: pressed, scene: scene)
    }
}

final class PianoBoardView: UIView {
    var onPressed: ((Set<Int>) -> Void)?

    private var litVel: [Int: CGFloat] = [:]
    private var harmonics: Set<Int> = []
    private var pressed: Set<Int> = []
    private var scene: SceneStyle = .stealth
    private var whiteFrames: [(midi: Int, frame: CGRect)] = []
    private var blackFrames: [(midi: Int, frame: CGRect)] = []
    private var touchMidi: [UITouch: Int] = [:]

    override init(frame: CGRect) {
        super.init(frame: frame)
        isMultipleTouchEnabled = true
        backgroundColor = .clear
        isOpaque = false
        accessibilityLabel = "Piano Do2 à Do7 / C2 to C7"
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        isMultipleTouchEnabled = true
    }

    func apply(lit: [LitNote], harmonics: Set<Int>, pressed: Set<Int>, scene: SceneStyle) {
        var vel: [Int: CGFloat] = [:]
        let maxDb = lit.map(\.db).max() ?? -60
        for note in lit {
            let span = max(6, maxDb + 48)
            vel[note.midi] = CGFloat(max(0.22, min(1, (note.db + 48) / span)))
        }
        litVel = vel
        self.harmonics = harmonics
        self.pressed = pressed
        self.scene = scene
        setNeedsDisplay()
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        rebuildFrames()
        setNeedsDisplay()
    }

    private func rebuildFrames() {
        let midis = Array(PitchMath.midiLo...PitchMath.midiHi)
        let whites = midis.filter { !PitchMath.isBlack($0) }
        let w = bounds.width / CGFloat(max(1, whites.count))
        let h = bounds.height
        whiteFrames = whites.enumerated().map { i, midi in
            (midi, CGRect(x: CGFloat(i) * w, y: 0, width: w, height: h))
        }
        let blackW = w * 0.62
        let blackH = h * 0.62
        blackFrames = []
        for (i, midi) in whites.enumerated() {
            let next = midi + 1
            if next <= PitchMath.midiHi && PitchMath.isBlack(next) {
                let x = CGFloat(i) * w + w - blackW / 2
                blackFrames.append((next, CGRect(x: x, y: 0, width: blackW, height: blackH)))
            }
        }
    }

    override func draw(_ rect: CGRect) {
        guard let ctx = UIGraphicsGetCurrentContext() else { return }
        for (midi, frame) in whiteFrames {
            paint(ctx: ctx, midi: midi, frame: frame, isBlack: false)
        }
        for (midi, frame) in blackFrames {
            paint(ctx: ctx, midi: midi, frame: frame, isBlack: true)
        }
    }

    private func paint(ctx: CGContext, midi: Int, frame: CGRect, isBlack: Bool) {
        let name = NoteName.pitchClass(of: midi)
        let on = litVel[midi] != nil || pressed.contains(midi)
        let harm = !on && harmonics.contains(midi)
        let idle = isBlack ? scene.blackKey : scene.whiteKey
        let fill: UIColor
        if on {
            fill = name.uiColor
        } else if harm {
            fill = name.uiColor.withAlphaComponent(isBlack ? 0.35 : 0.18).blended(with: idle) ?? idle
        } else {
            fill = idle
        }
        ctx.setFillColor(fill.cgColor)
        let path = UIBezierPath(roundedRect: frame.insetBy(dx: 0.4, dy: 0), cornerRadius: isBlack ? 3 : 5)
        ctx.addPath(path.cgPath)
        ctx.fillPath()
        ctx.setStrokeColor((isBlack ? UIColor.black : UIColor.white).withAlphaComponent(0.12).cgColor)
        ctx.addPath(path.cgPath)
        ctx.strokePath()

        let label: String
        if on {
            label = "\(name.french)\(PitchMath.octave(of: midi))"
        } else if isBlack {
            label = "♯"
        } else if midi % 12 == 0 {
            label = "\(name.french)\(PitchMath.octave(of: midi))"
        } else {
            label = name.french
        }
        let color: UIColor = on ? UIColor(name.labelColor) : (isBlack ? UIColor.white.withAlphaComponent(0.45) : UIColor(scene.muted))
        let font = UIFont.systemFont(ofSize: isBlack ? 8 : 9, weight: .semibold)
        let attrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: color
        ]
        let size = (label as NSString).size(withAttributes: attrs)
        let point = CGPoint(
            x: frame.midX - size.width / 2,
            y: frame.maxY - size.height - (isBlack ? 6 : 8)
        )
        (label as NSString).draw(at: point, withAttributes: attrs)
    }

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        for touch in touches {
            if let midi = midiAt(touch.location(in: self)) {
                touchMidi[touch] = midi
            }
        }
        emit()
    }

    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
        for touch in touches {
            touchMidi[touch] = midiAt(touch.location(in: self))
        }
        emit()
    }

    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent?) {
        for touch in touches { touchMidi.removeValue(forKey: touch) }
        emit()
    }

    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent?) {
        for touch in touches { touchMidi.removeValue(forKey: touch) }
        emit()
    }

    private func emit() {
        onPressed?(Set(touchMidi.values.compactMap { $0 }))
    }

    private func midiAt(_ point: CGPoint) -> Int? {
        for (midi, frame) in blackFrames where frame.contains(point) {
            return midi
        }
        for (midi, frame) in whiteFrames where frame.contains(point) {
            return midi
        }
        return nil
    }
}

private extension UIColor {
    func blended(with other: UIColor) -> UIColor? {
        var r1: CGFloat = 0, g1: CGFloat = 0, b1: CGFloat = 0, a1: CGFloat = 0
        var r2: CGFloat = 0, g2: CGFloat = 0, b2: CGFloat = 0, a2: CGFloat = 0
        guard getRed(&r1, green: &g1, blue: &b1, alpha: &a1),
              other.getRed(&r2, green: &g2, blue: &b2, alpha: &a2) else { return nil }
        let a = a1
        return UIColor(
            red: r1 * a + r2 * (1 - a),
            green: g1 * a + g2 * (1 - a),
            blue: b1 * a + b2 * (1 - a),
            alpha: 1
        )
    }
}
