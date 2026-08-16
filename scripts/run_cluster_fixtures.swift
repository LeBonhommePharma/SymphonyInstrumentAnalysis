import Foundation

/// Compile with DensityCluster.swift:
///   swiftc -o /tmp/run_cluster_fixtures \
///     ios/CrayonPiano.swiftpm/DensityCluster.swift \
///     scripts/run_cluster_fixtures.swift
@main
enum RunClusterFixtures {
    static func main() throws {
        let root = CommandLine.arguments.count > 1
            ? URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
            : URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true)
        let url = root.appendingPathComponent("piano/cluster_fixtures.json")
        let data = try Data(contentsOf: url)
        guard let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let cases = obj["cases"] as? [[String: Any]]
        else {
            fputs("bad fixtures: \(url.path)\n", stderr)
            exit(1)
        }
        for c in cases {
            let name = c["name"] as? String ?? "?"
            let merge = (c["merge_nearby"] as? Bool) ?? true
            let expectN = (c["expect_n"] as? NSNumber)?.intValue ?? -1
            let expectF0 = ((c["expect_f0"] as? [NSNumber]) ?? []).map(\.doubleValue)
            let rawPeaks = (c["peaks"] as? [[String: Any]]) ?? []
            let peaks = rawPeaks.compactMap { row -> SpecPeak? in
                guard let f = (row["f"] as? NSNumber)?.doubleValue,
                      let db = (row["db"] as? NSNumber)?.floatValue
                else { return nil }
                return SpecPeak(f: f, db: db)
            }
            let got = DensityCluster.cluster(peaks: peaks, mergeNearby: merge)
            if got.count != expectN {
                fputs("\(name): expected \(expectN) clusters, got \(got.count)\n", stderr)
                exit(1)
            }
            for (i, want) in expectF0.enumerated() {
                guard i < got.count else { break }
                if abs(got[i].f0 - want) > 1.0 {
                    fputs("\(name): f0[\(i)] \(got[i].f0) != \(want)\n", stderr)
                    exit(1)
                }
            }
        }
        print("cluster_fixtures.swift: \(cases.count) fixtures OK")
    }
}
