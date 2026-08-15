import SwiftUI
import UIKit

struct DualKeyboardView: View {
    @ObservedObject var session: PianoSession

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 8) {
                Button("⌫") { session.clearTyped() }
                    .buttonStyle(.plain)
                    .frame(width: 44, height: 44)
                    .background(session.scene.paper, in: RoundedRectangle(cornerRadius: 8))
                Text(session.typedText.isEmpty ? "US + canadien français · 10 doigts, plus si bien groupés" : session.typedText)
                    .font(.body.monospaced())
                    .foregroundStyle(session.typedText.isEmpty ? session.scene.muted : session.scene.ink)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(8)
                    .background(session.scene.paper, in: RoundedRectangle(cornerRadius: 8))
            }
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .top, spacing: 10) {
                    board("us")
                    board("csa")
                }
                VStack(spacing: 10) {
                    board("us")
                    board("csa")
                }
            }
        }
    }

    private func board(_ id: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(id == "us" ? "US" : "Canadien français · CSA")
                .font(.caption2.weight(.semibold))
                .foregroundStyle(session.scene.muted)
            DualBoardUIView(session: session, boardId: id)
                .frame(minHeight: 160)
                .frame(maxWidth: .infinity)
        }
        .padding(6)
        .background(session.scene.paper, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
    }
}

struct DualBoardUIView: UIViewRepresentable {
    @ObservedObject var session: PianoSession
    var boardId: String

    func makeUIView(context: Context) -> DualBoardView {
        let view = DualBoardView()
        view.boardId = boardId
        view.session = session
        return view
    }

    func updateUIView(_ uiView: DualBoardView, context: Context) {
        uiView.boardId = boardId
        uiView.session = session
        uiView.setNeedsDisplay()
    }
}

final class DualBoardView: UIView {
    var boardId = "us"
    weak var session: PianoSession?
    private var frames: [(DualKey, CGRect)] = []
    private var touchKey: [UITouch: DualKey] = [:]

    override init(frame: CGRect) {
        super.init(frame: frame)
        isMultipleTouchEnabled = true
        backgroundColor = .clear
        isOpaque = false
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        isMultipleTouchEnabled = true
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        rebuild()
        setNeedsDisplay()
    }

    private func rebuild() {
        let layout = DualBoards.layout(boardId)
        let ku = bounds.width / 15
        let kh = bounds.height / 5
        frames = layout.keys.map { key in
            let r = CGRect(x: key.col * ku, y: key.row * kh, width: key.w * ku, height: key.h * kh).insetBy(dx: 1, dy: 1)
            return (key, r)
        }
    }

    override func draw(_ rect: CGRect) {
        guard let ctx = UIGraphicsGetCurrentContext(), let session else { return }
        let held = Set(session.fingerGate.held.filter { $0.board == boardId }.map(\.kid))
        let groups = session.fingerGate.clusters
        for (key, frame) in frames {
            let on = held.contains(key.kid)
            var fill = session.scene.whiteKey
            if on {
                let idx = groups.firstIndex { $0.contains(HeldDual(board: boardId, kid: key.kid)) } ?? 0
                fill = NoteName.allCases[idx % 12].uiColor
            }
            ctx.setFillColor(fill.cgColor)
            let path = UIBezierPath(roundedRect: frame, cornerRadius: 4)
            ctx.addPath(path.cgPath)
            ctx.fillPath()
            let label = key.kind == "char" || key.kind == "space" ? key.base : key.base
            let attrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: key.w > 1.6 ? 9 : 11, weight: .semibold),
                .foregroundColor: on ? UIColor.white : UIColor(session.scene.ink)
            ]
            let size = (label as NSString).size(withAttributes: attrs)
            (label as NSString).draw(
                at: CGPoint(x: frame.midX - size.width / 2, y: frame.midY - size.height / 2),
                withAttributes: attrs
            )
        }
    }

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        for touch in touches {
            if let key = keyAt(touch.location(in: self)) {
                touchKey[touch] = key
                session?.dualDown(pointer: touch.hash, board: boardId, kid: key.kid)
            }
        }
        setNeedsDisplay()
    }

    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
        for touch in touches {
            if let key = keyAt(touch.location(in: self)) {
                touchKey[touch] = key
                session?.dualDown(pointer: touch.hash, board: boardId, kid: key.kid)
            }
        }
        setNeedsDisplay()
    }

    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent?) {
        for touch in touches {
            session?.dualUp(pointer: touch.hash)
            touchKey.removeValue(forKey: touch)
        }
        setNeedsDisplay()
    }

    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent?) {
        touchesEnded(touches, with: event)
    }

    private func keyAt(_ point: CGPoint) -> DualKey? {
        frames.first { $0.1.contains(point) }?.0
    }
}
