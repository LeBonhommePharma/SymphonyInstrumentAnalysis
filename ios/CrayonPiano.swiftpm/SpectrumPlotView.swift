import SwiftUI

/// Log-frequency clustered spectrum. Piano range A0–C8, not a linear 0–6 kHz crop.
struct SpectrumPlotView: View {
    @ObservedObject var session: PianoSession

    private let fLo = 27.5
    private let fHi = 4186.0

    var body: some View {
        Canvas { ctx, size in
            draw(ctx, size)
        }
        .background(session.scene.specBed)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        .accessibilityLabel("Spectrum, clustered sources, piano range A0 to C8")
    }

    private func xOf(_ f: Double, plot: CGRect) -> CGFloat {
        let t = (log2(max(f, fLo)) - log2(fLo)) / (log2(fHi) - log2(fLo))
        return plot.minX + CGFloat(min(1, max(0, t))) * plot.width
    }

    private func yOfDb(_ db: Double, plot: CGRect) -> CGFloat {
        let t = (db + 90) / 90
        return plot.maxY - CGFloat(min(1, max(0, t))) * plot.height
    }

    private func draw(_ ctx: GraphicsContext, _ size: CGSize) {
        let padL: CGFloat = 42
        let padR: CGFloat = 16
        let padT: CGFloat = 28
        let padB: CGFloat = 32
        let plot = CGRect(x: padL, y: padT, width: max(8, size.width - padL - padR), height: max(8, size.height - padT - padB))

        var bed = Path(roundedRect: CGRect(origin: .zero, size: size), cornerRadius: 10)
        ctx.fill(bed, with: .color(session.scene.specBed))

        let grid = session.scene.muted.opacity(0.35)
        let ink = Color.white.opacity(0.78)
        let faint = Color.white.opacity(0.38)

        for db in stride(from: -80.0, through: 0, by: 20) {
            let y = yOfDb(db, plot: plot)
            var line = Path()
            line.move(to: CGPoint(x: plot.minX, y: y))
            line.addLine(to: CGPoint(x: plot.maxX, y: y))
            ctx.stroke(line, with: .color(grid), lineWidth: 0.5)
            let label = Text("\(Int(db))")
                .font(.system(size: 8, weight: .semibold, design: .monospaced))
                .foregroundColor(faint)
            ctx.draw(label, at: CGPoint(x: padL - 4, y: y), anchor: .trailing)
        }

        let octaves: [(String, Double)] = [
            ("A0", 27.5), ("A1", 55), ("A2", 110), ("A3", 220),
            ("C4", 261.63), ("A4", 440), ("A5", 880), ("A6", 1760), ("C8", 4186)
        ]
        for (name, hz) in octaves {
            let x = xOf(hz, plot: plot)
            var line = Path()
            line.move(to: CGPoint(x: x, y: plot.minY))
            line.addLine(to: CGPoint(x: x, y: plot.maxY))
            let mark = name == "A4" || name == "C4"
            ctx.stroke(line, with: .color(grid), lineWidth: mark ? 1.1 : 0.5)
            let label = Text(name)
                .font(.system(size: 8, weight: .semibold, design: .monospaced))
                .foregroundColor(mark ? ink : faint)
            ctx.draw(label, at: CGPoint(x: x, y: size.height - 10), anchor: .center)
        }

        let axis = Text("Hz")
            .font(.system(size: 8, weight: .semibold))
            .foregroundColor(faint)
        ctx.draw(axis, at: CGPoint(x: size.width - 10, y: size.height - 10), anchor: .trailing)
        let dbLab = Text("dB")
            .font(.system(size: 8, weight: .semibold))
            .foregroundColor(faint)
        ctx.draw(dbLab, at: CGPoint(x: 14, y: 12), anchor: .center)

        let bins = session.specDb
        let binHz = session.specBinHz
        if bins.count > 8, binHz > 0 {
            var path = Path()
            var line = Path()
            var started = false
            var peakAll: Float = -120
            let steps = min(160, bins.count)
            for i in 0..<steps {
                let t = Double(i) / Double(max(1, steps - 1))
                let f = fLo * pow(2.0, t * (log2(fHi) - log2(fLo)))
                let idx = Int((f / binHz).rounded())
                guard idx >= 0 && idx < bins.count else { continue }
                let lo = max(1, Int((f * 0.97) / binHz))
                let hi = min(bins.count - 1, Int((f * 1.03) / binHz))
                var peak = bins[idx]
                if hi >= lo {
                    for k in lo...hi { peak = max(peak, bins[k]) }
                }
                peakAll = max(peakAll, peak)
                let x = xOf(f, plot: plot)
                let y = yOfDb(Double(peak), plot: plot)
                if !started {
                    path.move(to: CGPoint(x: x, y: plot.maxY))
                    path.addLine(to: CGPoint(x: x, y: y))
                    line.move(to: CGPoint(x: x, y: y))
                    started = true
                } else {
                    path.addLine(to: CGPoint(x: x, y: y))
                    line.addLine(to: CGPoint(x: x, y: y))
                }
            }
            if started, peakAll > -72 {
                path.addLine(to: CGPoint(x: plot.maxX, y: plot.maxY))
                path.closeSubpath()
                ctx.fill(path, with: .color(Color(red: 0.18, green: 0.83, blue: 0.75).opacity(0.38)))
                ctx.stroke(line, with: .color(Color(red: 0.18, green: 0.83, blue: 0.75).opacity(0.85)), lineWidth: 1.2)
            }
        }

        for (i, c) in session.specClusters.prefix(8).enumerated() {
            let x = xOf(c.f0, plot: plot)
            let y = yOfDb(Double(c.db), plot: plot)
            let name = NoteName.pitchClass(of: Int((69 + 12 * log2(c.f0 / 440)).rounded()))
            let r: CGFloat = i == 0 ? 7 : 5
            let dot = Path(ellipseIn: CGRect(x: x - r, y: y - r, width: r * 2, height: r * 2))
            ctx.fill(dot, with: .color(name.color))
            ctx.stroke(dot, with: .color(.white.opacity(0.7)), lineWidth: 1)
            let lab = Text(name.french)
                .font(.system(size: 9, weight: .semibold))
                .foregroundColor(.white)
            ctx.draw(lab, at: CGPoint(x: x, y: max(plot.minY + 8, y - 14)), anchor: .center)
        }
    }
}
