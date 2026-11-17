"""GTA VI launch-day Twitch CCU forecaster.

Reads one case (the Twitch viewer count for "Grand Theft Auto VI" up to the
end of hour 1 of release day, 2026-11-19 UTC) and forecasts hours 2..24 as
five quantiles each (5%, 25%, 50%, 75%, 95%).

Real case format (verified against the competition kit, 17 Nov 2026):
  * Input: JSON {"schema": "makefun/twitch-ccu-case/v1", "id", "game",
    "day_start", "checkpoint", "levels", "known", "forecast", "history",
    "history_hourly", "streams", "categories_hourly", "comparables",
    "notes"}, where "known" holds hour 1's print
    {hour: 1, from, until, viewers, channels, reads} and "forecast"
    lists the hours to forecast, 2..24.
  * Output: JSON {"hours": [{"hour": 2, "q": [q05, q25, q50, q75, q95]},
    ...]} — exactly 23 rows, hours 2..24 each once, no other key, each q
    five finite numbers above 0 and at most 1e9, non-decreasing, at most
    65,536 bytes. Quantiles are rounded to 2 decimals, half up (whole
    numbers written as ints), exactly like the kit's starter.

How the grader runs it: `python3 -P -s /bot/main.py`
(PYTHONHASHSEED=0) in python:3.13-slim, standard library only, no
network, no pip packages, with MAKEFUN_INPUT_DIR / MAKEFUN_OUTPUT_DIR
standing in for /input and /output outside the container. It runs one
case at a time, with only that case's file in the input directory.

Usage:
    python3 main.py                       # scans the input dir, writes
                                          # one .out per .in to the output dir
    python3 main.py /input/<id>.in       # writes <id>.out to the output dir
    python3 main.py /input/<id>.in /output/<id>.out   # single case, explicit

For local synthetic testing the parser also accepts the flexible forms
the first build used (a plain number, {"minutes": [...]}, {"hour1": N},
"labelled text", ...); those still produce the same JSON output format.

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
    band widens from about +/-16% at hour 2 to about -44%/+80% at
    hour 24. Quantiles use the standard-normal z-values for 5/25/50/75/95%.
"""

import json
import math
import os
import sys
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so an
# `import model` would find a model.py shipped beside this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

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

# Keys of the real case schema that must never be mistaken for the
# hour-1 print when falling back to a generic search: "levels" is the
# quantile levels (0.05..0.95) — mistaking its last value for hour 1
# was a real bug in the first build (hour1 read as 0.95 on the kit's
# practice cases); "comparables"/"history" are other games' curves.
_SKIP_KEYS = frozenset({
    "levels", "comparables", "forecast", "history", "history_hourly",
    "categories_hourly", "streams", "schema", "notes", "game", "id",
    "checkpoint", "day_start",
})


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) \
        and math.isfinite(x)


def round2(x):
    """x rounded to 2 decimals, half up, as the kit's starter rounds it.

    A whole number comes back as an int, so json.dumps writes 1240
    where JavaScript writes 1240 (not 1240.0).
    """
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


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


def _hour1_from_known(known):
    """Hour-1 print from the real schema's `known` list."""
    if not isinstance(known, list):
        return None
    first = None
    for row in known:
        if isinstance(row, dict) and _is_number(row.get("viewers")):
            if row.get("hour") == 1:
                return float(row["viewers"])
            if first is None:
                first = float(row["viewers"])
    return first


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
            elif isinstance(item, dict) and _is_number(item.get("viewers")):
                # e.g. a "known"-style row inside a list.
                flat.append(float(item["viewers"]))
        return _hour1_from_numbers(flat)
    if isinstance(obj, dict):
        # Real schema first: `known` holds hour 1's print.
        if "known" in obj:
            v = _hour1_from_known(obj["known"])
            if v is not None:
                return v
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
        # Any other numeric field, in insertion order, as a last resort —
        # but never the schema's descriptive fields (see _SKIP_KEYS).
        for k, v in obj.items():
            if k in _SKIP_KEYS:
                continue
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
            hour1 = _hour1_from_obj(json.loads(stripped))
            if hour1 is not None and hour1 > 0:
                return hour1
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


def forecast_hours(case):
    """Hours to forecast, from the real schema's `forecast` list."""
    if isinstance(case, dict) and isinstance(case.get("forecast"), list):
        hours = []
        for row in case["forecast"]:
            if isinstance(row, dict) and isinstance(row.get("hour"), int):
                hours.append(row["hour"])
        if hours:
            return sorted(hours)
    return list(range(2, 25))


def forecast(hour1, hours):
    """Return the {"hours": [...]} forecast object for the given hours."""
    rows = []
    for hour in hours:
        if not 2 <= hour <= 24:
            continue
        mult = MEDIAN_MULT[hour - 2]
        sigma = SIGMA0 + SIGMA_PER_HOUR * (hour - 1)
        median = hour1 * mult
        log_med = math.log(median)
        row = []
        for z in Z:
            q = math.exp(log_med + sigma * z)
            row.append(max(0, round2(q)))
        # Guarantee non-decreasing quantiles after rounding.
        for j in range(1, len(row)):
            row[j] = max(row[j], row[j - 1])
        rows.append({"hour": hour, "q": row})
    return {"hours": rows}


def parse_case(text):
    """Return (hour1, hours) for one raw case."""
    stripped = text.strip()
    case = None
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            case = json.loads(stripped)
        except json.JSONDecodeError:
            case = None
    hour1 = parse_hour1(text)
    hours = forecast_hours(case) if isinstance(case, dict) else list(range(2, 25))
    return max(1, hour1), hours


def default_dirs():
    """(input_dir, output_dir), honouring the kit's env vars."""
    in_dir = Path(os.environ.get("MAKEFUN_INPUT_DIR", ""))
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", ""))
    if not in_dir:
        in_dir = Path("/input") if Path("/input").is_dir() else Path("input")
    if not out_dir:
        out_dir = Path("/output") if Path("/input").is_dir() else Path("output")
    return in_dir, out_dir


def run_case(in_path, out_path):
    """Forecast one case file; returns (hour1, hours)."""
    text = in_path.read_text(encoding="utf-8")
    hour1, hours = parse_case(text)
    payload = forecast(hour1, hours)
    blob = json.dumps(payload, separators=(",", ":")) + "\n"
    assert len(blob.encode("utf-8")) <= 65536, "forecast exceeds 65,536 bytes"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(blob, encoding="utf-8")
    print(f"hour1={hour1:g} -> {out_path} ({len(payload['hours'])} hours x 5 quantiles)",
          file=sys.stderr)
    return hour1, hours


def main(argv):
    if len(argv) >= 3:
        run_case(Path(argv[1]), Path(argv[2]))
        return 0
    in_dir, out_dir = default_dirs()
    if len(argv) == 2:
        inp = Path(argv[1])
        run_case(inp, out_dir / (inp.stem + ".out"))
        return 0
    cases = sorted(in_dir.glob("*.in")) if in_dir.is_dir() else []
    if not cases:
        raise SystemExit(
            f"usage: python3 main.py [/input/<id>.in [/output/<id>.out]] "
            f"(no *.in found in {in_dir})")
    for inp in cases:
        run_case(inp, out_dir / (inp.stem + ".out"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
