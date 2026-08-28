# Data-at-Scale: ETL & Analytics on a Maxed-Out Mac Studio

**Bottom line up front:** A maxed M5 Ultra Mac Studio (36-core CPU, 1.2TB/s bandwidth, 512GB RAM, 16TB NVMe) genuinely replaces a small, chronically-underprovisioned Spark cluster for interactive-to-batch analytics from a few GB up to roughly 1-3TB of working data, on the strength of published DuckDB/DataFusion single-node numbers. It stops being "enterprise-in-a-box" the moment the job needs >16TB of local disk, more concurrent users than 36 cores can serve, fault-tolerant multi-day execution, or — most immediately for most people — a network pipe faster than home/small-office internet to actually get the data onto the box. Thunderbolt 5 RDMA clustering across multiple Studios is real and fast, but every public claim found is about pooling memory for AI/LLM inference, not about distributed SQL/ETL — treat "cluster your Mac Studios for Spark-scale ETL" as unproven, not just unbenchmarked.

Hardware envelope used throughout: **M5 Ultra** — 36-core CPU, 1.2TB/s memory bandwidth, up to 512GB unified memory, 16TB internal SSD (~6GB/s), 10GbE, Thunderbolt 5 w/ RDMA clustering, $5,499 base. **M5 Max** — 18-core CPU (see discrepancy note below), 614GB/s, 128GB, 8TB, $2,499 base.

---

## 1. What runs, and at what dataset size

| Tier | Ceiling on this hardware | Engines | Evidence |
|---|---|---|---|
| **Fits in RAM** | ≤128GB (M5 Max) / ≤512GB (M5 Ultra) | DuckDB, Polars, DataFusion | see below |
| **Larger-than-memory** | Up to ~16TB via NVMe spill (M5 Ultra only) | DuckDB (built-in out-of-core), Spark-local (disk spill) | see below |
| **Out of reach** | > local SSD capacity, or needs fault-tolerant multi-node execution | — needs a cluster | §2 |

**In-RAM tier.** DuckDB completes the full TPC-H SF100 (~100GB) query suite in **10.7s**, and SF1000 (~1TB) in **121s** ([DuckDB benchmark results, 2025-10-09](https://duckdb.org/2025/10/09/benchmark-results-14-lts)) — SF100 sits comfortably inside even the 128GB M5 Max; SF1000 needs the 512GB M5 Ultra tier. On a 100M-row group-by, Polars finished in **23s** vs DuckDB's **31s** ([benchmark writeup, 2025-05-15, medium confidence](https://medium.com/@2nick2patel2/we-benchmarked-pandas-vs-polars-vs-duckdb-jaw-dropping-results-29fb05809424)) — Polars can edge out DuckDB at this scale, but a separate source reports DuckDB overtaking Polars' in-memory engine once data reaches **~1TB** ([Confessions of a Data Guy, 2025-12-15, medium confidence, single source](https://www.confessionsofadataguy.com/duckdb-beats-polars-for-1tb-of-data/)). Memory *efficiency* matters more than the raw win/loss: on a 140GB Parquet dataset, DuckDB peaked at **~1.3GB** RAM vs Polars' **~17GB** ([codecentric.de, 2025-03-20](https://www.codecentric.de/en/knowledge-hub/blog/duckdb-vs-polars-performance-and-memory-with-massive-parquet-data)) — meaning even the 128GB M5 Max has huge headroom for DuckDB-style streaming execution, while Polars' more memory-hungry model is the one that actually benefits from paying for the Ultra's extra RAM. DataFusion is independently reported as the **fastest single-node engine on ClickBench Parquet (14GB)** as of November 2024 ([Apache DataFusion blog](https://datafusion.apache.org/blog/2024/11/18/datafusion-fastest-single-node-parquet-clickbench/)) — but that was measured on a cloud `c6a.4xlarge` instance, not Apple Silicon; **no Apple-Silicon-native DataFusion/DuckDB/Polars number exists in the evidence base** (gap, flagged below). Apple's own NEON SIMD path shows 1.2x-4.3x speedups on analytics-shaped micro-benchmarks on M4 ([dev.to, medium confidence](https://dev.to/erioharrison/rust-simd-benchmark-stdsimd-vs-neon-on-apple-m4-47jd)) — directional color, not a DuckDB/Spark measurement.

**Larger-than-memory tier.** DuckDB's TPC-H SF1000 result above (~1TB, 121s) is itself in this zone for the 128GB M5 Max (though it fits in-RAM on the 512GB Ultra). More aggressively, DuckDB has demonstrated all 22 TPC-H queries completing at **SF100000**, producing a **27TB final database**, using its larger-than-memory/out-of-core execution path ([DuckDB, 2025-10-09, medium confidence](https://duckdb.org/2025/10/09/benchmark-results-14-lts)). **This is a hard-ceiling flag, not just a benchmark**: 27TB exceeds the M5 Ultra's maximum 16TB internal SSD, so this exact benchmark could not be reproduced on a maxed-out Mac Studio as sold — it proves the *spill-to-disk technique* works, not that this box can hold that dataset. On the actual 16TB/512GB-RAM Ultra, expect DuckDB/Polars larger-than-memory execution to scale cleanly through the low-single-digit-TB range and then become progressively disk-bound (~6GB/s NVMe ceiling) as resident data climbs toward the 16TB SSD limit.

**Out of reach on this box:** working sets that exceed ~16TB of fast local storage, jobs needing concurrent large scans that saturate the single ~6GB/s SSD, or workloads requiring fault-tolerant multi-node execution — these need a cluster (§2).

---

## 2. Single node vs. cluster

**The case for replacing small Spark clusters:** a 2025 industry-consensus writeup puts the viable ceiling for single high-memory-node analytics at **up to ~1TB, "replacing Spark clusters"** ([pracdata.io, 2025-06-10, medium confidence, single article — directional, not a controlled benchmark](https://www.pracdata.io/p/the-rise-of-single-node-processing)). More concretely, DataFusion runs **2x faster than Spark when Spark is memory-constrained to 1GB**, and Spark needs **~3GB before it out-performs DataFusion** ([Medium/andymadson, 2026-01-20, medium confidence](https://medium.com/@andymadson/apache-datafusion-what-data-engineers-need-to-know-in-2026-3ad96f7157f6)) — the practical reading is that a lot of "small Spark clusters" in the wild are simply underprovisioned executors paying a JVM/shuffle tax for no benefit; a single generously-memoried box (128-512GB here) removes that tax outright. Separately, Pinterest reported **80%+ cost reduction** moving off long-running Hadoop/EMR clusters ([tech-insider.org, 2024-12-15, medium confidence](https://tech-insider.org/spark-vs-hadoop-2026/)) — note this is a Hadoop→Spark-on-cluster migration, not a cluster→single-node one, so it's adjacent evidence (organizations already fleeing always-on cluster cost) rather than direct proof; the source domain is low-profile and the claim should be treated cautiously.

**Where the cluster genuinely still wins:**
- **Capacity beyond the box:** datasets whose resident/working set exceeds ~16TB (or needs RAID/redundancy the Studio's fixed internal SSD doesn't provide) — see the 27TB DuckDB demo above.
- **Concurrency:** many simultaneous analysts/queries hit a hard ceiling at 36 CPU cores / 512GB RAM on one machine; a cluster scales cores and memory horizontally.
- **Fault tolerance:** multi-hour/multi-day jobs where losing the one machine loses all progress, vs. Spark's lineage-based recomputation across nodes.
- **Aggregate ingest bandwidth:** a cluster's combined NIC/disk bandwidth across nodes beats one machine's single 10GbE or TB5 uplink (see §3).

No evidence in the base is a controlled, identical-dataset **Mac Studio vs. live Spark cluster** bake-off — the single-node case rests on published TPC-H/ClickBench engine numbers and the memory-constrained-Spark comparison, not a head-to-head trial (gap).

---

## 3. Ingest reality check (the real bottleneck)

This is the sharpest limit on the whole "enterprise-in-a-box" pitch: the machine's *internal* paths are enormous — 512GB RAM at 1.2TB/s, 16TB SSD at **~6GB/s** (~48Gbps) — but nothing gets that data onto the box at anywhere near those speeds from outside.

- **Best-case LAN:** the built-in 10GbE port sustains **~9Gbps (~1.1GB/s) real-world**, not the theoretical 10Gbps ([ithy.com, 2025-04-20, medium confidence, informal source](https://ithy.com/article/mac-studio-networking-optimization-cjqs06i7)) — already ~5.5x slower than the local SSD and roughly three orders of magnitude slower than RAM bandwidth.
- **Typical home/ISP ceiling (2026 US median, Ookla-sourced):** **~300Mbps down / ~56Mbps up** on fixed broadband (medium confidence, aggregator summary of Ookla data).
- **Typical small-business fiber:** symmetric plans commonly **200-940Mbps**, priced $120-$400/mo for the 300Mbps-1Gbps range (medium confidence, industry roundup).

**Quantified:** pulling **1TB** from cloud storage —
- over median home broadband (300Mbps down): ≈ **7.4 hours**
- over a 940Mbps symmetric business fiber line: ≈ **2.4 hours**
- over the Studio's own 10GbE LAN port (9Gbps, i.e. data already on-prem): ≈ **15 minutes**

The WAN link is 10-30x slower than the machine's *own* network port, and that port is already the slowest interface on the box by a wide margin next to local NVMe or RAM. **Practical read:** this machine's ETL story is "excellent once the data is local, painful to keep fed live from the cloud." A nightly/off-hours bulk sync, or doing one heavy pull and iterating locally, is realistic; treating it as a live query engine directly over cloud object storage at interactive latency is not, given typical ISP ceilings — this argues for either co-locating the box on a fast pipe (office/colo fiber) or accepting batch-style ingest as the operating model.

---

## 4. Thunderbolt 5 RDMA multi-Mac clustering: claimed vs. proven

**Claimed (per fact base):** TB5 RDMA delivers **80Gbps with 3-9µs latency** ([Jeff Geerling, 2025-12-20, high confidence per source](https://www.jeffgeerling.com/blog/2025/15-tb-vram-on-mac-studio-rdma-over-thunderbolt-5/)), versus the ~300µs typical of conventional TCP/IP networking (secondary, via WebSearch summary — not independently re-fetched this session, see gaps). Coverage of the M5 Ultra launch (Apple Newsroom, MacRumors, AppleInsider, PopSci — all summarized via WebSearch; direct fetches were blocked by network egress policy this session, see gaps) reports that **four clustered Mac Studios can deliver up to 3x the inference throughput of a single machine**, with Thunderbolt 5 + RDMA creating a **shared memory pool across nodes** for running larger AI models.

**What's unproven for this chapter's purpose (ETL/analytics, not AI):** every claim and demo found targets **AI/LLM inference** — tensor/model-parallel weight sharing across GPU memory pools — not distributed data engines. There is **no evidence** in the fact base or supplemental search that DuckDB, Polars, DataFusion, or Spark has any RDMA-aware distributed execution mode for macOS, and no benchmark of TB5 RDMA under analytics-shaped access patterns (small random reads, shuffle-heavy joins) as opposed to the large, mostly-sequential tensor transfers AI inference favors. Public demos also cap at **four** nodes; scaling beyond that, and production/software maturity generally, is untested — this clustering capability launched alongside the M5 Ultra itself (August 2026), with no field track record yet.

**Bottom line:** treat TB5 RDMA clustering as a credible, narrow, AI-inference capability today — and as a speculative, unbuilt possibility for ETL/analytics scale-out. It is not currently a substitute for Spark-style horizontal scaling in this domain.

---

## 5. Hard ceilings, server-class comparison, and where the pitch holds or breaks

**Memory bandwidth vs. EPYC/DDR5:** Apple advertises **1.2TB/s** for the M5 Ultra (total SoC bandwidth, shared across CPU+GPU+Neural Engine). A single AMD EPYC (5th-gen "Turin," 12-channel DDR5) socket advertises **~576GB/s** theoretical peak, with real-world server testing (Fujitsu PRIMERGY, EPYC Genoa) landing closer to **~400GB/s** (supplemental WebSearch, medium confidence, secondary aggregator — not independently fetched). An unverified Hacker News comment pegs a single EPYC CPU at **460GB/s** vs. M3 Ultra's 819GB/s ([HN, low confidence, anecdotal](https://news.ycombinator.com/item?id=43268529)) — roughly consistent with the ~400-576GB/s range above, included only as a rough sanity check. **Important caveat:** this is not apples-to-apples — Apple's number is total unified-memory bandwidth shared by CPU, GPU, and NPU, while the EPYC figure is CPU-DRAM-channel bandwidth feeding CPU cores only. A CPU-bound DuckDB/Spark job on the Mac will not realize the full 1.2TB/s the way a GPU-heavy job might; no Apple-Silicon-specific CPU-only STREAM-style benchmark was found (gap) to say how much of that headline number a pure analytics workload actually gets.

**Core count vs. server-class:** the M5 Ultra's 36 CPU cores is the ceiling for this box. Server-class EPYC parts scale to 128-192 cores per socket (industry-standard spec, not separately sourced here) — for embarrassingly-parallel scan/aggregate workloads, a big EPYC server or even a modest cluster still out-parallelizes a single Mac Studio on raw core count, even where the Mac may be very competitive on a memory-bandwidth-per-core basis for memory-bound analytics.

**Storage ceiling:** 16TB internal NVMe at ~6GB/s (M5 Ultra) is the hard local-data limit — fixed, non-redundant, and not hot-swappable. Enterprise servers routinely offer far larger, RAID'd, expandable storage; once a dataset's on-disk footprint (not just its query-time working set) needs to exceed ~16TB or needs redundancy, that's the natural point to move to server-class storage regardless of compute headroom.

**Where "enterprise-in-a-box" holds:** single-analyst or small-team interactive analytics on data from a few GB up to the ~500GB-1TB range that fits comfortably in RAM, plus larger-than-memory batch jobs up to a few TB via NVMe spill. For this band, DuckDB/Polars/DataFusion on this hardware plausibly replace a small, chronically underprovisioned Spark cluster at far lower cost and operational overhead — directly backed by the TPC-H SF100/SF1000 numbers and the DataFusion-vs-constrained-Spark result above.

**Where it breaks:**
1. Working sets that exceed ~16TB or 512GB RAM by orders of magnitude (the 27TB DuckDB demo needs more disk than this box has).
2. Many concurrent users needing more aggregate cores/memory than one 36-core/512GB machine provides.
3. Feeding the box from the cloud faster than an overnight batch window (§3) — this is the limit most users hit *first*, before compute or storage.
4. Fault-tolerant, multi-day distributed jobs where a single node's failure must not lose progress.
5. True horizontal scale-out where the constraint is raw local disk capacity, not compute — the Studio's storage ceiling, not its CPU/RAM, is the actual wall here.

---

## Confidence & gaps

- **M5 Max core-count discrepancy (flagged per brief):** the verified envelope states **18-core CPU** for M5 Max, and this chapter uses that figure throughout. The source JSON as received, however, contains **no explicit "M5 Max CPU core count" fact** — it only has a **36-core** figure, which belongs to the **M5 Ultra**, plus two "M5 Max memory bandwidth (40-core **GPU** configuration)" entries that could be misread as a CPU core count. The specific "36-core in one line vs. 18-core in the summary" conflict described in the brief was **not reproducible from the JSON contents this agent received**; treat any external claim of "M5 Max = 36-core" as a conflation with the M5 Ultra CPU count or the 40-core *GPU* spec. Recommend re-checking whichever document originally contained that exact conflicting line.
- **No Apple-Silicon-native benchmark numbers exist in the evidence base.** All TPC-H/ClickBench/group-by figures (DuckDB, Polars, DataFusion) were measured on unspecified or cloud (`c6a.4xlarge`) hardware, not M-series chips. Applying them to M5 Max/Ultra performance is an **ESTIMATE/extrapolation**, not a direct measurement — a real gap for a hardware-specific capability atlas.
- **Single-source, medium/low-confidence figures used with caution:** 100M-row group-by (Medium/2nick2patel2), DuckDB-beats-Polars-at-1TB (confessionsofadataguy.com), 10GbE real-world throughput (ithy.com), 1TB single-node-consensus (pracdata.io), Pinterest migration figure (tech-insider.org — unusual domain, "2026" framing in a 2024-dated article), DataFusion-vs-Spark memory result (Medium/andymadson). None were independently replicated here.
- **TB5 RDMA clustering and EPYC/DDR5 bandwidth claims are secondary-sourced.** Direct WebFetch to apple.com, macrumors.com, appleinsider.com, ghacks.net, and jeffgeerling.com was **blocked by network egress policy** in this session; those claims rely on WebSearch's own summarization of those pages rather than this agent reading primary text. Re-verify before treating as final.
- **EPYC-vs-Apple bandwidth comparison is apples-to-oranges** (shared unified SoC bandwidth vs. CPU-only DDR5 channel bandwidth) — flagged in §5, not resolved; no CPU-only STREAM-equivalent benchmark for Apple Silicon was found.
- **ISP figures are national medians** (2026 US, Ookla-sourced via aggregator), useful for order-of-magnitude only — not a substitute for the specific line the box would actually sit behind.
- **Open questions:** (1) Apple-Silicon-native TPC-H/ClickBench numbers for M5 Max/Ultra; (2) a CPU-only memory-bandwidth benchmark on M5 Ultra to see how much of 1.2TB/s a pure DuckDB/Spark workload realizes; (3) whether any distributed analytics engine (Spark, Trino, DuckDB) ever gains TB5-RDMA-aware execution, vs. today's AI-inference-only demos; (4) primary-source confirmation of the exact Apple/MacRumors/AppleInsider clustering claims once egress access allows; (5) independent verification of the tech-insider.org and pracdata.io claims given their thin public track record.
