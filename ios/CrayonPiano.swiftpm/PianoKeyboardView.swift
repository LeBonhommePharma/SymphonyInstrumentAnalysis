import SwiftUI
import UIKit

struct PianoKeyboardView: UIViewRepresentable {
    var lit: [LitNote]
    var harmonics: Set<Int>
    var pressed: Set<Int>
    var binds: [Int: String]
    var scene: SceneStyle
    var onPressed: (Set<Int>) -> Void

    func makeUIView(context: Context) -> PianoScrollView {
        let view = PianoScrollView()
        view.board.onPressed = onPressed
        view.board.apply(lit: lit, harmonics: harmonics, pressed: pressed, binds: binds, scene: scene)
        return view
    }

    func updateUIView(_ uiView: PianoScrollView, context: Context) {
        uiView.board.onPressed = onPressed
        uiView.board.apply(lit: lit, harmonics: harmonics, pressed: pressed, binds: binds, scene: scene)
    }
}

final class PianoScrollView: UIScrollView {
    let board = PianoBoardView()
    private var didCenter = false

    override init(frame: CGRect) {
        super.init(frame: frame)
        showsVerticalScrollIndicator = false
        showsHorizontalScrollIndicator = true
        alwaysBounceHorizontal = true
        delaysContentTouches = false
        canCancelContentTouches = true
        addSubview(board)
        accessibilityLabel = "Piano 88 touches, La0 à Do8 / A0 to C8"
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        addSubview(board)
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        let whites = CGFloat(max(1, PitchMath.whiteKeyCount()))
        let minWhite: CGFloat = 28
        let width = max(bounds.width, whites * minWhite)
        board.frame = CGRect(x: 0, y: 0, width: width, height: bounds.height)
        contentSize = board.frame.size
        if !didCenter, width > bounds.width + 1 {
            didCenter = true
            // Middle C (Do4, MIDI 60) sits near the visual center of an 88-key piano.
            let midC = CGFloat(60 - PitchMath.midiLo) / CGFloat(max(1, PitchMath.midiHi - PitchMath.midiLo))
            let x = midC * width - bounds.width / 2
            contentOffset = CGPoint(x: max(0, min(width - bounds.width, x)), y: 0)
        }
    }
}

final class PianoBoardView: UIView {
    var onPressed: ((Set<Int>) -> Void)?

    private var litVel: [Int: CGFloat] = [:]
    private var harmonics: Set<Int> = []
    private var pressed: Set<Int> = []
    private var binds: [Int: String] = [:]
    private var scene: SceneStyle = .stealth
    private var whiteFrames: [(midi: Int, frame: CGRect)] = []
    private var blackFrames: [(midi: Int, frame: CGRect)] = []
    private var touchMidi: [UITouch: Int] = [:]

    override init(frame: CGRect) {
        super.init(frame: frame)
        isMultipleTouchEnabled = true
        backgroundColor = .clear
        isOpaque = false
        accessibilityLabel = "Piano 88 touches, La0 à Do8 / A0 to C8"
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        isMultipleTouchEnabled = true
    }

    func apply(lit: [LitNote], harmonics: Set<Int>, pressed: Set<Int>, binds: [Int: String], scene: SceneStyle) {
        var vel: [Int: CGFloat] = [:]
        let maxDb = lit.map(\.db).max() ?? -60
        for note in lit {
            let span = max(6, maxDb + 48)
            vel[note.midi] = CGFloat(max(0.22, min(1, (note.db + 48) / span)))
        }
        litVel = vel
        self.harmonics = harmonics
        self.pressed = pressed
        self.binds = binds
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
        let needed = Set(litVel.keys)
        let state = KeyboardLayout.highlight(midi: midi, needed: needed, pressed: pressed)
        let harm = state == .idle && harmonics.contains(midi)
        let idle = isBlack ? scene.blackKey : scene.whiteKey
        let fill: UIColor
        switch state {
        case .hit:
            fill = name.uiColor
        case .need:
            fill = name.uiColor
        case .held:
            fill = (isBlack ? UIColor.white : UIColor(scene.ink)).withAlphaComponent(0.22).blended(with: idle) ?? idle
        case .idle:
            if harm {
                fill = name.uiColor.withAlphaComponent(isBlack ? 0.35 : 0.18).blended(with: idle) ?? idle
            } else {
                fill = idle
            }
        }
        ctx.setFillColor(fill.cgColor)
        let path = UIBezierPath(roundedRect: frame.insetBy(dx: 0.4, dy: 0), cornerRadius: isBlack ? 3 : 5)
        ctx.addPath(path.cgPath)
        ctx.fillPath()
        if state == .held {
            ctx.setStrokeColor(UIColor(scene.ink).withAlphaComponent(0.85).cgColor)
            ctx.setLineWidth(2)
        } else if state == .hit {
            ctx.setStrokeColor(UIColor(red: 0.72, green: 1.0, blue: 0.38, alpha: 1).cgColor)
            ctx.setLineWidth(3)
        } else if state == .need {
            ctx.setStrokeColor(name.uiColor.withAlphaComponent(0.95).cgColor)
            ctx.setLineWidth(1.5)
            ctx.setLineDash(phase: 0, lengths: [3, 2])
        } else {
            ctx.setStrokeColor((isBlack ? UIColor.black : UIColor.white).withAlphaComponent(0.12).cgColor)
            ctx.setLineWidth(1)
        }
        ctx.addPath(path.cgPath)
        ctx.strokePath()
        ctx.setLineDash(phase: 0, lengths: [])

        let on = state == .need || state == .hit
        let label: String
        if on || state == .held {
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
        if let bind = binds[midi], !bind.isEmpty {
            let bindColor: UIColor = on ? UIColor(name.labelColor) : (isBlack ? UIColor.white.withAlphaComponent(0.4) : UIColor(scene.muted))
            let bindFont = UIFont.monospacedSystemFont(ofSize: isBlack ? 7 : 8, weight: .bold)
            let bindAttrs: [NSAttributedString.Key: Any] = [
                .font: bindFont,
                .foregroundColor: bindColor
            ]
            let bindSize = (bind as NSString).size(withAttributes: bindAttrs)
            (bind as NSString).draw(
                at: CGPoint(x: frame.midX - bindSize.width / 2, y: frame.minY + (isBlack ? 3 : 5)),
                withAttributes: bindAttrs
            )
        }
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
