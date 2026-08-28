# Signature Analysis — Synthesis Report

Run: 2026-08-28 · 2 Sonnet agents (algorithmic pipeline + visual examiner) · Artifacts in this directory
Inputs: iPhone Photos-app screenshot (1206×2622), signature in upper third, marker on light substrate.

## Verdict (per-claim confidence — claims at ≥95% marked ✓)

| Claim | Finding | Confidence |
|---|---|---|
| First name reads "Sara" | Fully legible, both agents agree, all four letters articulated | ✓ ≥95% |
| Surname opening | "Lor-" (capital ambiguous L/J), then 1–2 unarticulated humps | ~70–80% |
| Full surname | NOT RECOVERABLE — collapses into an unbroken terminal thread after 3–4 letters; Loren/Loran/Lorna/Jorem all consistent | Cannot reach 95%; refused |
| Writing instrument | Felt-tip/marker (uniform width, blunt terminals, stroke-width CV 0.39) | ✓ ≥95% |
| Image is a Photos-app screenshot | UI chrome + embedded EXIF `UserComment: Screenshot`, `DateTimeOriginal 2026-08-27T18:58:14`, no GPS/camera data | ✓ ≥95% |
| "Folsom Area / Today 9:35 AM" | Rendered pixels describing the *underlying* photo; not embedded metadata; original photo's EXIF does not survive screenshotting | ✓ ≥95% |
| Slant | 25.5° forward (right) of vertical, shear-search over ±45° | Direction ✓; magnitude ±few degrees (medium) |
| Baseline | Rises left→right at −4.6° (descender-excluded lower-envelope regression) | Medium-low (heuristic-sensitive) |
| Pen lifts | 3 connected components: "Sara" run, "Lor…"+loop+thread run, one stray tail | Medium (threshold-sensitive) |
| Dominant enclosure | One descender/flourish loop, ~29,100 px², eccentricity 0.935; measurably thinner-stroked than the letters → behaves like an added flourish, though positionally compatible with a J-descender | High for identification; interpretation moderate |
| Economy of stroke | Skeleton length / bbox diagonal = 3.50; terminal simplification into a thread — characteristic of a practiced, rapid signature | Medium (descriptive) |
| OCR | tesseract 5.3.4, 5 PSM modes: all garbage (best "Sore" @67%). Real result — general OCR models fail on connected cursive | ✓ (that it failed) ≥95% |
| Adjacent text | Second partial line reads "…nful"; top line not transcribable | Moderate / none |

## Out of scope, by evidence not by effort

- **Identity**: reading the written name is the limit; identifying the individual is neither possible nor appropriate.
- **Authenticity/forgery**: forensic signature examination is comparative — no known exemplars exist here, so no genuine/forged opinion is possible at any confidence.
- **Personality (graphology)**: no scientific validity; the writing is described, the writer is not.
- **Cryptography**: not applicable — nothing here is encrypted or signed cryptographically.

## Environment notes

- All analysis libraries were installed from a bare python3.11 env (numpy 2.4.6, opencv-headless 5.0.0, scikit-image 0.26.0, scipy 1.17.1, pytesseract 0.3.13, tesseract-ocr 5.3.4 via apt) — nothing blocked.
- `Project.ipynb` ("the libraries in my code") imports only numpy + matplotlib for a sine-wave demo; nothing signature-relevant existed to load.

## What would improve the answer

Original photo instead of a screenshot (true stroke edges, EXIF); a scale reference (physical units); a handwriting-specific recognizer or de-slanted re-OCR using the measured 25.5°; and, for any authenticity question ever, known exemplars.

## Artifact map

`analyze_signature.py` (pipeline), `metrics.json` (all measurements + raw OCR), `source.png`, `crop.png`, `binary.png`, `skeleton.png`, `overlay.png` (bbox/baseline/slant annotated), `ocr_input.png`, `visual-exam.md` (transcription, letterforms, provenance detail).
