# GTA VI Twitch CCU forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/adhiejoey/makefun-gta6-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/adhiejoey/makefun-gta6-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecast GTA VI's launch-day Twitch viewers hour by hour, built for
make.fun's **GTA VI Twitch CCU forecast** bounty
(`gta6-twitch-ccu-forecast-01`, $250, 20 places paid) —
https://make.fun/bounty/gta6-twitch-ccu-forecast-01.
Deadline: **Thu 19 Nov 2026 01:00 UTC / 08:00 WIB**. No entry fee.

---

<sub>Entered on [make.fun](https://make.fun/?ref=mcpf7r82&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>

## What it does

`main.py` (Python 3.13, standard library only, no network, deterministic)
reads one case — the Twitch viewer count for the "Grand Theft Auto VI"
category up to the end of hour 1 of release day, 2026-11-19 (UTC) — and
forecasts hours 2–24 as five quantiles each (5%, 25%, 50%, 75%, 95%).

Run it:

```sh
python3 main.py            # scans the input dir, writes one .out per .in
# or: python3 main.py /input/<id>.in /output/<id>.out
```

Input: JSON `{"schema": "makefun/twitch-ccu-case/v1", ...}` — `known`
holds hour 1's print `{hour: 1, viewers, ...}` and `forecast` lists the
hours to forecast, 2–24. Output: JSON
`{"hours": [{"hour": 2, "q": [q05, q25, q50, q75, q95]}, ...]}` — exactly
23 rows, hours 2..24 each once, each q five positive finite numbers
(≤ 1e9), non-decreasing, rounded to 2 decimals half up. Runs in well
under 1 s on 1 CPU. Outside the grader's container,
`MAKEFUN_INPUT_DIR` / `MAKEFUN_OUTPUT_DIR` stand in for `/input` and
`/output`.

## Spec confirmed from the bounty page and the kit (17 Nov 2026)

- Task: forecast mean Twitch CCU per hour, hours 2–24 of 2026-11-19 (UTC),
  from everything recorded before the cut plus the hour-1 count. An hour's
  count is the mean of that hour's minute reads.
- Score: **pinball loss on the log scale**; lowest wins. A forecast whose
  five quantiles are equal scores exactly its mean miss in log terms, so
  accuracy plus an honest spread wins. Ties broken by the faster program.
- Reward bar: a reward needs a **lower loss than the best house entry**.
  House baseline: every hour stays at the hour-1 count, with a spread that
  widens over the day. There is also a house AI-model forecast.
- Practice: before the deadline every entry is scored on past big launches'
  release days; after the deadline the final runs as a race, scored hour by
  hour, graded on the whole recorded day. Final case is cut at the deadline.
- Limits: stdlib + vendored source only, nothing installed, no network,
  deterministic (two runs on the same case write the same forecast),
  ≤ 8 s, 1 CPU, 1024 MB per case. `main.ts` (Node 22) or `main.py`
  (Python 3.13) in the repository root.
- Deliverables: public GitHub repo owned by the entrant, created after the
  competition opened (after 2026-11-17T06:00:00Z), OSI-approved licence,
  plus the AI coding-agent transcripts of the sessions that built it.
  Max 10 submissions/day, 20 total; last submission before the deadline
  is the final entry. Escrow: $250 USDC on Solana (see bounty page).

## The model

Simple and principled; it has to beat a flat house baseline, not pretend
to know the future.

1. **Anchor on hour 1.** Every forecast is a multiple of the observed
   hour-1 mean CCU. No external data is baked in, so the same code adapts
   to a huge launch (1M+ viewers) or a modest one.
2. **Median shape — a modest launch-day hump.** Hour 1 is 00:00–01:00 UTC,
   a low-traffic hour for Twitch globally, so category viewership is
   expected to rise through the European/US day to a modest peak and then
   fall back as the US evening ends:

   | hours | median multiple of hour 1 |
   |-------|---------------------------|
   | 2–5   | 1.02 → 1.14 (rising)      |
   | 6–12  | 1.18 → 1.28 (peak ~1.28×) |
   | 13–19 | 1.27 → 1.10 (falling)     |
   | 20–24 | 1.05 → 0.85 (late fall)   |

   The hump is deliberately modest (max |log multiple| ≈ 0.25). If the
   true day turns out flat or gently decaying, the median miss stays close
   to the flat house baseline instead of blowing up; if the usual diurnal
   rise is there, it beats flat. This is a generic big-launch shape, not a
   fit to any one game's data — no launch-day Twitch series was available
   to calibrate against, and none is claimed.
3. **Uncertainty — lognormal bands widening with horizon.**
   `sigma(h) = 0.08 + 0.012·(h−1)` on the log scale; quantiles use the
   standard-normal z-values for 5/25/50/75/95%. The 90% band is roughly
   ±16% at hour 2 and −44%/+80% at hour 24. Widening over the day mirrors
   the house baseline's widening spread and is what log-scale pinball
   rewards when the median is honest: too narrow and a miss is punished
   hard; too wide and every quantile is far from the truth.

## Input format — verified against the kit

The first build guessed the `.in` format from the bounty page and got it
wrong: its flexible parser read the kit practice cases' hour 1 as 0.95
(the `levels` list's last value) and wrote plain-text lines instead of
the required JSON. Fixed 17 Nov 2026 after downloading the competition
kit: `main.py` now reads the real `makefun/twitch-ccu-case/v1` schema
(`known` row for hour 1, `forecast` hours 2–24) and writes the required
JSON `{"hours": [...]}` output. Verified on all four kit practice cases
(p00 Marvel's Wolverine, hour 1 = 23,357; p01 Red Dead Redemption 2,
116,550; p02 God of War Ragnarök, 269,517; p03 Marvel's Spider-Man 2,
119,087) — correct hour-1 anchor and valid JSON output on each. The
kit's scorer/reference data are not published, so practice cases are
graded on the server only (`grade-local` refuses program/v1 kits).

## Tests

```sh
python3 test.py        # builds 3 synthetic cases, runs main.py twice
                       # each, checks validity / monotonicity / determinism
```

Cases: `case-a` hour 1 = 850,000 (plain number); `case-b` hour 1 =
1,250,000 (JSON with a 60-minute series, mean = 1,250,000);
`case-c` hour 1 = 12,000 (labelled `ccu: 12000` text). All checks passed
locally on 17 Nov 2026 — see `TESTS.md` for the exact outputs.

## Licence

MIT — see `LICENSE`.
