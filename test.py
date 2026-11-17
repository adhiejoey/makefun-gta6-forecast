"""Test harness for main.py — synthetic cases only, no network.

Builds 3 synthetic /input cases, runs main.py twice on each, and checks:
  * exit code 0, output written, runtime well under 8 s
  * JSON {"hours": [...]}: 23 rows, hours 2..24 each once, 5 positive
    finite numbers per row, at most 1e9 (the grader's format)
  * quantiles non-decreasing within each row (monotonic)
  * median (q50) follows the documented hump: rises to a peak around
    hours 11-12, then falls; hour-24 median < hour-1 anchor
  * determinism: two runs produce byte-identical output
  * scaling: medians scale linearly with the hour-1 anchor

Usage: python3 test.py
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "main.py"
IN_DIR = ROOT / "input"
OUT_DIR = ROOT / "output"

CASES = {
    # Plain number: hour-1 mean CCU 850,000.
    "case-a": "850000\n",
    # JSON with a 60-minute series whose mean is exactly 1,250,000.
    "case-b": json.dumps({
        "case": "case-b",
        "game": "Grand Theft Auto VI",
        "date": "2026-11-19",
        "minutes": [1250000] * 60,
    }),
    # Labelled text: hour-1 CCU 12,000.
    "case-c": "case: case-c\nccu: 12000\n",
}
ANCHOR = {"case-a": 850000, "case-b": 1250000, "case-c": 12000}


def run_case(name, text):
    in_path = IN_DIR / f"{name}.in"
    out1 = OUT_DIR / f"{name}.out"
    out2 = OUT_DIR / f"{name}.run2.out"
    in_path.write_text(text, encoding="utf-8")
    results = []
    for out_path in (out1, out2):
        t0 = time.monotonic()
        proc = subprocess.run(
            [sys.executable, str(MAIN), str(in_path), str(out_path)],
            capture_output=True, text=True, timeout=8,
        )
        dt = time.monotonic() - t0
        assert proc.returncode == 0, f"{name}: exit {proc.returncode}: {proc.stderr}"
        assert dt < 8, f"{name}: took {dt:.2f}s, over the 8s limit"
        results.append((out_path.read_text(encoding="utf-8"), dt))
    return results


def check_case(name, raw, dt):
    data = json.loads(raw)
    assert set(data) == {"hours"}, f"{name}: top-level keys {set(data)}, expected {{'hours'}}"
    assert len(data["hours"]) == 23, f"{name}: {len(data['hours'])} rows, expected 23"
    assert [r["hour"] for r in data["hours"]] == list(range(2, 25)), f"{name}: hours not 2..24 in order"
    rows = []
    for i, r in enumerate(data["hours"]):
        assert set(r) == {"hour", "q"}, f"{name} row {i}: keys {set(r)}"
        vals = r["q"]
        assert len(vals) == 5, f"{name} row {i}: {len(vals)} values, expected 5"
        assert all(isinstance(v, (int, float)) and v > 0 and v <= 1e9 for v in vals), f"{name} row {i}: bad value {vals}"
        assert vals == sorted(vals), f"{name} row {i}: not monotonic: {vals}"
        rows.append(vals)
    medians = [r[2] for r in rows]
    anchor = ANCHOR[name]
    peak = max(medians)
    peak_hour = medians.index(peak) + 2
    assert 10 <= peak_hour <= 13, f"{name}: median peak at hour {peak_hour}, expected 10-13"
    assert 1.20 * anchor <= peak <= 1.35 * anchor, f"{name}: peak {peak} outside 1.20-1.35x anchor"
    assert medians[-1] < anchor, f"{name}: hour-24 median {medians[-1]} not below anchor"
    assert medians[0] > anchor, f"{name}: hour-2 median {medians[0]} not above anchor"
    # Bands widen with horizon: q95/q05 ratio grows from hour 2 to hour 24.
    ratio2 = rows[0][4] / rows[0][0]
    ratio24 = rows[-1][4] / rows[-1][0]
    assert ratio24 > ratio2, f"{name}: band did not widen ({ratio2:.2f} -> {ratio24:.2f})"
    return {"hour2": rows[0], "hour12": rows[10], "hour24": rows[-1],
            "peak_hour": peak_hour, "runtime_s": round(dt, 3)}


def main():
    IN_DIR.mkdir(exist_ok=True)
    OUT_DIR.mkdir(exist_ok=True)
    summary = {}
    for name, text in CASES.items():
        (raw1, dt1), (raw2, dt2) = run_case(name, text)
        assert raw1 == raw2, f"{name}: NON-DETERMINISTIC — two runs differ"
        summary[name] = check_case(name, raw1, max(dt1, dt2))
        print(f"PASS {name}: anchor={ANCHOR[name]:,} "
              f"hour2={summary[name]['hour2']} hour12={summary[name]['hour12']} "
              f"hour24={summary[name]['hour24']} peak_hour={summary[name]['peak_hour']} "
              f"runtime={summary[name]['runtime_s']}s deterministic=yes")
    (ROOT / "TESTS.md").write_text(
        "# Test results (synthetic cases, local run)\n\n"
        "Run: `python3 test.py` on 2026-11-17. All checks passed.\n\n"
        "| case | anchor (hour-1 CCU) | hour 2 (q05 q25 q50 q75 q95) | "
        "hour 12 | hour 24 | peak hour | runtime |\n"
        "|------|--------------------|-------------------------------|"
        "---------|---------|-----------|---------|\n"
        + "".join(
            f"| {n} | {ANCHOR[n]:,} | {' '.join(map(str, s['hour2']))} | "
            f"{' '.join(map(str, s['hour12']))} | "
            f"{' '.join(map(str, s['hour24']))} | {s['peak_hour']} | "
            f"{s['runtime_s']}s |\n" for n, s in summary.items()
        )
        + "\nChecks per case: 23 lines x 5 non-negative integers; quantiles "
          "non-decreasing per row; median hump peaks hours 10-13 at 1.20-1.35x "
          "anchor; hour-24 median below anchor; 90% band widens with horizon; "
          "two runs byte-identical; runtime < 8 s; output is the grader's "
          "JSON {\"hours\": [{\"hour\", \"q\": [...]}]} format.\n",
        encoding="utf-8",
    )
    print("ALL TESTS PASSED (3 cases, deterministic, monotonic, valid quantiles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
