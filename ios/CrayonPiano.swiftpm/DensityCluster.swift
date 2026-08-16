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
    /// Ports scripts/density_cluster.py. Shared cases live in piano/cluster_fixtures.json.
    /// No count cap — every independent fund stays a source. Harmonics already folded.

    private static let dbscanMinPts = 3
    private static let epsFloor = 0.28
    private static let epsCap = 0.85
    private static let epsNeighborScale = 0.9
    /// Distinct fundamentals more than this many cents apart never share a cluster.
    private static let minF0Cents = 70.0

    static func cluster(peaks: [SpecPeak], mergeNearby: Bool = true) -> [SpectralCluster] {
        let funds = groupHarmonicFunds(peaks)
        if !mergeNearby { return fundsAsClusters(funds) }
        return densityClusterFunds(funds)
    }

    private static func fundsAsClusters(_ funds: [Fund]) -> [SpectralCluster] {
        funds
            .filter { $0.db > -90 }
            .sorted { $0.db > $1.db }
            .map { SpectralCluster(f0: $0.f0, db: $0.db, harm: $0.harm, centroid: $0.centroid) }
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

    private static func cents(_ a: Double, _ b: Double) -> Double {
        if a <= 0 || b <= 0 { return 1e9 }
        return abs(1200 * log2(a / b))
    }

    private static func fillFundStats(_ g: inout Fund) {
        var w = 0.0
        var fSum = 0.0
        for m in g.members {
            let mag = pow(10.0, Double(m.db) / 20.0)
            w += mag
            fSum += m.f * mag
        }
        g.centroid = fSum / (w == 0 ? 1 : w)
        g.harm = min(1, Double(g.members.count - 1) / 5)
        g.logF = log2(max(g.f0, 1e-6))
        g.logC = log2(max(g.centroid, 1))
    }

    /// Prefer the lowest candidate that explains the partials (not the loudest).
    /// Half-f0 only when a peak sits there or an odd partial needs that f0.
    private static func refineFundF0(_ g: inout Fund) {
        let freqs = g.members.map(\.f).filter { $0 > 0 }
        guard !freqs.isEmpty else { return }
        var cands = freqs
        cands.append(contentsOf: freqs.map { $0 / 2 })
        var best = g.f0
        var bestScore = -1e18
        for cand in cands {
            if cand < 20 { continue }
            var hits = 0
            var oddHi = 0
            var hasSelf = false
            for f in freqs {
                let n = (f / cand).rounded()
                if n >= 1 && n <= 16 && cents(f, n * cand) < 35 {
                    hits += 1
                    if n == 1 { hasSelf = true }
                    if n >= 3 && n.truncatingRemainder(dividingBy: 2) == 1 { oddHi += 1 }
                }
            }
            if hits < 2 { continue }
            if !hasSelf && oddHi < 1 { continue }
            let score = Double(hits) * 1000 + Double(oddHi) * 10 - cand
            if score > bestScore {
                bestScore = score
                best = cand
            }
        }
        g.f0 = best
    }

    private static func mergeOctaveFunds(_ funds: [Fund]) -> [Fund] {
        let sorted = funds.sorted { $0.f0 < $1.f0 }
        var used = Set<Int>()
        var out: [Fund] = []
        for i in sorted.indices {
            if used.contains(i) { continue }
            var a = sorted[i]
            if i + 1 < sorted.count {
                for j in (i + 1)..<sorted.count {
                    if used.contains(j) { continue }
                    let b = sorted[j]
                    let n = a.f0 == 0 ? 0 : (b.f0 / a.f0).rounded()
                    if n < 1 || n > 8 { continue }
                    if cents(b.f0, n * a.f0) < 35 {
                        a.members.append(contentsOf: b.members)
                        a.db = max(a.db, b.db)
                        used.insert(j)
                    }
                }
            }
            fillFundStats(&a)
            out.append(a)
        }
        return out
    }

    private static func groupHarmonicFunds(_ peaks: [SpecPeak]) -> [Fund] {
        var funds: [Fund] = []
        for p in peaks.sorted(by: { $0.db > $1.db }) {
            var bestIdx: Int?
            var bestCents = 35.0
            for i in funds.indices {
                let n = (p.f / funds[i].f0).rounded()
                if n < 2 || n > 16 { continue }
                let c = cents(p.f, n * funds[i].f0)
                if c < bestCents {
                    bestIdx = i
                    bestCents = c
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
            refineFundF0(&funds[i])
            fillFundStats(&funds[i])
        }
        return mergeOctaveFunds(funds)
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
        let median = gaps.isEmpty ? epsFloor : gaps[gaps.count / 2]
        let eps = max(epsFloor, min(epsCap, median * epsNeighborScale))
        let n = pts.count
        var labels = Array(repeating: -1, count: n)

        func neighbors(_ i: Int) -> [Int] {
            var out: [Int] = []
            for j in 0..<n {
                if i == j { continue }
                if abs(1200 * (pts[i].g.logF - pts[j].g.logF)) > minF0Cents { continue }
                if dist(pts[i].x, pts[j].x) <= eps { out.append(j) }
            }
            return out
        }

        // neighbors exclude self; +1 counts the point. minPts=3 means a pair of
        // notes is not a core (avoids single-linkage A~B~C chains).
        var core = Array(repeating: false, count: n)
        for i in 0..<n { core[i] = neighbors(i).count + 1 >= dbscanMinPts }

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
