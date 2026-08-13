import Foundation

#if canImport(FoundationModels)
import FoundationModels
#endif

struct LiveTrack: Identifiable, Hashable {
    var id: Int
    var f0: Double
    var db: Float
    var harm: Double
    var energy: Double
    var born: Double
    var lastSeen: Double
    var label: String = ""
    var labelSource: String = ""

    var pitchClass: NoteName {
        let midi = Int(PitchMath.hzToMidi(f0, concertA: PitchMath.a4Ref).rounded())
        return NoteName.pitchClass(of: midi)
    }

    var caption: String {
        if !label.isEmpty { return label }
        let midi = Int(PitchMath.hzToMidi(f0, concertA: PitchMath.a4Ref).rounded())
        if midi >= PitchMath.midiLo && midi <= PitchMath.midiHi {
            return "\(NoteName.pitchClass(of: midi).french)\(PitchMath.octave(of: midi))"
        }
        return String(Int(f0.rounded()))
    }
}

enum ClusterLabeler {
    static func heuristic(_ t: LiveTrack) -> String {
        if t.harm < 0.18 && t.f0 > 180 { return "bruit" }
        if t.f0 < 90 { return "grave" }
        if t.f0 < 280 && t.harm >= 0.35 { return "voix" }
        if t.f0 < 450 { return "corps" }
        if t.harm >= 0.55 { return "nylon" }
        if t.f0 > 1400 { return "air" }
        return ""
    }

    @MainActor
    static func label(_ tracks: [LiveTrack]) async -> [(id: Int, name: String, source: String)] {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, macOS 26.0, *) {
            let fm = await fmLabels(tracks)
            if !fm.isEmpty { return fm }
        }
        #endif
        return tracks.compactMap { t in
            let name = heuristic(t)
            guard !name.isEmpty else { return nil }
            return (t.id, name, "heuristic")
        }
    }

    #if canImport(FoundationModels)
    @available(iOS 26.0, macOS 26.0, *)
    @MainActor
    private static func fmLabels(_ tracks: [LiveTrack]) async -> [(id: Int, name: String, source: String)] {
        let model = SystemLanguageModel.default
        switch model.availability {
        case .available:
            break
        default:
            return []
        }
        var out: [(id: Int, name: String, source: String)] = []
        let session = LanguageModelSession()
        for t in tracks {
            let prompt = """
            Name one live audio source from stats. Reply with one short noun only.
            Allowed: grave, voix, nylon, corde, bois, souffle, bruit, piano, air, corps, metal, basse
            f0_hz: \(Int(t.f0.rounded())) harmonicity: \(String(format: "%.2f", t.harm)) mag_db: \(Int(t.db.rounded()))
            """
            do {
                let response = try await session.respond(to: prompt)
                let name = sanitize(response.content)
                if !name.isEmpty {
                    out.append((t.id, name, "fm"))
                }
            } catch {
                continue
            }
        }
        return out
    }
    #endif

    static func sanitize(_ raw: String) -> String {
        let first = raw.split(whereSeparator: { $0.isNewline || $0 == "," || $0 == "." }).first.map(String.init) ?? ""
        let trimmed = first.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let allowed = Set([
            "grave", "voix", "nylon", "corde", "bois", "souffle", "bruit",
            "piano", "air", "corps", "metal", "basse", "voice", "bass", "noise"
        ])
        if allowed.contains(trimmed) { return trimmed }
        if trimmed.count <= 16 && trimmed.unicodeScalars.allSatisfy({ CharacterSet.letters.contains($0) }) {
            return trimmed
        }
        return ""
    }
}
