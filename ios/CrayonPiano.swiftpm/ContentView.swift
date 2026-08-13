import SwiftUI

struct ContentView: View {
    @StateObject private var session = PianoSession()

    var body: some View {
        ZStack {
            session.scene.background.ignoresSafeArea()
            VStack(spacing: 0) {
                header
                    .padding(.horizontal, 14)
                    .padding(.top, 10)
                    .padding(.bottom, 8)
                ScrollView(.vertical, showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 14) {
                        ViewThatFits(in: .horizontal) {
                            HStack(alignment: .center, spacing: 10) {
                                controls
                                toggles
                            }
                            VStack(alignment: .leading, spacing: 10) {
                                controls
                                toggles
                            }
                        }
                        trackRow
                        if session.mode != .live {
                            HStack(alignment: .center, spacing: 10) {
                                WaveformTrackView(session: session)
                                Text(clock)
                                    .font(.caption.monospacedDigit().weight(.semibold))
                                    .foregroundStyle(session.scene.ink)
                                    .fixedSize()
                            }
                            .frame(height: 68)
                        }
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Spectre · sources regroupées")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(session.scene.muted)
                            SpectrumPlotView(session: session)
                                .frame(height: 280)
                                .frame(maxWidth: .infinity)
                        }
                        if !session.tuneLine.isEmpty {
                            Text(session.tuneLine)
                                .font(.subheadline.weight(.semibold).monospacedDigit())
                                .foregroundStyle(session.scene.ink)
                        }
                        if let err = session.errorMessage {
                            Text(err)
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(Color(red: 0.54, green: 0.29, blue: 0.30))
                        }
                        chromaRow
                        chipsRow
                        legend
                    }
                    .padding(.horizontal, 14)
                    .padding(.bottom, 12)
                }
                piano
                    .padding(.horizontal, 10)
                    .padding(.bottom, 10)
            }
        }
        .preferredColorScheme(session.scene.colorScheme)
        .statusBarHidden(false)
        .animation(.easeInOut(duration: 0.22), value: session.sceneChoice)
    }

    private var header: some View {
        HStack(alignment: .center, spacing: 12) {
            Text("Piano-crayon")
                .font(.title2.weight(.semibold))
                .foregroundStyle(session.scene.ink)
            Spacer(minLength: 8)
            scenePicker
        }
    }

    private var scenePicker: some View {
        HStack(spacing: 6) {
            ForEach(SceneStyle.allCases) { style in
                Button {
                    session.sceneChoice = style
                } label: {
                    Circle()
                        .fill(style.swatch)
                        .overlay(
                            Circle().stroke(
                                style.isLight
                                    ? Color.black.opacity(0.22)
                                    : Color.white.opacity(0.35),
                                lineWidth: 1
                            )
                        )
                        .overlay(
                            Circle().stroke(
                                session.sceneChoice == style ? session.scene.ink : Color.clear,
                                lineWidth: 2
                            )
                        )
                        .frame(width: 28, height: 28)
                        .padding(8)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(style.french)
                .accessibilityAddTraits(session.sceneChoice == style ? .isSelected : [])
            }
        }
        .padding(.horizontal, 4)
        .background(session.scene.paper.opacity(0.88), in: Capsule())
        .overlay(Capsule().stroke(session.scene.muted.opacity(0.35), lineWidth: 1))
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Ambiance")
    }

    private var controls: some View {
        HStack(spacing: 8) {
            Button(session.mode == .replay ? "Stop" : "Rejouer") {
                session.toggleReplay()
            }
            .buttonStyle(CrayonButtonStyle(kind: session.mode == .replay ? .replayOn : .replay, scene: session.scene))

            Button(session.mode == .live ? "Stop" : "Écouter") {
                session.toggleListen()
            }
            .buttonStyle(CrayonButtonStyle(kind: session.mode == .live ? .live : .stop, scene: session.scene))
        }
    }

    private var toggles: some View {
        HStack(spacing: 8) {
            iconToggle(session.chordsOn, label: "Accords") {
                session.chordsOn.toggle()
            } glyph: {
                ChordGlyph(on: session.chordsOn)
            }
            iconToggle(session.unmute, label: "Son") {
                session.unmute.toggle()
                session.applyUnmute()
            } glyph: {
                SpeakerGlyph(on: session.unmute)
            }
            iconToggle(session.autotune, label: "La") {
                session.autotune.toggle()
            } glyph: {
                LaGlyph(on: session.autotune)
            }
            if !session.statusLine.isEmpty {
                Text(session.statusLine)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(session.scene.ink)
                    .lineLimit(1)
            }
        }
    }

    private func iconToggle<G: View>(
        _ on: Bool,
        label: String,
        action: @escaping () -> Void,
        @ViewBuilder glyph: () -> G
    ) -> some View {
        Button(action: action) {
            glyph()
                .frame(width: 44, height: 44)
                .background(session.scene.paper, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .stroke(session.scene.muted.opacity(0.45), lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
        .accessibilityAddTraits(on ? .isSelected : [])
    }

    private var trackRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
            Text("\(session.liveTracks.count)")
                .font(.caption.weight(.semibold).monospacedDigit())
                .foregroundStyle(session.scene.muted)
                .frame(width: 28, height: 44)
                .background(session.scene.paper, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            if session.liveTracks.isEmpty {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(session.scene.muted.opacity(0.35), lineWidth: 1)
                    .frame(width: 44, height: 44)
                    .opacity(0.28)
            } else {
                ForEach(session.liveTracks) { track in
                    Button {
                        session.toggleTrack(track.id)
                    } label: {
                        Text(track.caption)
                            .font(.caption2.weight(.semibold))
                            .foregroundStyle(track.pitchClass.labelColor)
                            .frame(minWidth: 44, minHeight: 44)
                            .background(track.pitchClass.color.opacity(track.energy > 0.18 ? 1 : 0.28), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                    }
                    .buttonStyle(.plain)
                    .opacity(track.energy > 0.18 ? 1 : 0.4)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(session.selectedTrackId == track.id || session.isTous ? session.scene.ink.opacity(0.5) : Color.clear, lineWidth: 1)
                    )
                    .accessibilityLabel("\(track.caption) \(Int(track.f0.rounded())) Hz")
                }
            }
            }
        }
    }

    private var chromaRow: some View {
        HStack(spacing: 2) {
            ForEach(NoteName.allCases, id: \.self) { name in
                let db = session.chroma[name] ?? -120
                let on = session.lit.contains { $0.name == name }
                VStack {
                    Spacer(minLength: 0)
                    Capsule()
                        .fill(name.color)
                        .frame(height: max(4, min(48, CGFloat((db + 80) * 1.2))))
                }
                .frame(maxWidth: .infinity, minHeight: 52)
                .overlay(alignment: .bottom) {
                    Text(name.french)
                        .font(.system(size: 8, weight: .semibold))
                        .foregroundStyle(on ? name.labelColor : session.scene.muted)
                        .padding(.bottom, 2)
                }
                .background(session.scene.paper, in: RoundedRectangle(cornerRadius: 4))
            }
        }
        .padding(4)
        .background(session.scene.paper, in: RoundedRectangle(cornerRadius: 10))
    }

    private var chipsRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                if session.lit.isEmpty && session.pressed.isEmpty {
                    Color.clear.frame(height: 8)
                } else {
                    ForEach((session.lit + session.pressed.map { LitNote(midi: $0, db: 0, freq: 0) }).uniquedMidis) { note in
                        Text(note.label)
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(note.name.labelColor)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 5)
                            .background(note.name.color, in: RoundedRectangle(cornerRadius: 6))
                    }
                }
            }
        }
        .frame(minHeight: 28)
    }

    private var piano: some View {
        PianoKeyboardView(
            lit: session.lit,
            harmonics: session.harmonics,
            pressed: session.pressed,
            scene: session.scene,
            onPressed: { session.setPressed($0) }
        )
        .frame(height: 228)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(session.scene.muted.opacity(0.35), lineWidth: 1)
        )
        .shadow(color: session.scene.ink.opacity(session.scene.isLight ? 0.08 : 0.28), radius: 18, y: 8)
    }

    private var legend: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Crayons")
                .font(.caption.weight(.semibold))
                .foregroundStyle(session.scene.ink)
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 4), count: 6), spacing: 4) {
                ForEach(NoteName.allCases, id: \.self) { name in
                    Button {
                        session.setPressed([60 + (NoteName.allCases.firstIndex(of: name) ?? 0)])
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
                            session.setPressed([])
                        }
                    } label: {
                        VStack(spacing: 1) {
                            Text(name.french).font(.caption.weight(.semibold))
                            Text("\(name.rawValue) · \(name.pencil)").font(.system(size: 8, weight: .semibold))
                            Text("~\(Int(name.hz.rounded())) Hz").font(.system(size: 8).monospacedDigit())
                        }
                        .foregroundStyle(name.labelColor)
                        .frame(maxWidth: .infinity, minHeight: 52)
                        .background(name.color, in: RoundedRectangle(cornerRadius: 8))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private var clock: String {
        func fmt(_ s: Double) -> String {
            let t = max(0, s)
            let m = Int(t) / 60
            let sec = t - Double(m * 60)
            return String(format: "%d:%04.1f", m, sec)
        }
        return "\(fmt(session.sampleTime)) / \(fmt(session.sampleDuration))"
    }
}

private struct CrayonButtonStyle: ButtonStyle {
    enum Kind {
        case live
        case stop
        case replay
        case replayOn
    }

    var kind: Kind
    var scene: SceneStyle

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .foregroundStyle(foreground)
            .background(background, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .stroke(border, lineWidth: 1)
            )
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .opacity(configuration.isPressed ? 0.9 : 1)
    }

    private var background: Color {
        switch kind {
        case .live: return Color(red: 0.44, green: 0.60, blue: 0.28).opacity(0.85)
        case .stop: return Color(red: 0.60, green: 0.28, blue: 0.29).opacity(scene.isLight ? 0.95 : 0.35)
        case .replay: return Color(red: 0.28, green: 0.28, blue: 0.60).opacity(scene.isLight ? 0.95 : 0.35)
        case .replayOn: return Color(red: 0.28, green: 0.49, blue: 0.60).opacity(0.9)
        }
    }

    private var border: Color { background }
    private var foreground: Color {
        scene.isLight
            ? Color(red: 0.969, green: 0.945, blue: 0.910)
            : Color(red: 0.604, green: 0.604, blue: 0.635)
    }
}

private extension Array where Element == LitNote {
    var uniquedMidis: [LitNote] {
        var seen = Set<Int>()
        return filter { seen.insert($0.midi).inserted }
    }
}

private struct ChordGlyph: View {
    var on: Bool
    var body: some View {
        ZStack {
            Circle().fill(on ? Color(red: 0.20, green: 0.66, blue: 0.35) : Color.gray.opacity(0.45)).frame(width: 6, height: 6)
            if on {
                Circle().fill(Color(red: 0.20, green: 0.66, blue: 0.35)).frame(width: 6, height: 6).offset(x: 8, y: 8)
                Circle().fill(Color(red: 0.20, green: 0.66, blue: 0.35)).frame(width: 6, height: 6).offset(x: -8, y: 8)
            }
        }
    }
}

private struct SpeakerGlyph: View {
    var on: Bool
    var color: Color { on ? Color(red: 0.20, green: 0.66, blue: 0.35) : Color.gray.opacity(0.45) }
    var body: some View {
        HStack(spacing: 0) {
            RoundedRectangle(cornerRadius: 1).fill(color).frame(width: 5, height: 6)
            Triangle().fill(color).frame(width: 9, height: 12)
        }
    }
}

private struct Triangle: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: rect.minX, y: rect.minY))
        p.addLine(to: CGPoint(x: rect.maxX, y: rect.midY))
        p.addLine(to: CGPoint(x: rect.minX, y: rect.maxY))
        p.closeSubpath()
        return p
    }
}

private struct LaGlyph: View {
    var on: Bool
    var body: some View {
        Circle()
            .fill(on ? Color(red: 0, green: 0, blue: 1) : Color.clear)
            .overlay(Circle().stroke(Color(red: 0, green: 0, blue: 1), lineWidth: 2))
            .frame(width: 16, height: 16)
    }
}

#Preview {
    ContentView()
}
