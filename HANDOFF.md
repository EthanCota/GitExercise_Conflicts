# HANDOFF — Apple M-Series Capability Atlas (2026-08-28)

Successor handoff for a completed, single-session research run. This is the
entry point — read this first, then dip into `research/` as needed.

## 1. What this is + how to read it

Mission: build an evidence-backed capability atlas for the max-tier Apple
Silicon machines that went on preorder 2026-08-25 (Mac Studio M5 Ultra / M5
Max; MacBook Pro 16" M5 Max, already shipping) against a MacBook Air M4
baseline, ending in a lease-vs-alternatives decision packet for Ethan
(ethan.b.cota@gmail.com). The run is done; nothing here is in progress.

Artifact map (`research/`), one line each:

- `gate0-verification.md` — premise check: confirms the Aug 25 2026 launch, prices, and RAM/storage ceilings before any analysis started.
- `specs.json` — machine-readable spec sheet for all candidate Macs + the Air baseline; every field tagged with its extraction method and confidence.
- `fetch_report.json` — raw log of the deterministic spec-scraper's 8 attempted apple.com fetches, all proxy-blocked (403 at CONNECT).
- `finance.md` — lease/financing/cloud-rental cost comparison; the "$200/mo, 6-month lease" premise check.
- `baseline-delta.md` — MacBook Air M4 vs. each candidate: category shifts (things the Air categorically can't do) vs. degree shifts (same task, faster).
- `local-ai.md`, `databases.md`, `web-scraping.md`, `video-editing.md`, `agentic-automation.md`, `account-provisioning.md`, `data-at-scale.md` — the 7 domain chapters, each with a verdict, worked numbers, confidence/gaps, and sources.
- `synthesis.md` — cross-domain roll-up: verdict table, the capacity-bound-vs-permission-bound pattern, chassis comparison, top uncertainties, decision packet.
- `facts/*.json`, `raw_fetch/` — per-domain scout fact files and raw search artifacts underlying the chapters above.
- `scripts/extract_specs.py` — the deterministic spec-extraction script (ran, extracted 0 fields — see §3).

Read order for a fast catch-up: this file → `synthesis.md` → `finance.md` →
`baseline-delta.md` → whichever domain chapter matches the question at hand.

## 2. Verified premise & spec snapshot

Gate 0 (Haiku web scout, high confidence, corroborated across 3+ dated
press/primary sources per claim) confirmed:

- Mac mini M6 (Apple's first 2nm chip) + Mac Studio M5 Max/M5 Ultra announced 2026-08-25; preorders open in 30 countries; deliveries begin 2026-09-22.
- Mac Studio M5 Ultra: 36-core CPU / 80-core GPU, from $5,499; base Studio (M5 Max): 18-core/40-core, from $2,499.
- **Ceiling is 512GB RAM / 16TB SSD (M5 Ultra)** — corrects an earlier "2TB/256GB" handoff assumption, which is NOT the true ceiling.
- **The 512GB RAM tier ships late October 2026 and is unpriced** (only the 256GB/16TB config, at $18,299, is a real published number for the top end; press guesses of ">$20,000" for 512GB are unverified).
- No M6 Pro / M6 Max chips exist and none are planned for this generation — Apple skips straight to M7 (mid-2027, see §6).
- MacBook Pro 16" M5 Max is a March-2026 chip generation, already shipping today (not part of the Aug 25 announcement), $3,899–$7,349.

## 3. Method & provenance

Swarm shape: orchestrator + parallel Haiku "scout" agents (Phase A, one per
domain → `research/facts/<domain>.json`) → Sonnet domain analysts (Phase B →
`research/<domain>.md`) + a Sonnet finance track and Sonnet M4-Air comparator
→ Sonnet synthesis (Phase C, Opus reserved for evidence conflicts, none
arose) → this handoff. Full plan-spec is in `gate0-verification.md` §"Gate 1".

**Egress limitation (structural, applies to the whole run):**
`apple.com` and `support.apple.com` were rejected at the proxy CONNECT layer
(HTTP 403, organization policy) for every one of 8 targets attempted by the
deterministic script — see `fetch_report.json` for the raw denial log. A
wider set of secondary sources (appleinsider.com, macworld.com,
tomsguide.com, notebookcheck.net, pugetsystems.com, forums.macrumors.com, and
others) were also `EGRESS_BLOCKED` under `WebFetch` throughout the domain
chapters. As a result:

- `scripts/extract_specs.py` **ran successfully but extracted 0 fields** — it reached zero live targets. This is a network-policy outcome, not a script bug.
- Every field in `specs.json` and every fact in `research/facts/*.json` is tagged `extraction_method: "llm-parse"` — recovered via `WebSearch` (which is Anthropic-hosted and not subject to this sandbox's egress allowlist) synthesizing indexed Apple Newsroom/press content, not by parsing fetched primary HTML.
- Practical consequence: prices/specs are high-confidence (3+ independent press corroborations each), but anything requiring a live configurator page — notably the M5 Max Studio max-config price and the 512GB M5 Ultra price — could not be resolved and are flagged as open questions (§5) rather than guessed.
- **Rerunning `scripts/extract_specs.py` from a network without the apple.com block would resolve these null prices deterministically** — this is the single highest-value low-effort re-run action available to a successor.
- Every claim of substance is cited in-file (chapter "Sources" sections; `specs.json` field-level `extraction_method`/confidence; `baseline-delta.md`'s numbered footnotes). No claim in this handoff introduces a number not already sourced in `research/`.

## 4. Key findings (10 lines)

1. Verdict splits cleanly on one axis: hardware helps when the limiting resource is bytes in one coherent memory pool (local LLM weights, in-RAM DB/analytics, 8K video frames) and does nothing when the limit is someone else's permission (site rate limits, vendor API quotas, Claude Code's own concurrency cap).
2. Local LLM inference: PARTIAL — 512GB lets the M5 Ultra *hold* a 671B-class model at 4-bit (~140GB headroom) but only serves it at mid-teens tok/s; the 70B–~250B MoE band is owned outright at fixed cost.
3. Databases: PARTIAL — ~1M-TPS-class pgbench extrapolation and 400GB+ in-RAM datasets are real, but **no ECC RAM is a structural, unfixable disqualifier** for durability-critical production OLTP at every tier, Air through Ultra.
4. Web scraping, account/IdP provisioning, and cloud-API agent-swarm concurrency all BREAK — their ceilings are external (site politeness/IP reputation, AWS STS 600 req/s, Kubernetes' 110–250 pods/node, Claude Code's own 16-agent cap) and identical on a $6/month VM.
5. Video editing HOLDS on ProRes-native workflows; only loses to RTX GPUs (up to 149% faster, prior-gen measured) on GPU-effects-heavy stacks (Fusion, denoise).
6. Data-at-scale: PARTIAL, replaces a small Spark cluster up to ~1–3TB, but WAN ingest bandwidth is usually the first wall hit, before the 16TB/36-core hardware ceiling is the second.
7. **No matching lease product exists**: no program anywhere (Apple or third-party) offers a 6-month Mac Studio lease at ~$200/month. Shortest real Mac Studio lease term found is 24 months (Apple Business Financing/CIT, no published rate); Apple's own shortest fixed-term consumer product is Apple Upgrade at 24 or 36 months.
8. Apple Upgrade (Klarna-backed, launched 2026-07-28) 36-month rates: base M5 Max ≈$48.99/mo, base M5 Ultra $110.10/mo, max-published M5 Ultra (256GB/16TB, $18,299) $398.91/mo — $200/mo lands mid-pack between real quoted numbers, not on any actual price point.
9. The domain split doubles as the finance frame: hardware-unlocked (capacity-bound) workloads are where a Studio purchase substitutes for real infrastructure spend (H100 server, EPYC DB box, RTX NLE workstation); external-limit (permission-bound) workloads make the Studio functionally equivalent to a $6/month cloud shell — the finance case only holds for the former set.
10. The "$258/year" figure in Ethan's framing matches nothing found (not AppleCare+, not Apple Upgrade/ACMI, not a standard AI-subscription price) — likely contamination from an unrelated Aug 25 2026 Forbes/Yahoo piece framing "$200/month" as an AI-coding-subscription cost, not a lease payment. Flagged for Ethan directly (§5).

## 5. Open questions & unverifiables

Consolidated from every chapter's own gaps section — nothing below was
guessed past; each is a genuine hole in available evidence as of 2026-08-28.

1. **No independent M5 benchmarks exist for anything yet** (ships 2026-09-22 for 256GB configs, late Oct for 512GB) — every Studio-specific number in every chapter (pgbench TPS, tok/s, 8K stream counts) is either Apple's own marketing claim or an extrapolation from M3 Ultra/M4 Max data. First real numbers should appear from Puget Systems / Blackmagic forums / independent labs shortly after Sept 22.
2. **Prefill/TTFT for agentic loops is the single most decision-relevant unmeasured number.** Decode speed is fine on Apple Silicon; agentic coding is prefill-bound (large, mostly-new prompt every turn), and no M5 Max/Ultra prefill benchmark exists anywhere — this is the number that would most directly tell Ethan whether a local Claude-Code-style loop becomes viable (`local-ai.md` §5).
3. **512GB M5 Ultra price** — unannounced by Apple; ships late October 2026; press guesses (">$20,000") are not real quotes.
4. **M5 Max Studio max-config price (128GB/8TB)** — unpublished by Apple; the $7,299 figure used anywhere in `finance.md` is an unverified extrapolation, not a quote. Directly resolvable by re-running `scripts/extract_specs.py` from unblocked egress.
5. **Non-ECC incident rates are structural/analogical, not measured** — no Apple-Silicon-specific or Postgres/MySQL-specific silent-corruption study exists; the risk case rests on general SRAM soft-error research (ECC cuts risk ~1000x), not on this hardware.
6. **Current Anthropic API rate-limit figures by account tier** are not sourced in this run — needed to put a hard number on cloud-API swarm ceilings instead of the qualitative "software cap binds first" finding.
7. **The "$258/year" figure is unresolved** — ask Ethan directly where it originated before using it in any further analysis (`finance.md` Open Questions #5).
8. Secondary gaps worth knowing about but lower-priority: whether TB5-RDMA clustering ever gains a distributed-analytics execution mode (proven today only for AI-inference weight-sharing); Apple's uncorroborated 33-stream 8K ProRes claim (~3.7x above the only independent multi-stream measurement found, on prior-gen hardware); Apple Upgrade's 24-month Mac Studio rate (never located, only 36-month figures exist); Mac Studio-specific resale retention data (all found figures are MacBook-derived proxies).

## 6. Successor task A — re-run triggers

Re-open this atlas (not necessarily a full re-run) when any of these land:

- **After 2026-09-22** — independent M5 Max/Ultra benchmarks (pgbench, tok/s, prefill/TTFT, Resolve stream counts) should start appearing from Puget Systems, Blackmagic forums, and hardware review outlets once 256GB-tier units ship. This is the single highest-value trigger — it directly resolves open question #2 above.
- **After late October 2026** — the 512GB M5 Ultra tier ships and Apple should publish its price, closing open question #3 and letting `finance.md`'s TCO tables use a real number instead of a placeholder.
- **At the M7 generation (mid-2027)** — note explicitly: **there is no M6 Pro/M6 Max generation; Apple skips it entirely**, going straight from M5 Max/Ultra (Aug 2026) to M7 Max/Ultra. Do not schedule an "M6 Pro/Max" re-check — it will never exist. The next real capability jump for this decision is the M7 launch.
- Opportunistic trigger: if apple.com/support.apple.com egress is ever unblocked in a future session, immediately re-run `scripts/extract_specs.py` — it is fully built and tested, it simply had zero reachable targets in this session.

## 7. Successor task B — Claude Code stack migration plan skeleton (not a commitment)

If Ethan acquires one of these machines, here is what the atlas implies for
migrating (part of) his Claude Code stack onto it. This is a **plan
skeleton for a future session to flesh out**, not a decision made here — no
purchase, lease application, or migration was initiated in this run.

- **Hybrid local/cloud split** (`local-ai.md` §5): keep the actual agentic loop — multi-step tool-use, architecture/refactor planning, anything a human is waiting on — on the cloud API, because prefill cost compounds every turn and no local M5 hardware beats it yet (open question #2 above governs when/if this flips). Move to local: repo-wide semantic search/embeddings, first-pass static review/linting, batch doc generation, RAG index building, and any code that must not leave the premises.
- **Backend choice**: MLX outperforms Ollama/llama.cpp/GGUF backends on this hardware by a documented ~93% decode-speed factor in one measured case (`local-ai.md` §3) — any local serving experiment should default to MLX, not a generic GGUF runtime.
- **The 16-agent cap**: Claude Code's own concurrency ceiling is `min(16, cpu_cores − 2)` — the $5,499 Ultra buys essentially zero extra swarm concurrency over the $2,499 Max for cloud-API agent fan-out (`synthesis.md` §1, `baseline-delta.md` §4). Don't budget for "more parallel agents" as a reason to buy the bigger chassis.
- **Real payoff is coexistence, not more swarm**: CI runners (6 concurrent self-hosted GitHub Actions runners measured on one Mac), a container/VM fleet, and a resident local fallback model can all live on one always-on box alongside the cloud-API workflow (`synthesis.md` §1, `agentic-automation.md`).
- **2-VM limit and container isolation path**: flagged in `account-provisioning.md` (Podman-on-macOS runs containers inside a Linux VM, not natively — density figures for "100–500+ containers" are Linux-host numbers and do not directly transfer to a macOS host; this needs its own verification pass before being load-bearing for an isolation design). A migration plan should test actual container density on the target macOS host rather than assuming Linux-host figures apply.
- Next steps for whoever picks this up: (1) once Sept 22 benchmarks land, re-check the prefill number before finalizing any local/cloud line; (2) prototype the MLX-backed local fallback model path first, since it's the lowest-risk, highest-confidence piece; (3) treat the CI-runner and container-density plans as needing their own measured pilot on real M5 hardware, not extrapolation.

## 8. Dates, source authority, and session provenance

- Research conducted and dated: **2026-08-28**, single session.
- Source authority order used throughout: Apple Newsroom / apple.com (when reachable) > dated tech press with 3+ independent corroborations (MacRumors, 9to5Mac, AppleInsider, Macworld, Tom's Hardware) > single-source press/blog (flagged low/medium confidence in-line) > WebSearch-synthesized snippets standing in for blocked WebFetch (flagged as `llm-parse`, weakest tier, always disclosed). No claim above the lowest tier is used without an in-file confidence flag.
- Branch: `claude/apple-m-series-capability-atlas-8qd72w`.
