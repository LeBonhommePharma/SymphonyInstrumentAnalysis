#!/usr/bin/env swift
/// On-device cluster namer for the web piano. Bind 127.0.0.1:4174.
/// POST /label  { "tracks": [{ "id", "f0", "harmonicity", "duration", "mag" }] }
/// GET  /health { "fm": bool }
/// Never sends audio. Apple Intelligence if present; else heuristic names.
/// Run: swift scripts/cluster_labeler.swift

import Foundation
import Network

#if canImport(FoundationModels)
import FoundationModels
#endif

let port: NWEndpoint.Port = 4174

func heuristic(f0: Double, harm: Double) -> String {
    if harm < 0.18 && f0 > 180 { return "bruit" }
    if f0 < 90 { return "grave" }
    if f0 < 280 && harm >= 0.35 { return "voix" }
    if f0 < 450 { return "corps" }
    if harm >= 0.55 { return "nylon" }
    if f0 > 1400 { return "air" }
    return ""
}

func sanitize(_ raw: String) -> String {
    let first = raw.split(whereSeparator: { $0.isNewline || $0 == "." || $0 == "," }).first.map(String.init) ?? ""
    let trimmed = first.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    let allowed: Set<String> = [
        "grave", "voix", "nylon", "corde", "bois", "souffle", "bruit",
        "piano", "air", "corps", "metal", "basse", "voice", "bass", "noise"
    ]
    if allowed.contains(trimmed) { return trimmed }
    if trimmed.count <= 16 && trimmed.unicodeScalars.allSatisfy({ CharacterSet.letters.contains($0) }) {
        return trimmed
    }
    return ""
}

func fmAvailable() -> Bool {
    #if canImport(FoundationModels)
    if #available(macOS 26.0, iOS 26.0, *) {
        if case .available = SystemLanguageModel.default.availability { return true }
    }
    #endif
    return false
}

func cors(_ extra: [String: String] = [:]) -> [String: String] {
    var h = [
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Content-Type": "application/json; charset=utf-8"
    ]
    extra.forEach { h[$0.key] = $0.value }
    return h
}

func http(_ status: Int, body: Data, extra: [String: String] = [:]) -> Data {
    let reason = status == 200 ? "OK" : "Error"
    var head = "HTTP/1.1 \(status) \(reason)\r\n"
    let headers = cors(extra)
    headers.forEach { head += "\($0.key): \($0.value)\r\n" }
    head += "Content-Length: \(body.count)\r\n\r\n"
    var out = Data(head.utf8)
    out.append(body)
    return out
}

func json(_ obj: Any) -> Data {
    (try? JSONSerialization.data(withJSONObject: obj, options: [])) ?? Data("{}".utf8)
}

func labelTracks(_ tracks: [[String: Any]]) async -> (fm: Bool, labels: [[String: Any]]) {
    let hasFM = fmAvailable()
    var labels: [[String: Any]] = []
    #if canImport(FoundationModels)
    if hasFM, #available(macOS 26.0, iOS 26.0, *) {
        let session = LanguageModelSession()
        for row in tracks {
            let id = row["id"] as? Int ?? Int(row["id"] as? Double ?? 0)
            let f0 = row["f0"] as? Double ?? 0
            let harm = row["harmonicity"] as? Double ?? 0
            let mag = row["mag"] as? Double ?? 0
            let prompt = """
            Name one live audio source from stats. Reply with one short noun only.
            Allowed: grave, voix, nylon, corde, bois, souffle, bruit, piano, air, corps, metal, basse
            f0_hz: \(Int(f0.rounded())) harmonicity: \(String(format: "%.2f", harm)) mag_db: \(Int(mag.rounded()))
            """
            var name = ""
            var source = "heuristic"
            do {
                let response = try await session.respond(to: prompt)
                let cleaned = sanitize(response.content)
                if !cleaned.isEmpty {
                    name = cleaned
                    source = "fm"
                }
            } catch {
                name = heuristic(f0: f0, harm: harm)
            }
            if name.isEmpty { name = heuristic(f0: f0, harm: harm) }
            if !name.isEmpty {
                labels.append(["id": id, "name": name, "source": source])
            }
        }
        return (true, labels)
    }
    #endif
    for row in tracks {
        let id = row["id"] as? Int ?? Int(row["id"] as? Double ?? 0)
        let f0 = row["f0"] as? Double ?? 0
        let harm = row["harmonicity"] as? Double ?? 0
        let name = heuristic(f0: f0, harm: harm)
        if !name.isEmpty {
            labels.append(["id": id, "name": name, "source": "heuristic"])
        }
    }
    return (false, labels)
}

final class LabelServer {
    let listener: NWListener
    let queue = DispatchQueue(label: "cluster-labeler")

    init() throws {
        listener = try NWListener(using: .tcp, on: port)
        listener.newConnectionHandler = { [weak self] conn in
            self?.handle(conn)
        }
        listener.start(queue: queue)
        fputs("cluster_labeler http://127.0.0.1:\(port.rawValue) fm=\(fmAvailable())\n", stdout)
        fflush(stdout)
    }

    func handle(_ conn: NWConnection) {
        conn.start(queue: queue)
        conn.receive(minimumIncompleteLength: 1, maximumLength: 64 * 1024) { data, _, _, _ in
            guard let data, !data.isEmpty, let raw = String(data: data, encoding: .utf8) else {
                conn.cancel()
                return
            }
            Task {
                let reply = await self.respond(raw)
                conn.send(content: reply, completion: .contentProcessed { _ in
                    conn.cancel()
                })
            }
        }
    }

    func respond(_ raw: String) async -> Data {
        let parts = raw.split(separator: "\r\n", maxSplits: 1, omittingEmptySubsequences: false)
        let requestLine = parts.first.map(String.init) ?? ""
        if requestLine.hasPrefix("OPTIONS") {
            return http(204, body: Data())
        }
        if requestLine.hasPrefix("GET /health") {
            return http(200, body: json(["fm": fmAvailable(), "ok": true]))
        }
        if requestLine.hasPrefix("POST /label") {
            let body: Data
            if let range = raw.range(of: "\r\n\r\n") {
                body = Data(raw[range.upperBound...].utf8)
            } else {
                body = Data()
            }
            let obj = (try? JSONSerialization.jsonObject(with: body)) as? [String: Any]
            let tracks = obj?["tracks"] as? [[String: Any]] ?? []
            let result = await labelTracks(tracks)
            return http(200, body: json(["fm": result.fm, "labels": result.labels]))
        }
        return http(404, body: json(["error": "not found"]))
    }
}

do {
    _ = try LabelServer()
    RunLoop.main.run()
} catch {
    fputs("cluster_labeler failed: \(error)\n", stderr)
    exit(1)
}
