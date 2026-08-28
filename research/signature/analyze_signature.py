#!/usr/bin/env python3
"""
Algorithmic feature extraction on a handwritten signature crop from an
iPhone Photos screenshot.

Pipeline:
  1. Load source.png, locate the signature row-band via a near-black
     ink-density profile (naturally rejects the mid-gray, low-saturation
     iPhone UI pill/buttons and any stray writing outside the band).
  2. Crop, grayscale, adaptive-threshold to a binary ink mask.
  3. Compute geometry / stroke / slant / baseline / loop / skeleton metrics.
  4. Save overlay.png, binary.png, skeleton.png.
  5. Attempt OCR with pytesseract across several PSM modes, verbatim.

All numeric results are written to metrics.json.
"""
import json
import math
import sys

import cv2
import numpy as np
from skimage.morphology import skeletonize

try:
    import pytesseract
    from pytesseract import Output as TessOutput
    HAVE_TESS = True
except Exception as e:  # pragma: no cover
    HAVE_TESS = False
    TESS_IMPORT_ERROR = repr(e)

WORKDIR = "/home/user/GitExercise_Conflicts/research/signature"
SRC = f"{WORKDIR}/source.png"

metrics = {}


# ---------------------------------------------------------------------------
# 1. Load + locate signature band by ink-density profile
# ---------------------------------------------------------------------------
bgr = cv2.imread(SRC, cv2.IMREAD_COLOR)
if bgr is None:
    print(f"FATAL: could not load {SRC}", file=sys.stderr)
    sys.exit(1)

H, W = bgr.shape[:2]
metrics["source_image"] = {"width": W, "height": H}

gray_full = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
hsv_full = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
sat_full = hsv_full[:, :, 1]

# "Ink" = near-black pixels. The UI pill/buttons are mid-gray with low
# saturation and much higher value (~130-190) than marker ink (~20-90), and
# pill text is white-on-gray -- neither registers under a strict dark
# threshold. We still add an explicit low-saturation gray-blob guard (as
# requested) so any near-gray rounded-rect UI chrome is masked out even if
# its value happened to dip into the ink range.
DARK_THRESH = 110
GRAY_LOW_SAT_MAX = 40      # low-saturation ("gray") ceiling
GRAY_VAL_LO, GRAY_VAL_HI = 100, 210  # iOS translucent pill/button value band

dark_mask_full = (gray_full < DARK_THRESH).astype(np.uint8)
ui_gray_mask = (
    (sat_full < GRAY_LOW_SAT_MAX)
    & (gray_full >= GRAY_VAL_LO)
    & (gray_full <= GRAY_VAL_HI)
).astype(np.uint8)
# dilate the gray-UI guard slightly so it fully swallows anti-aliased pill edges
ui_gray_mask = cv2.dilate(ui_gray_mask, np.ones((5, 5), np.uint8))
dark_mask_full = dark_mask_full & (1 - ui_gray_mask)

row_density = dark_mask_full.sum(axis=1).astype(np.float64)

# Search only within a candidate vertical window (per task spec ~15%-35%,
# widened for safety) so we don't accidentally lock onto the partial line
# of writing at the very top of the frame.
search_top = int(0.10 * H)
search_bot = int(0.42 * H)
window = row_density[search_top:search_bot]
peak = window.max() if window.max() > 0 else 1.0
active_rows = np.where(window > 0.04 * peak)[0]
if len(active_rows) == 0:
    print("FATAL: no ink found in candidate signature band", file=sys.stderr)
    sys.exit(1)

pad = 12
band_top = max(0, search_top + active_rows.min() - pad)
band_bot = min(H, search_top + active_rows.max() + pad)

# Column extent within that row band (full width minus a small margin, since
# the trailing flourish is cut off at the frame edge in this screenshot).
col_density = dark_mask_full[band_top:band_bot, :].sum(axis=0).astype(np.float64)
cpeak = col_density.max() if col_density.max() > 0 else 1.0
active_cols = np.where(col_density > 0.02 * cpeak)[0]
cpad = 8
band_left = max(0, active_cols.min() - cpad)
band_right = min(W, active_cols.max() + cpad)

crop = bgr[band_top:band_bot, band_left:band_right].copy()
metrics["crop_region_in_source_px"] = {
    "top": int(band_top), "bottom": int(band_bot),
    "left": int(band_left), "right": int(band_right),
    "top_pct_of_height": round(100 * band_top / H, 2),
    "bottom_pct_of_height": round(100 * band_bot / H, 2),
}

cv2.imwrite(f"{WORKDIR}/crop.png", crop)


# ---------------------------------------------------------------------------
# 2. Grayscale + adaptive threshold -> binary ink mask
# ---------------------------------------------------------------------------
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
gray_blur = cv2.GaussianBlur(gray, (3, 3), 0)

adap = cv2.adaptiveThreshold(
    gray_blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
    blockSize=35, C=10,
)

# Guard against residual low-saturation gray UI fragments inside the crop.
hsv_c = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
sat_c = hsv_c[:, :, 1]
gray_guard = ((sat_c < GRAY_LOW_SAT_MAX) & (gray >= GRAY_VAL_LO) & (gray <= GRAY_VAL_HI)).astype(np.uint8) * 255
adap[gray_guard > 0] = 0

# Morphological cleanup: close small gaps in strokes, then drop specks
# (photo grain / paper texture) below an area threshold.
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
closed = cv2.morphologyEx(adap, cv2.MORPH_CLOSE, kernel, iterations=1)

n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(closed, connectivity=8)
MIN_COMPONENT_AREA = 12
clean = np.zeros_like(closed)
kept_components = 0
for lbl in range(1, n_labels):
    area = stats[lbl, cv2.CC_STAT_AREA]
    if area >= MIN_COMPONENT_AREA:
        clean[labels == lbl] = 255
        kept_components += 1

binary = clean  # 255 = ink, 0 = background
cv2.imwrite(f"{WORKDIR}/binary.png", binary)

ink_mask = binary > 0
ys, xs = np.where(ink_mask)
if len(xs) == 0:
    print("FATAL: binary mask empty after thresholding", file=sys.stderr)
    sys.exit(1)

x_min, x_max = int(xs.min()), int(xs.max())
y_min, y_max = int(ys.min()), int(ys.max())
bbox_w = x_max - x_min + 1
bbox_h = y_max - y_min + 1
bbox_area = bbox_w * bbox_h
ink_count = int(ink_mask.sum())

metrics["geometry"] = {
    "bbox_x_min": x_min, "bbox_x_max": x_max,
    "bbox_y_min": y_min, "bbox_y_max": y_max,
    "bbox_width_px": bbox_w, "bbox_height_px": bbox_h,
    "aspect_ratio_w_over_h": round(bbox_w / bbox_h, 4),
    "ink_pixel_count": ink_count,
    "bbox_area_px": bbox_area,
    "ink_density_in_bbox": round(ink_count / bbox_area, 5),
    "connected_components": kept_components,
}


# ---------------------------------------------------------------------------
# 3a. Stroke width via distance transform
# ---------------------------------------------------------------------------
dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
skel = skeletonize(ink_mask)
cv2.imwrite(f"{WORKDIR}/skeleton.png", (skel.astype(np.uint8) * 255))

skel_widths = 2.0 * dist[skel]  # local stroke width at each skeleton pixel
if skel_widths.size == 0:
    sw_mean = sw_std = sw_cv = float("nan")
else:
    sw_mean = float(skel_widths.mean())
    sw_std = float(skel_widths.std())
    sw_cv = float(sw_std / sw_mean) if sw_mean > 0 else float("nan")

metrics["stroke_width_px"] = {
    "mean": round(sw_mean, 3),
    "std": round(sw_std, 3),
    "coefficient_of_variation": round(sw_cv, 4),
    "n_skeleton_px_sampled": int(skel_widths.size),
}


# ---------------------------------------------------------------------------
# 3b. Slant via shear-search (maximize vertical-stroke concentration)
# ---------------------------------------------------------------------------
def sheared_column_score(mask_u8, theta_deg):
    """Shear the binary mask horizontally by theta (deg from vertical) and
    score how tightly ink concentrates into narrow vertical strokes -- the
    correct de-slant angle maximizes sum(column_density**2)."""
    h, w = mask_u8.shape
    shear = math.tan(math.radians(theta_deg))
    M = np.array([[1, shear, -shear * h / 2.0], [0, 1, 0]], dtype=np.float64)
    extra_w = int(abs(shear) * h) + 2
    out_w = w + extra_w
    sheared = cv2.warpAffine(
        mask_u8, M, (out_w, h), flags=cv2.INTER_NEAREST, borderValue=0
    )
    col_sum = (sheared > 0).sum(axis=0).astype(np.float64)
    return float((col_sum ** 2).sum())


angles = np.arange(-45.0, 45.01, 0.5)
scores = [sheared_column_score(binary, a) for a in angles]
best_idx = int(np.argmax(scores))
slant_deg_from_vertical = float(angles[best_idx])

metrics["slant"] = {
    "method": "shear-search maximizing vertical-projection concentration",
    "degrees_from_vertical": round(slant_deg_from_vertical, 2),
    "sign_convention": "positive = top leans right (forward/right slant), "
                        "negative = backhand/left slant",
    "search_range_deg": [-45, 45],
    "search_step_deg": 0.5,
}


# ---------------------------------------------------------------------------
# 3c. Baseline angle via lower-envelope regression, excluding descender loop
# ---------------------------------------------------------------------------
n_cols = binary.shape[1]
lower_env = np.full(n_cols, np.nan)
for c in range(n_cols):
    col = np.where(ink_mask[:, c])[0]
    if col.size:
        lower_env[c] = col.max()

valid_cols = np.where(~np.isnan(lower_env))[0]
valid_y = lower_env[valid_cols]
med = float(np.median(valid_y))
sigma = float(valid_y.std())
keep = np.abs(valid_y - med) < 1.0 * sigma
fit_x = valid_cols[keep]
fit_y = valid_y[keep]

if len(fit_x) >= 2:
    slope, intercept = np.polyfit(fit_x, fit_y, 1)
    baseline_deg = float(math.degrees(math.atan(slope)))
else:
    slope, intercept = 0.0, med
    baseline_deg = 0.0

metrics["baseline"] = {
    "method": "linear regression of lower ink envelope per column, "
              "columns kept where |y - median| < 1 sigma (excludes the "
              "descender loop dip)",
    "slope_px_per_px": round(float(slope), 5),
    "intercept_px": round(float(intercept), 2),
    "angle_deg_from_horizontal": round(baseline_deg, 2),
    "n_columns_total": int(len(valid_x := valid_cols)),
    "n_columns_used_after_1sigma_filter": int(len(fit_x)),
}


# ---------------------------------------------------------------------------
# 3d. Loops / enclosures via contour hierarchy (holes)
# ---------------------------------------------------------------------------
contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
loops = []
if hierarchy is not None:
    hierarchy = hierarchy[0]
    for i, h in enumerate(hierarchy):
        parent = h[3]
        if parent != -1:  # this contour is a hole inside a stroke -> an enclosure
            area = cv2.contourArea(contours[i])
            if area < 3:
                continue
            entry = {"contour_index": i, "area_px": round(float(area), 1)}
            if len(contours[i]) >= 5:
                (ex, ey), (MA, ma), angle = cv2.fitEllipse(contours[i])
                major, minor = max(MA, ma), min(MA, ma)
                ecc = math.sqrt(1 - (minor / major) ** 2) if major > 0 else float("nan")
                entry.update({
                    "ellipse_center": [round(ex, 1), round(ey, 1)],
                    "ellipse_major_axis_px": round(major, 1),
                    "ellipse_minor_axis_px": round(minor, 1),
                    "eccentricity": round(ecc, 4),
                })
            loops.append(entry)

loops.sort(key=lambda d: d["area_px"], reverse=True)
largest_loop = loops[0] if loops else None

metrics["loops"] = {
    "count": len(loops),
    "all": loops,
    "largest_loop_is_descender": largest_loop,
}


# ---------------------------------------------------------------------------
# 3e. Skeleton length vs bounding-box diagonal (economy of stroke)
# ---------------------------------------------------------------------------
skel_pts = np.argwhere(skel)  # (row, col)
skel_set = set(map(tuple, skel_pts.tolist()))
neighbor_offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
total_edge_len = 0.0
for (r, c) in skel_set:
    for dr, dc in neighbor_offsets:
        rr, cc = r + dr, c + dc
        if (rr, cc) in skel_set:
            step = math.hypot(dr, dc)
            total_edge_len += step
skeleton_length_px = total_edge_len / 2.0  # each edge counted from both ends

diagonal_px = math.hypot(bbox_w, bbox_h)
metrics["stroke_economy"] = {
    "skeleton_length_px": round(skeleton_length_px, 1),
    "skeleton_pixel_count": int(len(skel_set)),
    "bbox_diagonal_px": round(diagonal_px, 2),
    "skeleton_length_over_diagonal": round(skeleton_length_px / diagonal_px, 3),
}


# ---------------------------------------------------------------------------
# 4. Annotated overlay
# ---------------------------------------------------------------------------
overlay = crop.copy()
cv2.rectangle(overlay, (x_min, y_min), (x_max, y_max), (0, 0, 255), 2)

# baseline fit line, drawn across the fitted x-range
bx0, bx1 = int(fit_x.min()), int(fit_x.max())
by0 = int(slope * bx0 + intercept)
by1 = int(slope * bx1 + intercept)
cv2.line(overlay, (bx0, by0), (bx1, by1), (0, 255, 0), 2)

# slant indicator: a short reference segment at the measured slant angle,
# anchored near the bounding-box left-top area
cx, cy = x_min + 40, y_min + 10
seg_len = 90
sdx = seg_len * math.sin(math.radians(slant_deg_from_vertical))
sdy = -seg_len * math.cos(math.radians(slant_deg_from_vertical))
cv2.arrowedLine(overlay, (int(cx), int(cy + seg_len)), (int(cx + sdx), int(cy + sdy + seg_len)),
                 (255, 0, 0), 2, tipLength=0.15)

cv2.putText(overlay, f"slant {slant_deg_from_vertical:.1f} deg", (x_min, max(15, y_min - 10)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1, cv2.LINE_AA)
cv2.putText(overlay, f"baseline {baseline_deg:.1f} deg", (x_min, y_max + 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

cv2.imwrite(f"{WORKDIR}/overlay.png", overlay)


# ---------------------------------------------------------------------------
# 5. OCR attempt
# ---------------------------------------------------------------------------
ocr_result = {}
if not HAVE_TESS:
    ocr_result["available"] = False
    ocr_result["reason"] = TESS_IMPORT_ERROR
else:
    try:
        tess_ver = str(pytesseract.get_tesseract_version())
        ocr_result["available"] = True
        ocr_result["tesseract_version"] = tess_ver

        # Preprocessed OCR input: black ink on white background, upscaled
        # (tesseract performs poorly on small/thin cursive strokes otherwise).
        ocr_input = 255 - binary  # invert: black text(0) on white(255)
        scale = 3
        ocr_input_big = cv2.resize(
            ocr_input, (ocr_input.shape[1] * scale, ocr_input.shape[0] * scale),
            interpolation=cv2.INTER_CUBIC,
        )
        cv2.imwrite(f"{WORKDIR}/ocr_input.png", ocr_input_big)

        psm_modes = [6, 7, 8, 11, 13]
        per_psm = {}
        for psm in psm_modes:
            cfg = f"--oem 3 --psm {psm}"
            try:
                text = pytesseract.image_to_string(ocr_input_big, config=cfg)
                data = pytesseract.image_to_data(
                    ocr_input_big, config=cfg, output_type=TessOutput.DICT
                )
                confs = [float(c) for c in data.get("conf", []) if c not in ("-1", -1)]
                mean_conf = round(sum(confs) / len(confs), 2) if confs else None
                per_psm[str(psm)] = {
                    "raw_text": text,
                    "raw_text_stripped": text.strip(),
                    "mean_word_confidence": mean_conf,
                    "word_confidences": confs,
                }
            except Exception as e:
                per_psm[str(psm)] = {"error": repr(e)}
        ocr_result["per_psm_mode"] = per_psm
    except Exception as e:
        ocr_result["available"] = False
        ocr_result["reason"] = f"tesseract binary/pytesseract call failed: {e!r}"

metrics["ocr"] = ocr_result


# ---------------------------------------------------------------------------
# Write metrics.json
# ---------------------------------------------------------------------------
with open(f"{WORKDIR}/metrics.json", "w") as f:
    json.dump(metrics, f, indent=2)

print("Done. Wrote metrics.json, crop.png, binary.png, skeleton.png, overlay.png")
print(json.dumps({k: metrics[k] for k in
                   ["geometry", "stroke_width_px", "slant", "baseline", "stroke_economy"]},
                  indent=2))
