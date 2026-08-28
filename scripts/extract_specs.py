#!/usr/bin/env python3
"""
extract_specs.py — Deterministic-first spec extraction for Apple hardware.

Strategy (script-first, LLM-parse only as fallback):
  1. Fetch each target Apple URL with requests, honoring HTTPS_PROXY and the
     CA bundle at /root/.ccr/ca-bundle.crt.
  2. Try to parse chip / core counts / memory / storage / price / ports out
     of the raw HTML (both visible text and any embedded JSON blobs Apple
     ships in <script> tags) using regexes — no JS execution.
  3. Record, per machine, which fields were actually recovered this way.
  4. Whatever could NOT be recovered script-side is left for a follow-up
     LLM-parse pass (done separately, outside this script, via WebFetch/
     WebSearch) and is written out with "source":"unresolved-by-script" so
     the follow-up step knows exactly what to fill in.

This script never fabricates a number. Anything it can't find in the
fetched HTML is left null with a note.
"""

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone

import requests

CA_BUNDLE = "/root/.ccr/ca-bundle.crt"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research")
RAW_DIR = os.path.join(OUT_DIR, "raw_fetch")
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

TARGETS = {
    "mac_studio": "https://www.apple.com/mac-studio/specs/",
    "mac_mini": "https://www.apple.com/mac-mini/specs/",
    "macbook_pro": "https://www.apple.com/macbook-pro/specs/",
    "macbook_air": "https://www.apple.com/macbook-air/specs/",
    "mac_studio_buy": "https://www.apple.com/shop/buy-mac/mac-studio",
    "mac_mini_buy": "https://www.apple.com/shop/buy-mac/mac-mini",
    "macbook_pro_buy": "https://www.apple.com/shop/buy-mac/macbook-pro",
    "macbook_air_buy": "https://www.apple.com/shop/buy-mac/macbook-air",
}


def fetch(url, retries=2, timeout=25):
    """Fetch a URL via requests, respecting HTTPS_PROXY / CA bundle."""
    proxies = None
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if https_proxy or http_proxy:
        proxies = {"https": https_proxy or http_proxy, "http": http_proxy or https_proxy}

    verify = CA_BUNDLE if os.path.exists(CA_BUNDLE) else True

    last_err = None
    for attempt in range(1, retries + 2):
        try:
            resp = requests.get(
                url,
                headers=HEADERS,
                proxies=proxies,
                verify=verify,
                timeout=timeout,
            )
            return {
                "url": url,
                "status": resp.status_code,
                "final_url": resp.url,
                "text": resp.text,
                "error": None,
            }
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1)
    return {
        "url": url,
        "status": None,
        "final_url": url,
        "text": "",
        "error": f"{type(last_err).__name__}: {last_err}",
    }


# ---------------------------------------------------------------------------
# Parsing helpers — all regex/text based, no JS execution.
# ---------------------------------------------------------------------------

CORE_RE = re.compile(r"(\d+)[‑\-\s]*core\s*(CPU|GPU|Neural Engine)", re.IGNORECASE)
CHIP_RE = re.compile(r"Apple\s+(M\d(?:\s?(?:Pro|Max|Ultra))?)", re.IGNORECASE)
MEM_OPT_RE = re.compile(r"\b(\d+)\s*GB\s+(?:unified memory|memory)\b", re.IGNORECASE)
BANDWIDTH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*GB/s\s+(?:of\s+)?memory bandwidth", re.IGNORECASE)
STORAGE_RE = re.compile(r"\b(\d+)\s*(TB|GB)\s+SSD\b", re.IGNORECASE)
PRICE_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)")


def strip_tags(html):
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", " ", text)
    return text


def extract_fields(html):
    """Best-effort regex extraction. Returns dict of field -> value/None,
    plus a `found` set naming which fields were actually recovered."""
    text = strip_tags(html)
    found = set()
    out = {}

    chips = sorted(set(m.group(1).strip() for m in CHIP_RE.finditer(text)))
    if chips:
        out["chips_mentioned"] = chips
        found.add("chip")

    cores = {}
    for m in CORE_RE.finditer(text):
        n, kind = int(m.group(1)), m.group(2).lower()
        cores.setdefault(kind, set()).add(n)
    if cores:
        out["cores_mentioned"] = {k: sorted(v) for k, v in cores.items()}
        if "cpu" in cores:
            found.add("cpu_cores")
        if "gpu" in cores:
            found.add("gpu_cores")
        if "neural engine" in cores:
            found.add("neural_engine")

    mem_opts = sorted(set(int(m.group(1)) for m in MEM_OPT_RE.finditer(text)))
    if mem_opts:
        out["memory_options_gb_mentioned"] = mem_opts
        found.add("memory_options")

    bw = sorted(set(float(m.group(1)) for m in BANDWIDTH_RE.finditer(text)))
    if bw:
        out["memory_bandwidth_gbs_mentioned"] = bw
        found.add("memory_bandwidth")

    storage = set()
    for m in STORAGE_RE.finditer(text):
        val, unit = int(m.group(1)), m.group(2).upper()
        storage.add(f"{val}{unit}")
    if storage:
        out["storage_mentioned"] = sorted(storage)
        found.add("storage")

    prices = sorted(set(m.group(1) for m in PRICE_RE.finditer(text)))
    if prices:
        out["prices_mentioned"] = prices
        found.add("price")

    return out, found


def looks_js_gated(html, status):
    if status is None:
        return True
    if status in (403, 405, 407, 429) or (status and status >= 500):
        return True
    if len(html) < 2000:
        return True
    # Apple's spec pages are largely server-rendered but shop config pages
    # are heavy client-side apps; detect near-empty content shells.
    text = strip_tags(html)
    if len(text) < 1500:
        return True
    return False


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    report = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "targets": {},
    }

    for name, url in TARGETS.items():
        print(f"[fetch] {name}: {url}", file=sys.stderr)
        result = fetch(url)
        raw_path = os.path.join(RAW_DIR, f"{name}.html")
        try:
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(result["text"] or "")
        except Exception as e:  # noqa: BLE001
            print(f"  ! could not write raw file: {e}", file=sys.stderr)

        entry = {
            "url": url,
            "final_url": result["final_url"],
            "status": result["status"],
            "fetch_error": result["error"],
            "bytes": len(result["text"] or ""),
        }

        if result["error"] or looks_js_gated(result["text"] or "", result["status"]):
            entry["script_extractable"] = False
            entry["reason"] = (
                result["error"]
                or f"status={result['status']}, content too short/empty (JS-rendered or blocked) "
                f"len={len(result['text'] or '')}"
            )
            entry["fields_found"] = []
            entry["parsed"] = {}
        else:
            parsed, found = extract_fields(result["text"])
            entry["script_extractable"] = bool(found)
            entry["fields_found"] = sorted(found)
            entry["parsed"] = parsed
            if not found:
                entry["reason"] = "page fetched but no recognizable spec patterns matched"

        report["targets"][name] = entry
        time.sleep(0.5)

    fetch_report_path = os.path.join(OUT_DIR, "fetch_report.json")
    with open(fetch_report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nWrote fetch report: {fetch_report_path}", file=sys.stderr)
    print(f"Raw HTML saved under: {RAW_DIR}", file=sys.stderr)

    n_ok = sum(1 for e in report["targets"].values() if e["script_extractable"])
    n_total = len(report["targets"])
    print(f"\nSummary: {n_ok}/{n_total} targets yielded script-extractable spec fields.", file=sys.stderr)
    for name, e in report["targets"].items():
        status = "OK" if e["script_extractable"] else "FALLBACK-NEEDED"
        print(f"  [{status}] {name} (status={e['status']}, bytes={e['bytes']}) -> {e.get('reason', e.get('fields_found'))}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
