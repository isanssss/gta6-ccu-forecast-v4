"""gta6-twitch-ccu-forecast-01 entry: pooled launch-shape quantiles.

Model (all quantities measured locally against the kit's practice cases and a
leave-one-out pass over the comparables before this was written):

  * Every comparable launch in the case contributes its release-day curve as
    log-ratios to its own hour-1 print, r_h = ln(y_h / p1_c), per hour h.
  * Comparables whose research note reports an affirmative early-access
    period before the standard release are left out: their "release day" is
    really the fourth day of public play, so their day shape measures a
    different event. Mentions that are negated ("no early access") or that
    cover a campaign-only preview do not exclude a comparable.
  * The remaining pool is weighted by a Gaussian kernel on the log distance
    between the target's hour-1 print and each comparable's (bandwidth 0.9):
    launches of a similar size share an unlock-day shape.
  * Each hour's five quantiles are the weighted empirical quantiles of that
    hour's pooled log-ratios, with the spread around the pooled median scaled
    by 0.95. No normal fit anywhere: the tails are the pool's own tails.
  * If no comparable is usable, the forecast falls back to persistence with
    the house baseline's widening spread, so the output is always valid.

The program reads every <id>.in in $MAKEFUN_INPUT_DIR (else /input) and writes
<id>.out to $MAKEFUN_OUTPUT_DIR (else /output). Standard library only, no
network, fully deterministic.
"""

import json
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
HOURS = list(range(2, 25))
BANDWIDTH = 0.9
SPREAD = 0.95
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

EA_RE = re.compile(r"early[ -]access")
NEG_RE = re.compile(r"\b(no|not|never|without)\s*$")


def has_early_access(unlock_text: str) -> bool:
    """True when the note affirmatively reports early access before release."""
    t = (unlock_text or "").lower()
    for m in EA_RE.finditer(t):
        back = t[max(0, m.start() - 16):m.start()]
        if NEG_RE.search(back):
            continue  # "no early access", "not early access", ...
        if back.rstrip().endswith("campaign"):
            continue  # a campaign-only preview; launch day is still launch day
        return True
    return False


def parse_ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def day_buckets(comp: dict) -> dict:
    """Hour-of-release-day mean viewers per hour (1..24) from hourly points."""
    start = parse_ts(comp["day_start"])
    buckets = {}
    for p in comp.get("hourly") or []:
        try:
            t = parse_ts(p["from"])
            v = float(p["viewers"])
        except (KeyError, TypeError, ValueError):
            continue
        h = int((t - start).total_seconds() // 3600) + 1
        if 1 <= h <= 24:
            buckets.setdefault(h, []).append(v)
    return {h: sum(vs) / len(vs) for h, vs in buckets.items() if vs}


def wquantile(pairs: list, tau: float) -> float:
    """Weighted empirical quantile, midpoint plotting positions."""
    pairs = sorted(pairs)
    total = sum(w for _, w in pairs)
    if total <= 0:
        return pairs[0][0]
    cum = []
    acc = 0.0
    for v, w in pairs:
        acc += w
        cum.append((acc - w / 2) / total)
    if tau <= cum[0]:
        return pairs[0][0]
    if tau >= cum[-1]:
        return pairs[-1][0]
    for i in range(1, len(pairs)):
        if cum[i] >= tau:
            f = (tau - cum[i - 1]) / (cum[i] - cum[i - 1])
            return pairs[i - 1][0] + f * (pairs[i][0] - pairs[i - 1][0])
    return pairs[-1][0]


def baseline_row(p1: float, h: int) -> list:
    return [p1 * math.exp(z * 0.15 * math.sqrt(h - 1)) for z in Z]


def forecast_case(case: dict) -> dict:
    first = next((k for k in case.get("known") or [] if k.get("hour") == 1), None)
    p1 = max(1.0, float(first["viewers"])) if first else 1.0

    per_hour = {h: [] for h in HOURS}
    for comp in case.get("comparables") or []:
        if not isinstance(comp, dict) or has_early_access(comp.get("unlock")):
            continue
        try:
            day = day_buckets(comp)
        except (KeyError, TypeError, ValueError):
            continue  # one malformed comparable must never sink the case
        c1 = day.get(1)
        if not c1 or c1 <= 0:
            continue
        w = math.exp(-0.5 * (math.log(p1 / c1) / BANDWIDTH) ** 2)
        for h in HOURS:
            y = day.get(h)
            if y and y > 0:
                per_hour[h].append((math.log(y / c1), w))

    rows = []
    for row in sorted(case["forecast"], key=lambda r: r["hour"]):
        h = row["hour"]
        pairs = per_hour.get(h) or []
        if pairs:
            med = wquantile(pairs, 0.5)
            qs = [p1 * math.exp(med + SPREAD * (wquantile(pairs, t) - med)) for t in LEVELS]
        else:
            qs = baseline_row(p1, h)
        rows.append({"hour": h, "q": clean_quantiles(qs)})
    return {"hours": rows}


def clean_quantiles(qs: list) -> list:
    """Force the output contract: finite, non-decreasing, inside (0, 1e9],
    rounded to 2 decimals so two runs write identical bytes."""
    out = []
    prev = 0.0
    for q in qs:
        if not math.isfinite(q):
            q = prev if prev > 0 else 1.0
        q = round(min(max(q, prev, 0.01), 1e9), 2)
        q = max(q, prev)  # rounding may shave half a cent; stay non-decreasing
        out.append(q)
        prev = q
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
