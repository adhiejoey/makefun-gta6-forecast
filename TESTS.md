# Test results (synthetic cases, local run)

Run: `python3 test.py` on 2026-11-17. All checks passed.

| case | anchor (hour-1 CCU) | hour 2 (q05 q25 q50 q75 q95) | hour 12 | hour 24 | peak hour | runtime |
|------|--------------------|-------------------------------|---------|---------|-----------|---------|
| case-a | 850,000 | 745245 814835 867000 922504 1008647 | 767691 943036 1088000 1255248 1541953 | 402280 568271 722500 918586 1297618 | 11 | 0.219s |
| case-b | 1,250,000 | 1095948 1198287 1275000 1356624 1483305 | 1128958 1386818 1600000 1845953 2267579 | 591589 835693 1062500 1350862 1908261 | 11 | 0.185s |
| case-c | 12,000 | 10521 11504 12240 13024 14240 | 10838 13313 15360 17721 21769 | 5679 8023 10200 12968 18319 | 11 | 0.095s |

Checks per case: 23 lines x 5 non-negative integers; quantiles non-decreasing per row; median hump peaks hours 10-13 at 1.20-1.35x anchor; hour-24 median below anchor; 90% band widens with horizon; two runs byte-identical; runtime < 8 s.
