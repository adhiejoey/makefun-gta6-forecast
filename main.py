"""GTA VI launch-day Twitch CCU forecaster.

Reads one case (the Twitch viewer count for "Grand Theft Auto VI" up to the
end of hour 1 of release day, 2026-11-19 UTC) and writes, for each of hours
2..24, five quantiles (5%, 25%, 50%, 75%, 95%) of that hour's mean CCU.

Usage (any of these work; the grader's form is the first):
    python3 main.py /input/<id>.in /output/<id>.out
    python3 main.py /input/<id>.in            # writes <id>.out next to it / to /output
    python3 main.py                            # scans /input/*.in, then input/*.in

Output: 23 lines, one per hour 2..24 in order, each line five
space-separated non-negative integers: q05 q25 q50 q75 q95.
No header, no hour column. Quantiles are non-decreasing within each row.

Input: accepted flexibly, because the bounty page states the case contents
(hour-1 count, plus everything recorded before it) but does not publish a
byte-level .in schema. Accepted forms:
  * JSON object: {"hour1": N} / {"hour_1": N} / {"first_hour_ccu": N} /
    {"ccu": N} / {"viewers": N} / {"count": N} / {"value": N}, or
    {"minutes": [60 minute reads]} (hour 1 = their mean), or
    {"hourly": [...]} (hour 1 = last value), or {"history": [[...], ...]}.
  * JSON array of numbers: a single number is hour 1; several numbers are
    minute reads (mean) if > 24 of them, otherwise hourly values (last one
    is hour 1).
  * Plain text: one number per line; the same rules apply. A leading
    non-numeric line (case id / label) is ignored. "key: value" / "key=value"
    lines are recognised for the keys above.

Model (see README.md for the full reasoning):
  * Anchor on hour 1: every forecast is a multiple of the observed hour-1
    mean CCU. No external data, no network, stdlib only, deterministic.
  * Median shape: a smooth launch-day hump. Hour 1 (00:00-01:00 UTC) is a
    low-traffic hour globally, so category viewership is expected to rise
    through the EU/US day to a modest peak (~1.28x hour 1 around hours
    11-12), then fall back as the US evening ends (~0.85x by hour 24).
    The hump is deliberately modest (max |log mult| ~ 0.25) so that, if
    the true day is flat or gently decaying, the median miss stays close
    to the flat house baseline instead of blowing up.
  * Uncertainty: lognormal bands. log-quantile spread sigma(h) grows
    linearly with horizon, sigma = 0.08 + 0.012 * (h - 1), so the 90%
    band widens from about +/-16% at hour 2 to about +/-56%/+80% at
    hour 24 (asymmetric in levels, symmetric in logs). Quantiles use the
    standard-normal z-values for 5/25/50/75/95%.
"""

import json
import math
import os
import sys
from pathlib import Path

QUANTILES = (0.05, 0.25, 0.50, 0.75, 0.95)
# Standard-normal quantiles for the levels above.
Z = (-1.6448536269514722, -0.6744897501960817, 0.0,
     0.6744897501960817, 1.6448536269514722)

# Median multiplier of hour-1 CCU for hours 2..24 (index 0 == hour 2).
MEDIAN_MULT = (
    1.02, 1.06, 1.10, 1.14, 1.18, 1.21, 1.24, 1.26, 1.27, 1.28,
    1.28, 1.27, 1.26, 1.24, 1.21, 1.18, 1.14, 1.10, 1.05, 1.00,
    0.95, 0.90, 0.85,
)

SIGMA0 = 0.08    # log-spread at hour 2 (h - 1 == 1 gives 0.092)
SIGMA_PER_HOUR = 0.012


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) \
        and math.isfinite(x)


def _hour1_from_numbers(nums):
    """Anchor hour-1 CCU from a flat list of numbers.

    One number: it is hour 1. Several: minute reads (>24 values) -> mean;
    otherwise hourly values -> last one is hour 1.
    """
    nums = [float(n) for n in nums if _is_number(n)]
    if not nums:
        return None
    if len(nums) == 1:
        return nums[0]
    if len(nums) > 24:
        return sum(nums) / len(nums)
    return nums[-1]


def _hour1_from_obj(obj):
    if _is_number(obj):
        return float(obj)
    if isinstance(obj, list):
        flat = []
        for item in obj:
            if _is_number(item):
                flat.append(item)
            elif isinstance(item, list):
                flat.extend([v for v in item if _is_number(v)])
        return _hour1_from_numbers(flat)
    if isinstance(obj, dict):
        for key in ("hour1", "hour_1", "first_hour", "first_hour_ccu",
                    "hour1_ccu", "ccu", "viewers", "viewer_count",
                    "count", "value", "mean_ccu", "ccu_hour1"):
            if key in obj:
                v = _hour1_from_obj(obj[key])
                if v is not None:
                    return v
        for key in ("minutes", "minute_ccu", "minute_reads"):
            if key in obj and isinstance(obj[key], list):
                vals = [v for v in obj[key] if _is_number(v)]
                if vals:
                    return sum(vals) / len(vals)
        for key in ("hourly", "hours", "series"):
            if key in obj:
                v = _hour1_from_obj(obj[key])
                if v is not None:
                    return v
        # Any other numeric field, in insertion order, as a last resort.
        for v in obj.values():
            got = _hour1_from_obj(v)
            if got is not None:
                return got
    return None


def parse_hour1(text):
    """Extract the hour-1 CCU from raw case text. Raises ValueError."""
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty input case")
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return _hour1_from_obj(json.loads(stripped))
        except (json.JSONDecodeError, ValueError):
            pass  # fall through to the text parser
    nums = []
    for line in stripped.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # "key: value" / "key = value" lines.
        for sep in (":", "="):
            if sep in line:
                head, _, tail = line.partition(sep)
                if head.strip().lower().replace(" ", "_") in (
                        "hour1", "hour_1", "first_hour", "first_hour_ccu",
                        "hour1_ccu", "ccu", "viewers", "viewer_count",
                        "count", "value", "mean_ccu", "ccu_hour1", "id",
                        "case"):
                    try:
                        nums.append(float(tail.strip().split()[0]))
                    except (ValueError, IndexError):
                        pass
                    break
        else:
            for token in line.replace(",", " ").split():
                try:
                    nums.append(float(token))
                except ValueError:
                    pass  # labels / case ids are ignored
    hour1 = _hour1_from_numbers(nums)
    if hour1 is None or hour1 <= 0:
        raise ValueError("no positive hour-1 viewer count found in input")
    return hour1


def forecast(hour1):
    """Return 23 rows (hours 2..24) of 5 integer quantiles each."""
    rows = []
    for i, mult in enumerate(MEDIAN_MULT):
        hour = i + 2
        sigma = SIGMA0 + SIGMA_PER_HOUR * (hour - 1)
        median = hour1 * mult
        log_med = math.log(median)
        row = []
        for z in Z:
            q = math.exp(log_med + sigma * z)
            row.append(max(0, int(round(q))))
        # Guarantee non-decreasing quantiles after rounding.
        for j in range(1, len(row)):
            row[j] = max(row[j], row[j - 1])
        rows.append(row)
    return rows


def find_input(argv):
    """Resolve (input_path, output_path) from argv / conventional dirs."""
    if len(argv) >= 3:
        return Path(argv[1]), Path(argv[2])
    if len(argv) == 2:
        inp = Path(argv[1])
        out = Path("/output") / (inp.stem + ".out")
        return inp, out
    for base in (Path("/input"), Path("input"), Path(".")):
        ins = sorted(base.glob("*.in")) if base.is_dir() else []
        if ins:
            inp = ins[0]
            out = (Path("/output") if Path("/input").is_dir()
                   else Path("output")) / (inp.stem + ".out")
            return inp, out
    raise SystemExit("usage: python3 main.py [/input/<id>.in [/output/<id>.out]]")


def main(argv):
    in_path, out_path = find_input(argv)
    text = in_path.read_text(encoding="utf-8")
    hour1 = parse_hour1(text)
    rows = forecast(hour1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "".join(" ".join(str(v) for v in row) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(f"hour1={hour1:g} -> {out_path} ({len(rows)} hours x 5 quantiles)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
