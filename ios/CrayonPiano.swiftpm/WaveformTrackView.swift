import SwiftUI

/// DAW-style scrolling waveform (Logic Pro / GarageBand feel): a fixed playhead
/// with the audio waveform scrolling right→left as the sample plays.
struct WaveformTrackView: View {
    @ObservedObject var session: PianoSession

    private let pxPerSec: Double = 96
    private let playheadFrac: Double = 0.34

    @State private var dragging = false
    @State private var grabX: CGFloat = 0
    @State private var grabT: Double = 0

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30.0, paused: session.mode != .replay && !session.scrubbing)) { _ in
            GeometryReader { geo in
                Canvas { ctx, size in
                    draw(ctx, size, session.currentSampleTime())
                }
                .background(session.scene.paper)
                .overlay(alignment: .topLeading) {
                    if session.wavePeaks.isEmpty {
                        Text("Temps / Time · glisse pour naviguer / drag to scrub")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundStyle(session.scene.muted)
                            .padding(.leading, 8)
                            .padding(.top, 6)
                    }
                }
                .contentShape(Rectangle())
                .gesture(
                    DragGesture(minimumDistance: 0)
                        .onChanged { value in
                            if !dragging {
                                dragging = true
                                grabX = value.startLocation.x
                                grabT = session.currentSampleTime()
                                session.beginScrub()
                            }
                            let dt = Double(value.location.x - grabX) / pxPerSec
                            session.scrub(toTime: grabT - dt)
                        }
                        .onEnded { _ in
                            dragging = false
                            session.endScrub()
                        }
                )
                .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 6, style: .continuous)
                        .stroke(session.scene.muted.opacity(0.35), lineWidth: 1)
                )
            }
        }
        .frame(height: 68)
    }

    private func draw(_ ctx: GraphicsContext, _ size: CGSize, _ t: Double) {
        let w = size.width
        let h = size.height
        let mid = h / 2
        let playheadX = w * playheadFrac
        let dur = session.sampleDuration
        let peaks = session.wavePeaks
        let pps = session.peaksPerSec

        let grid = session.scene.muted
        let ink = session.scene.ink
        let played = Color(red: 0.28, green: 0.49, blue: 0.60)
        let future = session.scene.muted

        // Scrolling second gridlines + tick labels.
        let firstSec = Int(floor(t - Double(playheadX) / pxPerSec))
        let lastSec = Int(ceil(t + Double(w - playheadX) / pxPerSec))
        if firstSec <= lastSec {
            for s in firstSec...lastSec {
                if s < 0 || (dur > 0 && Double(s) > dur) { continue }
                let x = playheadX + CGFloat((Double(s) - t) * pxPerSec)
                if x < 0 || x > w { continue }
                var line = Path()
                line.move(to: CGPoint(x: x, y: 12))
                line.addLine(to: CGPoint(x: x, y: h))
                ctx.stroke(line, with: .color(grid.opacity(0.28)), lineWidth: 1)
                ctx.draw(
                    Text("\(s)s").font(.system(size: 9)).foregroundColor(grid.opacity(0.7)),
                    at: CGPoint(x: x + 11, y: 7),
                    anchor: .center
                )
            }
        }

        // Center baseline.
        var base = Path()
        base.move(to: CGPoint(x: 0, y: mid))
        base.addLine(to: CGPoint(x: w, y: mid))
        ctx.stroke(base, with: .color(grid.opacity(0.25)), lineWidth: 1)

        // Waveform, one vertical bar per pixel column.
        if !peaks.isEmpty {
            let amp = mid - 3
            var playedPath = Path()
            var futurePath = Path()
            var xi = 0
            let iw = Int(w)
            while xi <= iw {
                let x = CGFloat(xi)
                let tt = t + Double(x - playheadX) / pxPerSec
                if tt >= 0 && tt <= dur {
                    let b = Int(tt * pps)
                    if b >= 0 && b < peaks.count {
                        let a = CGFloat(peaks[b]) * amp
                        if a > 0.5 {
                            if tt <= t {
                                playedPath.move(to: CGPoint(x: x, y: mid - a))
                                playedPath.addLine(to: CGPoint(x: x, y: mid + a))
                            } else {
                                futurePath.move(to: CGPoint(x: x, y: mid - a))
                                futurePath.addLine(to: CGPoint(x: x, y: mid + a))
                            }
                        }
                    }
                }
                xi += 1
            }
            ctx.stroke(futurePath, with: .color(future.opacity(0.5)), lineWidth: 1)
            ctx.stroke(playedPath, with: .color(played.opacity(0.95)), lineWidth: 1)
        }

        // Fixed playhead + top triangle.
        var ph = Path()
        ph.move(to: CGPoint(x: playheadX, y: 0))
        ph.addLine(to: CGPoint(x: playheadX, y: h))
        ctx.stroke(ph, with: .color(ink), lineWidth: 2)
        var tri = Path()
        tri.move(to: CGPoint(x: playheadX - 4.5, y: 0))
        tri.addLine(to: CGPoint(x: playheadX + 5.5, y: 0))
        tri.addLine(to: CGPoint(x: playheadX + 0.5, y: 6))
        tri.closeSubpath()
        ctx.fill(tri, with: .color(ink))
    }
}
