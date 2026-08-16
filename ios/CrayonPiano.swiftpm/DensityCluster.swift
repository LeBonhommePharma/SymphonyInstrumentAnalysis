import Foundation

struct SpecPeak {
    var f: Double
    var db: Float
}

struct SpectralCluster {
    var f0: Double
    var db: Float
    var harm: Double
    var centroid: Double
}

enum DensityCluster {
    /// No count cap — every independent fund stays a source. Harmonics already folded.

    static func cluster(peaks: [SpecPeak]) -> [SpectralCluster] {
        densityClusterFunds(groupHarmonicFunds(peaks))
    }

    private struct Fund {
        var f0: Double
        var db: Float
        var members: [SpecPeak]
        var centroid: Double = 0
        var harm: Double = 0
        var logF: Double = 0
        var logC: Double = 0
    }

    private static func groupHarmonicFunds(_ peaks: [SpecPeak]) -> [Fund] {
        var funds: [Fund] = []
        for p in peaks.sorted(by: { $0.db > $1.db }) {
            var bestIdx: Int? = nil
            var bestCents = 35.0
            for i in funds.indices {
                let n = (p.f / funds[i].f0).rounded()
                if n < 2 || n > 16 { continue }
                let cents = abs(1200 * log2(p.f / (n * funds[i].f0)))
                if cents < bestCents {
                    bestIdx = i
                    bestCents = cents
                }
            }
            if let idx = bestIdx {
                funds[idx].members.append(p)
                funds[idx].db = max(funds[idx].db, p.db)
            } else {
                funds.append(Fund(f0: p.f, db: p.db, members: [p]))
            }
        }
        for i in funds.indices {
            var w: Double = 0
            var fSum: Double = 0
            for m in funds[i].members {
                let mag = pow(10.0, Double(m.db) / 20.0)
                w += mag
                fSum += m.f * mag
            }
            funds[i].centroid = fSum / (w == 0 ? 1 : w)
            funds[i].harm = min(1, Double(funds[i].members.count - 1) / 5)
            funds[i].logF = log2(funds[i].f0)
            funds[i].logC = log2(max(funds[i].centroid, 1))
        }
        return funds
    }

    private static func feat(_ g: Fund) -> (Double, Double, Double) {
        (g.logF * 0.42, g.harm * 1.8, g.logC * 0.35)
    }

    private static func dist(_ a: (Double, Double, Double), _ b: (Double, Double, Double)) -> Double {
        let dx = a.0 - b.0
        let dy = a.1 - b.1
        let dz = a.2 - b.2
        return sqrt(dx * dx + dy * dy + dz * dz)
    }

    private static func densityClusterFunds(_ funds: [Fund]) -> [SpectralCluster] {
        guard !funds.isEmpty else { return [] }
        let pts = funds.map { (g: $0, x: feat($0)) }
        var gaps: [Double] = []
        for i in pts.indices {
            var best = 1e9
            for j in pts.indices where i != j {
                let d = dist(pts[i].x, pts[j].x)
                if d < best { best = d }
            }
            if best < 1e9 { gaps.append(best) }
        }
        gaps.sort()
        let median = gaps.isEmpty ? 0.28 : gaps[gaps.count / 2]
        // Scale eps *below* the median nearest-neighbor gap (was 1.35×) so two
        // distinct fundamentals stay separate; the old inflation let the
        // single-linkage expansion chain A~B~C into one cluster.
        let eps = max(0.28, min(0.85, median * 0.9))
        let n = pts.count
        var labels = Array(repeating: -1, count: n)

        let order = pts.indices.sorted { pts[$0].g.logF < pts[$1].g.logF }
        func neighbors(_ i: Int) -> [Int] {
            var out: [Int] = []
            let logF = pts[i].g.logF
            for j in order {
                if abs(pts[j].g.logF - logF) * 0.42 > eps + 0.05 { continue }
                if dist(pts[i].x, pts[j].x) <= eps { out.append(j) }
            }
            return out
        }

        // Proper DBSCAN with minPts = 2: only core points (>= 2 points incl.
        // self within eps) seed a cluster. Isolated funds stay their own track.
        var core = Array(repeating: false, count: n)
        for i in 0..<n { core[i] = neighbors(i).count + 1 >= 2 }

        var cid = 0
        for i in 0..<n {
            if labels[i] != -1 || !core[i] { continue }
            labels[i] = cid
            var seed = neighbors(i)
            var s = 0
            while s < seed.count {
                let j = seed[s]
                s += 1
                if labels[j] == -1 {
                    labels[j] = cid
                    if core[j] {
                        for k in neighbors(j) where !seed.contains(k) {
                            seed.append(k)
                        }
                    }
                }
            }
            cid += 1
        }
        for i in 0..<n where labels[i] == -1 {
            labels[i] = cid
            cid += 1
        }

        var buckets: [Int: [Fund]] = [:]
        for i in 0..<n {
            buckets[labels[i], default: []].append(pts[i].g)
        }
        var clusters: [SpectralCluster] = []
        for members in buckets.values {
            let sorted = members.sorted { $0.db > $1.db }
            guard let head = sorted.first else { continue }
            let db = sorted.map(\.db).max() ?? head.db
            let harm = sorted.map(\.harm).reduce(0, +) / Double(sorted.count)
            clusters.append(SpectralCluster(f0: head.f0, db: db, harm: harm, centroid: head.centroid))
        }
        clusters.sort { $0.db > $1.db }
        return clusters.filter { $0.db > -90 }
    }
}
