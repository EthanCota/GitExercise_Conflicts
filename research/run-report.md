# Framework Run Report — Orchestrated Capability Atlas (First Test)

Run date: 2026-08-28 · Session: single, remote sandbox · Branch: `claude/apple-m-series-capability-atlas-8qd72w`
Written by the orchestrator (Fable) from run telemetry held only in orchestrator context — the one task in this run where delegation would have cost more than it saved (the brief would have been the work).

## 1. Executive summary

A 21-sub-agent research swarm produced a 13-artifact, fully cited capability atlas plus finance packet, decision packet, and successor handoff in **~20 minutes wall-clock** (first dispatch 00:46 → Gate 3 verdict ~01:06) and **~1.40M sub-agent tokens** (~$5–15 at current API list prices). All four gates passed. Zero Opus escalations (no evidence conflicts fired the trigger). The architecture's two load-bearing bets — filesystem-as-blackboard and event-driven pipelining — both paid off measurably. The weakest link is citation provenance under an egress-restricted sandbox: WebSearch-snippet sourcing with access-date/publication-date conflation, structurally verified but not adversarially verified.

## 2. Architecture as executed

```
Gate 0 (Haiku scout: premise verification, 87s)
  → Gate 1 (orchestrator plan-spec approval)
    → Phase A, 9-way parallel:
        7× Haiku domain scouts  → research/facts/<domain>.json
        1× Sonnet spec extractor → scripts/extract_specs.py + specs.json  (deterministic-first)
        1× Sonnet finance track  → finance.md  (scout+analyst fused, saved a round trip)
    → Phase B, event-driven (analyst dispatched on its scout's completion, no barrier):
        7× Sonnet domain analysts → research/<domain>.md
        1× Sonnet comparator (blocked only on specs.json) → baseline-delta.md
    → Phase C:
        1× Sonnet synthesis (reads all 11 artifacts) → synthesis.md
        ∥ 1× Haiku Gate-3 verifier + 1× Sonnet HANDOFF writer (parallel)
    → Fable decision packet (orchestrator, chat deliverable)
```

Key structural choices:
- **Blackboard pattern**: scouts wrote fact JSONs to the shared worktree; analysts read files, not orchestrator relays. Orchestrator context overhead stayed ≈150K tokens for 21 agents (~7K/agent), dominated by dispatch briefs + result summaries. This is the scaling enabler: context cost is O(agents), not O(agents × evidence volume).
- **Need-to-know briefs**: every sub-agent got mission/inputs/done-condition/return-shape/tier only. Return contract (result/evidence/confidence/open_questions, no narrative) was honored by all 21 agents.
- **Commit-at-gate + commit-per-landing** gave 13 durable checkpoints on the branch.

## 3. Telemetry

| Tier | Runs | Tokens | Tool calls | Token share | Role |
|---|---|---|---|---|---|
| Haiku | 9 | 443,849 | 223 | 31.6% | Gate-0 scout, 7 domain scouts, Gate-3 verifier |
| Sonnet | 12 | 959,689 | 207 | 68.4% | Spec, finance, 7 analysts, comparator, synthesis, HANDOFF |
| Opus | 0 | 0 | 0 | 0% | Trigger (evidence conflict) never fired |
| Fable | orchestrator only | ≈150K | ~25 | — | Gates, routing, packet |
| **Total** | **21** | **≈1.40M** | **~455** | | |

- **Wall clock**: ~20 min (00:46–01:06). Total agent compute ≈ 65 min (3,903 agent-seconds) → effective parallelism ≈ 3.3× average, 9× peak. vs. the handoff's 3–5h estimate: **9–15× under**.
- **Routing target**: 15–30% Haiku *runs* → actual 43% of runs / 31.6% of tokens. Overshoot in the cheap direction; lesson in §5.3.
- **Per-agent patterns**: scouts were tool-heavy (18–32 calls, search fan-out), analysts tool-light (8–16 calls) — direct evidence the scout→analyst split moved the retrieval burden to the cheap tier. Most expensive runs: synthesis 125K (read 11 files), comparator 100K (read 8), spec extractor 98K (40 tool calls fighting the proxy).
- **Cost estimate**: at list prices (Haiku ~$1–5/Mtok, Sonnet ~$3–15/Mtok blended in/out), the whole atlas cost **roughly $5–15**.

## 4. What worked (with evidence)

1. **Gate 0 verify-before-spend**: 39K tokens / 87s corrected the mission's spec assumptions before any swarm spend — real ceilings 512GB/16TB (not 256GB/2TB), confirmed no-M6-Pro/Max, and surfaced the 512GB-ships-late-October wrinkle that ended up gating the maxed-Ultra decision itself.
2. **Event-driven pipelining**: first analyst dispatched ~5 min into the run while 6 scouts were still out; Phase A and B overlapped almost completely. Barrier-sync would have roughly doubled wall clock.
3. **Cross-tier error correction emerged unprompted**: the Sonnet account-provisioning analyst caught and corrected a Haiku scout's factual error (Podman "no VM overhead" claim — Podman on macOS does run a lightweight VM), documented inline with citations both ways. The scout/analyst split functions as a two-pass review, not just a cost optimization.
4. **Escalation discipline held**: Opus budget was reserved for evidence conflicts; chapters converged, so it was never spent. The framework spent nothing on capability it didn't need.
5. **Convergent findings across independent agents**: seven separately-briefed analysts, unaware of each other, converged on the same capacity-bound vs. permission-bound split (below) — a useful internal-consistency signal, though brief-priming (each was asked where "enterprise-in-a-box" holds/breaks) means it is not a fully independent replication.

## 5. Failure modes & threats to validity

1. **Egress policy broke deterministic-first** — the most important finding. `extract_specs.py` ran and got HTTP 403 on 8/8 apple.com URLs (org proxy policy, logged in `fetch_report.json`); WebFetch was blocked on apple.com and most press/spec domains for *every* agent. Result: 100% of specs.json is llm-parse from WebSearch snippets, i.e. the framework silently degraded from primary-source scraping to search-snippet triangulation. Mitigated by per-field `extraction_method` tags — but sandbox network policy must be treated as a first-class design input, probed *before* choosing the script-vs-LLM path.
2. **Provenance date leakage**: many scout citations carry `2026-08-28` — the access date, not publication date. Fact-file schema conflated the two. Any downstream freshness reasoning over those dates is unsound. Fix: separate `published` / `retrieved` fields + a validator.
3. **Verification was structural, not adversarial**: the Gate-3 Haiku pass checked existence, JSON validity, citation counts, ESTIMATE labels, and cross-file spec consistency (all PASS) — it never re-derived any claim. Load-bearing single-source figures (456K TPS pgbench anchor, M5 Max 25–32 tok/s, $7,349 MacBook price) are labeled but unreplicated. Gate 2 enforced ≥2 sources per *domain*, not per *claim*.
4. **Routing quota expressed in the wrong unit**: "15–30% of runs on Haiku" is gameable and was overshot (43%) without consequence; token-share or dollar-share is the meaningful quota.
5. **Scout overlap**: the agentic-automation scout re-collected local-LLM facts (tok/s, bandwidth) already owned by the local-AI scout — duplicated retrieval spend from briefs sharing an implicit fact namespace. Fix: declare fact-file ownership in briefs.
6. **Shared-worktree commit races**: async agents writing files + a stop-hook forcing commits produced sweep commits ("nothing to commit" races, chapters landing under earlier commit messages). Harmless here because file ownership was disjoint by design; a collision hazard in general. Fix: per-agent worktrees or an orchestrator-owned commit queue.
7. **Un-auditable secondary sourcing**: for egress-blocked domains, agents could not fetch the pages they cite; several URLs are search-derived and unconfirmed. Recommend a post-hoc link audit from an unrestricted network before any high-stakes reuse.

## 6. Research output (compressed; full packet in chat, artifacts in `research/`)

- **Cross-cutting result**: the seven domains split cleanly into *capacity-bound* (local LLM 70B–671B band, ≤~1–3TB in-RAM analytics, ProRes-native 8K video — max-tier hardware genuinely unlocks these) and *permission-bound* (scraping, IaC/provisioning, cloud-API agent swarms — bound by API rate limits, IP reputation, politeness, and Claude Code's 16-agent cap; identical on a $6/mo VM).
- **Finance**: no 6-month lease exists anywhere; Apple Upgrade (36-mo) is $49/$110/$399 per month for base Max Studio / base Ultra / maxed Ultra; the "$200/mo, 6-month" framing traces to press coverage of AI-subscription replacement, not a lease product. "$258/yr" unresolved.
- **Recommendation**: M5 Max Studio ($2,499) unless the 512GB/671B-class category is specifically wanted — and that tier is late-October and unpriced, so a maxed-Ultra decision cannot be finalized yet.
- **Global caveat**: zero independent M5 benchmarks exist before Sept 22; every M5 performance figure is a labeled Apple claim or shown-math extrapolation.

## 7. Recommendations for v2

1. **Pre-flight egress probe** (one cheap script, ~seconds) before routing extraction tasks; would have saved the spec agent ~400s and 40 tool calls of proxy-fighting.
2. **Provenance schema v2**: `{claim, value, url, published, retrieved, method: script|fetch|search-snippet}` + deterministic validator at Gate 2; promote per-claim (not per-domain) source requirements for load-bearing figures.
3. **Adversarial verify tier**: after synthesis, extract the top-N decision-bearing claims and re-verify each with an independent agent — verify truth, not structure. Cost at this run's scale: ~3–5 Haiku runs.
4. **Quota in token/dollar share**, logged at dispatch; end-of-run audit becomes a diff, not a reconstruction.
5. **Fact-namespace ownership** declared in briefs to kill duplicate retrieval.
6. **Commit discipline**: orchestrator-owned commit queue or per-agent worktrees; hook-driven sweeps degrade commit semantics.
7. **Keep**: Gate 0 as designed; blackboard file passing; event-driven dispatch; fused scout+analyst for narrow topical tracks (finance); Opus-only-on-conflict.

## 8. Session provenance

Timeline (commit-anchored): Gate 0 pass 00:48:57 · Phase A facts complete 00:52:34 · finance 00:54:53 · chapters 00:55–01:00 · baseline-delta 01:00:37 · synthesis 01:03:15 · HANDOFF 01:04:56 · Gate 3 all-PASS ~01:06. Companion docs: `HANDOFF.md` (successor tasks + re-run triggers), `research/gate0-verification.md` (premise), `research/synthesis.md` (atlas verdicts).
