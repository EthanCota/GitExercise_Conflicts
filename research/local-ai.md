# Local AI / LLM Chapter — Mac Studio M5 Ultra as Enterprise-in-a-Box

**Bottom line up front:** An M5 Ultra (512GB) comfortably serves any dense 70B-class model at any quantization and 100–200B-class MoE models (Qwen3-235B-A22B-class) at Q4/Q8 with large context headroom. It can *hold* a DeepSeek-671B-class model at 4-bit (~372GB, ~140GB headroom) and run it at an estimated **mid-teens tok/s** generation — usable for batch/offline work, not for snappy interactive coding. It cannot comfortably hold a full 1T-parameter MoE (Kimi-K2-class) even at Q4 (~500GB, ~12GB headroom) on a single node. For agentic coding specifically, **prompt-processing (prefill) speed, not generation speed, is the binding constraint** — every agent turn re-sends a large context, and Apple-Silicon prefill throughput on huge models is 1–2 orders of magnitude below what a cloud API delivers. The sane architecture is hybrid: local for privacy-sensitive/high-volume/latency-tolerant work, cloud API for tight agentic loops and frontier reasoning.

Sources are inline as `[fact-file]` (from `research/facts/local-ai.json`, confidence as given) or `[web, <date/n.d.>]` (supplemental search this session — WebFetch was blocked for every candidate domain by the network egress proxy, so supplemental citations rely on WebSearch result snippets/synthesis rather than fetched full text; treated as lower-rigor than fact-file entries and flagged accordingly).

---

## 1. What runs at 128GB / 256GB / 512GB

### Measured/reported memory footprints (fact file)

| Model class | Precision | Footprint | Source |
|---|---|---|---|
| Llama-3 70B (dense) | FP16 | 140 GB | [fact-file, easecloud.io, 2026-01-15, high] |
| Llama-3 70B (dense) | Q8 | 70 GB | [fact-file, easecloud.io, 2026-01-15, high] |
| Llama-3 70B (dense) | Q4_K_M | 35–40 GB | [fact-file, sitepoint, 2026-02-01, high] |
| Llama-3.1 70B (dense) | AWQ INT4 | 35 GB | [fact-file, abhinand05/medium, 2024-12-01, high] |
| Qwen-72B (dense) | FP16 | 144 GB | [fact-file, willitrunai, 2026-04-10, medium] |
| Qwen-35B (dense) | Q4 | ~20 GB | [fact-file, compute-market, 2026-03-20, medium] |
| Qwen3-235B-A22B (MoE, ~22B active) | Q4_K_M | ~132–148 GB | [web, apxml.com/willitrunai.com, n.d. 2026, medium — MoE: all 235B expert params must reside in memory even though only 22B activate per token] |
| Qwen3-235B-A22B (MoE) | Q8_0 | ~190–212 GB (≈43% over Q4) | [web, spheron.network, n.d. 2026, medium] |
| DeepSeek R1 671B (MoE, ~37B active) | FP8 (native) | 671 GB (weights only) | [fact-file, hivenet.com, 2026-02-10, high] |
| DeepSeek R1 671B | AWQ 4-bit | 335 GB weights + 37 GB activated ≈ 372 GB | [fact-file, hivenet.com, 2026-02-10, medium] |
| DeepSeek R1 671B | "Q8_0" GGUF, 32K ctx, measured | 220 GB RAM in use | [fact-file, github/ollama#8667, 2026-01-15, medium] — likely a mixed/dynamic-precision quant, not naive 1 byte/param; see Confidence & gaps |
| Kimi K2 (1T total, 32B active MoE) | FP16 | ~2 TB (impractical) | [web, apxml.com, n.d. 2026, medium] |
| Kimi K2 | Native INT4 (QAT) | ~500 GB | [web, apxml.com/localaimaster, n.d. 2026, medium] |

### Headroom math (KV cache), worked example

KV cache size scales with **attention architecture**, not total context alone. For a GQA dense model like Llama-3-70B (80 layers, 8 KV heads, head_dim 128 — public architecture spec):

```
KV bytes/token = 2 (K&V) × 80 layers × 8 kv_heads × 128 head_dim × 2 bytes (fp16)
              = 327,680 bytes ≈ 0.31 MB/token
32K context  ≈ 10 GB
128K context ≈ 40 GB
```
(This is an analytical derivation from published architecture, not a sourced benchmark — flagged as calculated, not scouted.)

**Tier-by-tier:**

- **128GB (M5 Max)**: 70B dense at Q4/INT4 (35–40GB) leaves ~88–93GB free — enough for a full 128K-token KV cache (40GB) *and* OS/other models with room to spare. Q8 (70GB) leaves ~58GB, still comfortable. **FP16 70B (140GB) does not fit** — 128GB is a quantized-only tier for 70B-class. **100–200B MoE (Qwen3-235B-A22B) does not fit at any current quant** (min ~132GB at Q4) — this is the key ceiling of the 128GB tier.
- **256GB (M5 Ultra base config)**: 70B dense fits at *any* precision including FP16, with ~112–116GB headroom. Qwen3-235B-A22B MoE fits at Q4 with ~108–124GB headroom (large context viable); at Q8 it's tight (~44–66GB headroom, workable but constrained context). **DeepSeek-671B-class does not fit comfortably** — the AWQ-4bit footprint (372GB) exceeds 256GB outright, and the measured "Q8" config already consumed 220GB at only 32K context on a 256GB box [fact-file, github#8667] — near-zero headroom for anything larger.
- **512GB (M5 Ultra top config)**: DeepSeek-671B-class AWQ-4bit (372GB) fits with ~140GB headroom — enough for large context (128K ≈ 40GB scaled up for this architecture, likely less than the Llama calc above since DeepSeek uses Multi-head Latent Attention, not verified in our sources) plus OS/runtime. **Kimi-K2-class 1T MoE at Q4 (~500GB) is borderline** — only ~12GB headroom on a 512GB box, effectively no room for KV cache or a second process. This is the practical single-node ceiling.

**Net:** 512GB buys you from "70B, anything" up through "DeepSeek-671B-class at 4-bit, comfortably" — but a full 1T-parameter frontier MoE at usable quantization is *not* a comfortable single-node fit even at the top configuration.

---

## 2. Expected throughput

### Measured (label = chip generation)

| Model | Chip | Metric | Value | Source |
|---|---|---|---|---|
| Llama-3 70B Q4_K_M | **M4 Max** | generation | 12.5 tok/s | [fact-file, markaicode, 2024-11-01, medium] |
| Llama-3 70B Q4 | **M5 Max** | generation | 25–32 tok/s | [fact-file, localaimaster, 2026-08-20, medium] |
| Llama-3.3 70B | **M5 Max** | generation | 30+ tok/s | [fact-file, starmorph, 2026-07-10, medium] (corroborates the row above) |
| DeepSeek R1 671B Q4_K_M | **M3 Ultra** (512GB) | prompt processing | 189.5 tok/s | [fact-file, dev.to, 2025-05-28, medium] |
| DeepSeek R1 671B Q4_K_M | **M3 Ultra** (512GB) | generation | 11.15 tok/s | [fact-file, dev.to, 2025-05-28, medium] |
| Qwen3-235B-A22B | **M3 Ultra** (256GB) | generation | ~11.3 tok/s | [web, willitrunai.com, n.d. 2026, medium] |
| Kimi K2 1T (INT4, pipeline-parallel, 2 nodes) | **2× M3 Ultra** | generation | ~15 tok/s | [web, apxml.com/localaimaster (Awni Hannun experiment), n.d. 2026, low — per-node memory figure in source snippet looked internally inconsistent, treat number directionally only] |
| Kimi K2 Thinking 1T | **4× M3 Ultra, RDMA/TB5 cluster** | generation | ~25 tok/s | [web, runaihome.com, n.d. 2026, low-medium] |

### ESTIMATE — extrapolated to M5 Ultra (label = ESTIMATE, math shown)

M5 Ultra bandwidth = 1.2 TB/s [fact-file, fstoppers, 2026-08-25, high]. M3 Ultra bandwidth = 819 GB/s [fact-file, apple newsroom, 2025-03-12, high]. M5 Max high-end bandwidth = 614 GB/s [fact-file, apple.com/mac-studio/specs, 2026-08-25, high]. M5 Ultra peak-AI-compute uplift vs M3 Ultra = 4.3x [fact-file, engadget, 2026-08-25, high].

LLM inference has two distinct regimes: **decode (generation) is memory-bandwidth-bound**; **prefill (prompt processing) is compute-bound**. Scale each with the matching ratio:

- **DeepSeek-671B-class Q4 generation on M5 Ultra** (bandwidth-scaled from M3 Ultra):
  `11.15 tok/s × (1200/819 = 1.465x) ≈ 16.3 tok/s` — **ESTIMATE**
- **DeepSeek-671B-class Q4 prompt processing on M5 Ultra** — two bounding scenarios:
  - Conservative (bandwidth-scaled): `189.5 × 1.465 ≈ 278 tok/s` — **ESTIMATE**
  - Optimistic (compute-scaled, using the 4.3x peak-AI-compute figure, which bakes in the new per-GPU-core Neural Accelerators): `189.5 × 4.3 ≈ 815 tok/s` — **ESTIMATE, upper bound; real sustained matmul throughput on a specific model/framework will fall well short of a "peak compute" multiplier**
  - Working range: **~280–800 tok/s prefill, treat the low end as more credible** for a first-turn planning estimate.
- **Llama-3-70B Q4 generation on M5 Ultra** (bandwidth-scaled from M5 Max high-end): `25–32 tok/s × (1200/614 = 1.955x) ≈ 49–63 tok/s` — **ESTIMATE**. Caveat: Ultra chips are two Max dies joined by UltraFusion; cross-die synchronization overhead means decode throughput scaling with raw bandwidth ratio is an upper-bound assumption, not a guarantee — flagged as reasoning, not a sourced claim.

---

## 3. Quantization tradeoffs in practice

- **Q4 (Q4_K_M / AWQ-INT4) is the default "fits and runs" tier**: for Llama-3-70B it roughly halves memory vs Q8 (35–40GB vs 70GB) [fact-file, easecloud/sitepoint] with the AWQ INT4 variant landing at the same ~35GB [fact-file, abhinand05]. This is what makes 70B practical even on the 128GB M5 Max.
- **Q8 roughly doubles memory over Q4** (Qwen3-235B-A22B: Q8 is ~43% larger than Q4 per source figures, i.e. ~190–212GB vs ~132–148GB) [web, spheron.network] for a generally modest quality gain — the right choice only when there's headroom to spare (256GB+ tier) and quality matters more than context length.
- **FP16 is essentially a "256GB+ tier" precision** for 70B-class (140–144GB) [fact-file, easecloud/willitrunai] — rarely worth it over Q8 given the memory cost, unless benchmarking against a full-precision baseline.
- **Format matters as much as bit-width**: MLX-native quantized models run 30–40% faster than the equivalent llama.cpp/GGUF quant on M5-generation silicon [fact-file, yage.ai, 2026-03-31, medium], and Ollama itself moved its default backend from llama.cpp/Metal to MLX in v0.19+ [fact-file, yage.ai, 2026-03-30, high] — meaning mainstream tooling now defaults to the faster path, but older GGUF-based workflows/tutorials will understate real throughput.
- **Dynamic/mixed-precision quants can beat naive math**: the measured 671B "Q8_0" config using 220GB (not ~671GB) at 32K context [fact-file, github#8667] is well below a naive 1-byte/param estimate, consistent with mixed-precision ("dynamic quant") schemes that keep only sensitive layers at higher precision — useful in practice, but makes footprint planning from bit-width alone unreliable for MoE models; budget from measured numbers where available, not formulas.

---

## 4. Fine-tuning and serving

- **Fine-tuning**: MLX supports fine-tuning via CLI, Python, Swift, and C++ on Apple Silicon (M3+) [fact-file, kdnuggets, 2026-04-15, high]. No fact-file/search evidence was found on full-parameter fine-tuning of 70B+ models on a single node (memory cost of optimizer states makes this implausible without offload); treat fine-tuning capability as LoRA/adapter-scale, not full fine-tune of frontier-sized models, pending confirmation.
- **Multi-model serving**: MLX explicitly supports serving multiple models concurrently, including over Thunderbolt 5 [fact-file, kdnuggets, 2026-04-15, high] — relevant for an "enterprise-in-a-box" pitch (e.g., one small model for autocomplete + one large model for planning, resident simultaneously), and the 128GB-tier headroom math in §1 shows there's room to do this at the 70B-Q4 scale.
- **Distributed/multi-node**: macOS Tahoe 26.2 (Dec 2025) added RDMA over Thunderbolt 5, and EXO 1.0 shipped with RDMA support the same window [web, macfax.com/contracollective.com, n.d. 2026, medium — corroborated by 2+ independent write-ups]. A reported 4-node M3 Ultra cluster using RDMA-over-TB5 + EXO 1.0 held Kimi K2 Thinking (1T MoE) and ran it at ~25 tok/s, for a claimed all-in cost under $40K and 600–800W draw [web, runaihome.com, n.d. 2026, low-medium — single-source, treat cautiously]. Practical read for Ethan: clustering multiple Mac Studios is a real, documented option for models that exceed one node's memory (1T-class), but it adds real capex and complexity versus one $18,299 M5 Ultra — worth it only if the 1T-class tier is a hard requirement.

---

## 5. Claude Code stack: local, hybrid, or not

**Prompt-processing speed is the actual gate, not generation speed — address this directly:** Agentic coding sends a large, mostly-new prompt on *every* turn (system prompt + tool schemas + file contents + running transcript), while the useful output (a tool call, a diff) is often short. Perceived latency per turn ≈ `prefill_time(large, growing prompt) + decode_time(short output)`. This inverts the usual chat-benchmark framing where generation tok/s dominates.

- On DeepSeek-671B-class Q4 on M3 Ultra, measured prefill was 189.5 tok/s [fact-file, dev.to, 2025-05-28] — a 20K-token tool-heavy turn (a realistic size once file contents and prior turns are included) takes **~105 seconds just to process the prompt**, before any output starts. At the ESTIMATE'd M5 Ultra range (~280–800 tok/s prefill, §2), the same turn drops to roughly **25–70 seconds** — better, still slow for a tight iterate-run-fix loop.
- A separate data point, a hardware review of DeepSeek-671B on an M3-Ultra-class box via llama.cpp/GGUF, reported multi-minute waits before first token on a single query [web, hardware-corner.net-class headline, n.d., low-confidence, not independently re-verified — flagged, not load-bearing] — directionally consistent with the prefill-bound framing above, and a reminder that backend choice (MLX vs. GGUF/llama.cpp, §3) swings this by the reported 30–40%+ factor.
- Generation-side, 25–63 tok/s (measured M5 Max, ESTIMATE'd M5 Ultra for 70B-class, §2) is workable for short-to-medium completions but noticeably slower than a cloud API for long code generations; 11–16 tok/s (measured/ESTIMATE'd for 671B-class) is sluggish for anything interactive.

**Sensible hybrid split for Ethan's stack:**
- **Local (M5 Ultra)**: bulk/offline work where latency doesn't compound across many turns — repo-wide semantic search and embeddings, first-pass static review/linting over a large codebase, batch documentation generation, RAG index building, and any task touching code that must not leave the premises. Also good for keeping a small model resident for autocomplete/inline suggestions alongside a large model for occasional deep queries (multi-model serving, §4).
- **Cloud API (current Claude Code stack)**: the actual agentic loop — multi-step tool-use where each turn's prefill cost compounds, architecture/refactor planning, and anything where turnaround time matters to a human waiting on the loop. This is where the prefill-bound math above argues hardest against a local-only setup today.
- Re-evaluate the split as MLX/EXO software matures and as M5 Ultra-specific (not extrapolated) prefill benchmarks appear — the 4.3x peak-AI-compute figure [fact-file, engadget] suggests real headroom on the prefill side that isn't reflected in any measured-on-M5-Ultra number yet (gap, see below).

---

## 6. Hard ceilings + nearest server-class equivalent

**Hard ceiling of the top M5 Ultra config (512GB, $18,299):** a full 1T-parameter frontier MoE (Kimi-K2-class) at native INT4 QAT (~500GB) [web, apxml.com] leaves only ~12GB headroom — not a usable single-node config once KV cache and OS overhead are counted. Full-precision flagship weights (DeepSeek-V3/R1 671B FP8 at 671GB [fact-file, hivenet.com]; Kimi K2 FP16 at ~2TB [web, apxml.com]) don't fit at all on any Apple Silicon single node available or announced.

**Nearest server-class equivalents:**
- **For 70B-class INT4 serving** (the M5 Ultra's comfortable zone): a single Nvidia H100 80GB suffices, at roughly $2.5–5/GPU-hr cloud rental [web, spheron.network / generic H100 pricing sources, n.d. 2026, medium] — this is *cheaper per-hour* than owning the Mac outright for occasional use, but the Mac wins on privacy, zero marginal cost at high utilization, and no data leaving the building.
- **For DeepSeek-671B/Kimi-K2-1T-class FP8, comfortably**: practical VRAM need is ~700GB+ once KV cache/activations are counted, which exceeds 8×H100 80GB (640GB total) — the standard config is **8×H200 141GB (1,128GB total)** or a multi-node split with CPU offload [web, theriseunion.com / spheron.network, n.d. 2026, medium]. H200 pricing: ~$30K/chip to buy, or ~$10/GPU-hr cloud (~$80/hr, ~$58K/month for 8 GPUs) [web, modal.com, n.d. 2026, medium]. That's a **>$240K capex** or a **five-figure-per-month** cloud bill for full-fidelity serving of the model class the M5 Ultra can only just barely hold at 4-bit.
- **Raw memory bandwidth gap**: H100 SXM5 = 3.35 TB/s, H200 = 4.8 TB/s [web, runpod.io/cudocompute.com, n.d. 2026, medium] vs. M5 Ultra's 1.2 TB/s [fact-file, fstoppers] — datacenter GPUs retain a ~3–4x per-chip bandwidth advantage, which is why cloud/server decode throughput on the same quantized model will still meaningfully outpace even the ESTIMATE'd M5 Ultra numbers in §2, at metered cost instead of a fixed capex.

**Reading for the lease decision:** the M5 Ultra's real value is not "beats a GPU cluster on raw speed" — it doesn't — but "owns the 70B–~250B MoE band outright, at fixed cost, on-prem, with no per-token bill," while the 671B-and-above band is a "can hold it, can't serve it briskly" capability, not a production one.

---

## Confidence & gaps

- **High confidence**: all Apple hardware specs (bandwidth, memory tiers, pricing) — Apple's own spec pages/newsroom plus corroborated tech press [fact-file, multiple high-confidence entries]. Llama-3-70B memory footprints across precisions — multiple independent, high-confidence sources agree.
- **Medium confidence, single-or-thin-sourced**: M5 Max/M3 Ultra tok/s numbers (2–3 independent write-ups per figure, directionally consistent but none are controlled benchmarks with disclosed methodology). Qwen3-235B-A22B and Kimi K2 figures pulled from this session's supplemental web search are synthesis-of-search-snippets, not fetched primary text (**every WebFetch attempt in this task was blocked by the network egress proxy** — see caveat below) — treat as corroborating direction, not precise numbers.
- **Low confidence, explicitly flagged in-line**: the M3 Ultra "80+ tok/s" MLX 8-bit figure (unclear which model) [fact-file, sitepoint, low]; the 2×M3 Ultra Kimi-K2 pipeline-parallel figure (internally inconsistent per-node memory number in the source); the 4-node RDMA cluster cost/throughput claim (single source); MLX speculative-decoding 18.3 tok/s figure (single low-confidence source, unclear chip) [fact-file, medium.com, low].
- **Gap — no M5-Ultra-specific measured benchmarks exist yet** (hardware ships Sept–Oct 2026 per brief): every M5 Ultra throughput number in §2 is this analyst's ESTIMATE via bandwidth/compute-ratio scaling from M3 Ultra and M5 Max data, not a direct measurement. Re-run this analysis once real M5 Ultra tok/s benchmarks (ideally MLX-backend, both prefill and decode, on 70B/235B/671B classes) are published.
- **Gap — no direct prompt-processing/prefill benchmark exists for M5 Max or M5 Ultra** on any model size; §5's agentic-coding argument leans on a single M3 Ultra DeepSeek-R1 data point plus the general prefill-is-compute-bound framing. This is the single most decision-relevant number missing for the Claude-Code-local question and should be the first thing re-checked against real hardware.
- **Gap — fine-tuning at scale**: no evidence found (fact file or supplemental) on whether full-parameter fine-tuning of a 70B+ model is practical on a single Mac Studio, only that MLX supports fine-tuning tooling generically; assume LoRA/adapter-scale only until shown otherwise.
- **Process caveat**: WebFetch was blocked for every domain attempted in this session's supplemental research (macrumors.com, runaihome.com, modal.com, theriseunion.com, runpod.io, spheron.network, petronellatech.com — all returned `EGRESS_BLOCKED`). All supplemental facts therefore come from WebSearch's built-in result synthesis rather than this analyst reading primary source text directly — a materially weaker evidence standard than the fact-file entries, and worth a second pass with working fetch access if this chapter needs to support a large financial decision.
