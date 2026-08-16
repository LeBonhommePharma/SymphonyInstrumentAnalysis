import SwiftUI
import Foundation

/// One log-Hz / dBFS plot. Every live source is a crayon tick on the same axes as the FFT.
/// X: A0 (27.5 Hz) → C8 (~4186 Hz), log2. Y: −90…0 dBFS.
struct SpectrumPlotView: View {
    var scene: SceneStyle
    var bus: SpectrumBus
    var paused = false

    var body: some View {
        TimelineView(.animation(paused: paused)) { _ in
            Canvas { ctx, size in
                SpectrumPlot.draw(ctx, size, scene: scene, snapshot: bus.snapshot())
            }
        }
        .background(scene.specBed)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        .accessibilityLabel("Spectrum, regrouped sources, log hertz A0 to C8, dB full scale")
    }
}

enum SpectrumPlot {
    static let fLo = 27.5
    static let fHi = 440.0 * pow(2.0, 39.0 / 12.0)
    static let dbLo = -90.0
    static let dbHi = 0.0
    static let hzTicks: [(String, Double)] = [
        ("27.5", 27.5), ("55", 55), ("110", 110), ("220", 220),
        ("440", 440), ("880", 880), ("1.76k", 1760), ("3.5k", 3520)
    ]
    static let dbTicks: [Double] = [-90, -60, -30, 0]

    static func xOf(_ f: Double, plot: CGRect) -> CGFloat {
        let t = (log2(max(f, fLo)) - log2(fLo)) / (log2(fHi) - log2(fLo))
        return plot.minX + CGFloat(min(1, max(0, t))) * plot.width
    }

    static func yOfDb(_ db: Double, plot: CGRect) -> CGFloat {
        let t = (db - dbLo) / (dbHi - dbLo)
        return plot.maxY - CGFloat(min(1, max(0, t))) * plot.height
    }

    static func draw(_ ctx: GraphicsContext, _ size: CGSize, scene: SceneStyle, snapshot: SpectrumSnapshot) {
        let padL: CGFloat = 36
        let padR: CGFloat = 10
        let padT: CGFloat = 22
        let padB: CGFloat = 28
        let plot = CGRect(
            x: padL,
            y: padT,
            width: max(8, size.width - padL - padR),
            height: max(8, size.height - padT - padB)
        )

        ctx.fill(Path(roundedRect: CGRect(origin: .zero, size: size), cornerRadius: 10), with: .color(scene.specBed))

        let grid = Color.white.opacity(scene == .stealth ? 0.10 : 0.22)
        let ink = Color.white.opacity(0.82)
        let faint = Color.white.opacity(0.42)

        for db in dbTicks {
            let y = yOfDb(db, plot: plot)
            var line = Path()
            line.move(to: CGPoint(x: plot.minX, y: y))
            line.addLine(to: CGPoint(x: plot.maxX, y: y))
            ctx.stroke(line, with: .color(grid), lineWidth: db == 0 ? 1 : 0.5)
            let label = Text("\(Int(db))")
                .font(.system(size: 8, weight: .semibold, design: .monospaced))
                .foregroundColor(faint)
            ctx.draw(label, at: CGPoint(x: padL - 4, y: y), anchor: .trailing)
        }

        for (name, hz) in hzTicks {
            let x = xOf(hz, plot: plot)
            var line = Path()
            line.move(to: CGPoint(x: x, y: plot.minY))
            line.addLine(to: CGPoint(x: x, y: plot.maxY))
            let mark = abs(hz - 440) < 0.5
            ctx.stroke(line, with: .color(mark ? Color.white.opacity(0.45) : grid), lineWidth: mark ? 1.2 : 0.5)
            let label = Text(name)
                .font(.system(size: mark ? 9 : 8, weight: .semibold, design: .monospaced))
                .foregroundColor(mark ? ink : faint)
            ctx.draw(label, at: CGPoint(x: x, y: size.height - 10), anchor: .center)
        }

        ctx.draw(
            Text("Hz").font(.system(size: 8, weight: .semibold)).foregroundColor(faint),
            at: CGPoint(x: size.width - 8, y: size.height - 10),
            anchor: .trailing
        )
        ctx.draw(
            Text("dBFS").font(.system(size: 8, weight: .semibold)).foregroundColor(faint),
            at: CGPoint(x: 18, y: 11),
            anchor: .center
        )

        let bins = snapshot.db
        let binHz = snapshot.binHz
        if bins.count > 8, binHz > 0 {
            let i0 = max(1, Int((fLo / binHz).rounded(.down)))
            let i1 = min(bins.count - 1, Int((fHi / binHz).rounded(.up)))
            if i1 > i0 {
                var path = Path()
                var line = Path()
                path.move(to: CGPoint(x: xOf(Double(i0) * binHz, plot: plot), y: plot.maxY))
                var started = false
                for i in i0...i1 {
                    let f = Double(i) * binHz
                    let x = xOf(f, plot: plot)
                    let y = yOfDb(Double(bins[i]), plot: plot)
                    path.addLine(to: CGPoint(x: x, y: y))
                    if !started {
                        line.move(to: CGPoint(x: x, y: y))
                        started = true
                    } else {
                        line.addLine(to: CGPoint(x: x, y: y))
                    }
                }
                path.addLine(to: CGPoint(x: xOf(Double(i1) * binHz, plot: plot), y: plot.maxY))
                path.closeSubpath()
                let fill = Color(red: 0.18, green: 0.83, blue: 0.75).opacity(scene == .stealth ? 0.22 : 0.34)
                let stroke = Color(red: 0.18, green: 0.83, blue: 0.75).opacity(scene == .stealth ? 0.55 : 0.85)
                ctx.fill(path, with: .color(fill))
                ctx.stroke(line, with: .color(stroke), lineWidth: 1.1)
            }
        }

        for mark in snapshot.marks {
            let x = xOf(mark.f, plot: plot)
            let y = yOfDb(Double(mark.db), plot: plot)
            let r: CGFloat = mark.kind == .held ? 4 : (mark.kind == .cluster ? 5.5 : 3.5)
            let dot = Path(ellipseIn: CGRect(x: x - r, y: y - r, width: r * 2, height: r * 2))
            ctx.fill(dot, with: .color(mark.name.color.opacity(mark.kind == .held ? 0.7 : 1)))
            ctx.stroke(dot, with: .color(.white.opacity(0.55)), lineWidth: 0.8)
            if mark.kind != .peak {
                let lab = Text(mark.name.french)
                    .font(.system(size: 8, weight: .semibold))
                    .foregroundColor(.white)
                ctx.draw(lab, at: CGPoint(x: x, y: max(plot.minY + 7, y - 12)), anchor: .center)
            }
        }

        let n = snapshot.marks.filter { $0.kind == .cluster }.count
        if n > 0 {
            ctx.draw(
                Text("\(n)").font(.system(size: 10, weight: .semibold, design: .monospaced)).foregroundColor(ink),
                at: CGPoint(x: plot.maxX - 6, y: plot.minY + 8),
                anchor: .trailing
            )
        }
    }
}

enum SpecMarkKind {
    case cluster
    case held
    case peak
}

struct SpecMark {
    var f: Double
    var db: Float
    var name: NoteName
    var kind: SpecMarkKind
}

struct SpectrumSnapshot {
    var db: [Float]
    var binHz: Double
    var marks: [SpecMark]
}

/// Lock-free-enough snapshot bus. Not @Published — SpectrumPlotView polls on the display clock.
final class SpectrumBus {
    private let lock = NSLock()
    private var db: [Float] = []
    private var binHz: Double = 0
    private var marks: [SpecMark] = []

    func update(db: [Float], binHz: Double, marks: [SpecMark]) {
        lock.lock()
        self.db = db
        self.binHz = binHz
        self.marks = marks
        lock.unlock()
    }

    func clear() {
        update(db: [], binHz: 0, marks: [])
    }

    func snapshot() -> SpectrumSnapshot {
        lock.lock()
        let snap = SpectrumSnapshot(db: db, binHz: binHz, marks: marks)
        lock.unlock()
        return snap
    }
}
