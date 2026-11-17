# Test results (synthetic cases, local run)

Run: `python3 test.py` on 2026-11-17. All checks passed.

| case | anchor (hour-1 CCU) | hour 2 (q05 q25 q50 q75 q95) | hour 12 | hour 24 | peak hour | runtime |
|------|--------------------|-------------------------------|---------|---------|-----------|---------|
| case-a | 850,000 | 745244.57 814835.23 867000 922504.3 1008647.41 | 767691.12 943036.13 1088000 1255247.77 1541953.5 | 402280.47 568271.37 722500 918586.22 1297617.68 | 11 | 0.047s |
| case-b | 1,250,000 | 1095947.89 1198287.1 1275000 1356623.97 1483305.01 | 1128957.52 1386817.84 1600000 1845952.6 2267578.67 | 591588.92 835693.19 1062500 1350862.09 1908261.3 | 11 | 0.045s |
| case-c | 12,000 | 10521.1 11503.56 12240 13023.59 14239.73 | 10837.99 13313.45 15360 17721.14 21768.76 | 5679.25 8022.65 10200 12968.28 18319.31 | 11 | 0.046s |

Checks per case: 23 lines x 5 non-negative integers; quantiles non-decreasing per row; median hump peaks hours 10-13 at 1.20-1.35x anchor; hour-24 median below anchor; 90% band widens with horizon; two runs byte-identical; runtime < 8 s; output is the grader's JSON {"hours": [{"hour", "q": [...]}]} format.
