# Gate 0 — Premise Verification (PASSED)

Verified: 2026-08-28, via web scout (Haiku). All claims confirmed against dated primary/press sources.

## Verdict

| Claim | Verdict | Confidence |
|---|---|---|
| Mac mini M6 (first 2nm Apple chip) announced Aug 25, 2026 | TRUE | High |
| Mac Studio M5 Max / M5 Ultra announced concurrently | TRUE | High |
| Preorders open in 30 countries | TRUE | High |
| Deliveries begin Sept 22, 2026 | TRUE | High |
| Mac Studio M5 Ultra from $5,499; base Studio (M5 Max) from $2,499 | TRUE | High |
| No M6 Pro / M6 Max chips | TRUE | High |
| No M6 MacBook | PARTIAL — an M6 (base) MacBook Pro is expected late 2026, not on preorder now; no M6 Pro/Max MacBook exists | High |

## Confirmed max-tier envelope (supersedes handoff assumptions)

| Chassis | Chip | CPU / GPU | Max RAM | Max SSD | Price |
|---|---|---|---|---|---|
| Mac Studio | M5 Ultra | 36-core / 80-core | **512GB** (512GB configs ship late Oct; 256GB ships Sept 22) | **16TB** | $5,499 base; $18,299 at 256GB/16TB; 512GB pricing TBD |
| Mac Studio | M5 Max | 18-core / 40-core | 128GB | 8TB | $2,499 base; max-config price TBD |
| Mac mini | M5 Pro | 18-core / 20-core | 64GB | 8TB | $1,699 base; ~$4,699 est. max |
| Mac mini | M6 | 12-core / 12-core | 32GB | 2TB | $899 base; $2,229 max |

Handoff correction: "2TB storage + 256GB unified memory" is NOT the ceiling — real ceiling is 512GB/16TB (M5 Ultra).

## Key sources (dated)

- apple.com/newsroom 2026/08 — Mac mini M6+M5 Pro announcement; Mac Studio M5 Max+M5 Ultra announcement (Aug 25, 2026)
- macrumors.com 2026/08/25 — 2026 Mac mini announcement, prices
- appleinsider.com 26/08/25 — $18,299 for 256GB/16TB M5 Ultra; 512GB late October
- macworld.com — M5 Ultra up to 512GB RAM
- notebookcheck.net — 16TB max storage confirmation
- macrumors.com 2026/07/12 — no M6 Pro/Max generation (skipped to M7, mid-2027)
- 9to5mac.com 2026/08/25 — three Macs this fall; M6 MacBook Pro expected October

## Open questions carried forward

1. Max-config price for M5 Max Studio (128GB/8TB) — spec track.
2. Is a MacBook Pro M5 Max purchasable today (laptop path of the atlas)? — spec track.
3. 512GB/16TB M5 Ultra final price — unannounced by Apple.
4. List of the 30 preorder countries — not needed for decision; dropped unless requested.

## Gate 1 — Plan-spec (APPROVED by orchestrator, 2026-08-28)

Phase A (parallel): 7 Haiku domain scouts → `research/facts/<domain>.json`; 1 Sonnet deterministic spec extractor → `scripts/extract_specs.py` + `research/specs.json`; 1 Sonnet finance track → `research/finance.md`.
Phase B (parallel): Sonnet analysts per domain → `research/<domain>.md`; Sonnet M4-Air comparator → `research/baseline-delta.md`.
Phase C: synthesis (Opus only if evidence conflicts), gates 2–3, decision packet, HANDOFF.md.
