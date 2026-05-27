# Summary table — sweep_anytime

## Aggregate by (goal, variant)

| goal | variant | n_cells | success | success_rate | mean plan_time (s) | mean plan_count | mean init_facts | mean total_boxels |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| find-and-tray-stack | semantic | 299 | 119 | 39.8% | 28.37 | 3.03 | 557 | 45.0 |
| find-and-tray-stack | semantic+mbs0.05 | 300 | 99 | 33.0% | 21.49 | 3.34 | 558 | 45.0 |
| find-and-tray-stack | uniform | 300 | 4 | 1.3% | 156.10 | 1.50 | 3365 | 329.1 |
| holding | semantic | 300 | 127 | 42.3% | 7.78 | 2.31 | 304 | 35.1 |
| holding | semantic+mbs0.05 | 300 | 139 | 46.3% | 7.42 | 2.67 | 303 | 35.0 |
| holding | uniform | 300 | 100 | 33.3% | 50.35 | 2.07 | 2356 | 326.0 |
| stack | semantic | 300 | 184 | 61.3% | 1.23 | 1.19 | 312 | 27.8 |
| stack | semantic+mbs0.05 | 300 | 184 | 61.3% | 1.23 | 1.19 | 312 | 27.8 |
| stack | uniform | 301 | 118 | 39.2% | 23.84 | 1.04 | 12097 | 1339.9 |

## Per-difficulty breakdown

Note: 'difficulty' is `n_occluders` for the random-pairs / scalability paths and `stack_height` for the stack scene (audit #95).  The stack-scene matrix axis is tag-only — run_config records `n_occluders=0` because stack_scene has no occluders by construction.

| goal | variant | difficulty | n_cells | success | success_rate | mean plan_time (s) | mean plan_count | mean init_facts | mean total_boxels |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| find-and-tray-stack | semantic | 2 | 99 | 39 | 39.4% | 14.93 | 2.31 | 402 | 37.7 |
| find-and-tray-stack | semantic | 3 | 100 | 38 | 38.0% | 51.57 | 2.76 | 570 | 46.2 |
| find-and-tray-stack | semantic | 4 | 100 | 42 | 42.0% | 19.88 | 3.93 | 716 | 51.8 |
| find-and-tray-stack | semantic+mbs0.05 | 2 | 100 | 40 | 40.0% | 5.10 | 2.20 | 393 | 37.3 |
| find-and-tray-stack | semantic+mbs0.05 | 3 | 100 | 31 | 31.0% | 16.14 | 2.61 | 577 | 45.9 |
| find-and-tray-stack | semantic+mbs0.05 | 4 | 100 | 28 | 28.0% | 50.81 | 5.79 | 725 | 52.9 |
| find-and-tray-stack | uniform | 2 | 100 | 2 | 2.0% | 25.77 | 1.50 | 3010 | 335.9 |
| find-and-tray-stack | uniform | 3 | 100 | 1 | 1.0% | 39.55 | 2.00 | 3343 | 325.6 |
| find-and-tray-stack | uniform | 4 | 100 | 1 | 1.0% | 533.31 | 1.00 | 3765 | 325.6 |
| holding | semantic | 2 | 100 | 41 | 41.0% | 2.00 | 1.46 | 182 | 26.4 |
| holding | semantic | 3 | 100 | 39 | 39.0% | 4.91 | 2.46 | 307 | 36.3 |
| holding | semantic | 4 | 100 | 47 | 47.0% | 15.19 | 2.94 | 427 | 42.6 |
| holding | semantic+mbs0.05 | 2 | 100 | 47 | 47.0% | 1.82 | 1.36 | 185 | 26.7 |
| holding | semantic+mbs0.05 | 3 | 100 | 44 | 44.0% | 6.80 | 3.23 | 305 | 36.0 |
| holding | semantic+mbs0.05 | 4 | 100 | 48 | 48.0% | 13.46 | 3.44 | 424 | 42.8 |
| holding | uniform | 2 | 100 | 33 | 33.0% | 21.24 | 1.45 | 2052 | 333.5 |
| holding | uniform | 3 | 100 | 36 | 36.0% | 48.90 | 2.14 | 2386 | 322.7 |
| holding | uniform | 4 | 100 | 31 | 31.0% | 83.04 | 2.65 | 2653 | 321.2 |
| stack | semantic | 2 | 100 | 97 | 97.0% | 1.15 | 1.02 | 273 | 26.3 |
| stack | semantic | 3 | 100 | 74 | 74.0% | 1.25 | 1.32 | 272 | 26.3 |
| stack | semantic | 4 | 100 | 13 | 13.0% | 1.77 | 1.69 | 394 | 30.9 |
| stack | semantic+mbs0.05 | 2 | 100 | 97 | 97.0% | 1.13 | 1.02 | 273 | 26.3 |
| stack | semantic+mbs0.05 | 3 | 100 | 74 | 74.0% | 1.29 | 1.32 | 272 | 26.3 |
| stack | semantic+mbs0.05 | 4 | 100 | 13 | 13.0% | 1.63 | 1.69 | 394 | 30.9 |
| stack | uniform | 2 | 100 | 97 | 97.0% | 20.08 | 1.02 | 11210 | 1340.8 |
| stack | uniform | 3 | 99 | 20 | 20.2% | 32.20 | 1.05 | 11116 | 1340.8 |
| stack | uniform | 4 | 102 | 1 | 1.0% | 220.54 | 3.00 | 13919 | 1338.1 |
