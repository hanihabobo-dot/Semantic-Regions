# Summary table — sweep_anytime

## Aggregate by (goal, baseline)

| goal | baseline | n_cells | success | success_rate | mean plan_time (s) | mean plan_count | mean init_facts | mean total_boxels |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| find-and-tray-stack | semantic | 599 | 218 | 36.4% | 25.25 | 3.17 | 557 | 45.0 |
| find-and-tray-stack | uniform | 300 | 4 | 1.3% | 156.10 | 1.50 | 3365 | 329.1 |
| holding | semantic | 600 | 266 | 44.3% | 7.59 | 2.50 | 303 | 35.0 |
| holding | uniform | 300 | 100 | 33.3% | 50.35 | 2.07 | 2356 | 326.0 |
| stack | semantic | 600 | 368 | 61.3% | 1.23 | 1.19 | 312 | 27.8 |
| stack | uniform | 222 | 117 | 52.7% | 22.16 | 1.03 | 11454 | 1340.5 |

## Per-occluder breakdown

Note: stack-scene cells log `n_occluders=0` because stack_scene has no occluders by construction (the matrix-axis value is tag-only and is not passed through to the pipeline).

| goal | baseline | n_occluders | n_cells | success | success_rate | mean plan_time (s) | mean plan_count | mean init_facts | mean total_boxels |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| find-and-tray-stack | semantic | 2 | 199 | 79 | 39.7% | 9.95 | 2.25 | 397 | 37.5 |
| find-and-tray-stack | semantic | 3 | 200 | 69 | 34.5% | 35.65 | 2.70 | 573 | 46.0 |
| find-and-tray-stack | semantic | 4 | 200 | 70 | 35.0% | 32.25 | 4.67 | 720 | 52.3 |
| find-and-tray-stack | uniform | 2 | 100 | 2 | 2.0% | 25.77 | 1.50 | 3010 | 335.9 |
| find-and-tray-stack | uniform | 3 | 100 | 1 | 1.0% | 39.55 | 2.00 | 3343 | 325.6 |
| find-and-tray-stack | uniform | 4 | 100 | 1 | 1.0% | 533.31 | 1.00 | 3765 | 325.6 |
| holding | semantic | 2 | 200 | 88 | 44.0% | 1.90 | 1.41 | 184 | 26.6 |
| holding | semantic | 3 | 200 | 83 | 41.5% | 5.91 | 2.87 | 306 | 36.2 |
| holding | semantic | 4 | 200 | 95 | 47.5% | 14.32 | 3.19 | 425 | 42.7 |
| holding | uniform | 2 | 100 | 33 | 33.0% | 21.24 | 1.45 | 2052 | 333.5 |
| holding | uniform | 3 | 100 | 36 | 36.0% | 48.90 | 2.14 | 2386 | 322.7 |
| holding | uniform | 4 | 100 | 31 | 31.0% | 83.04 | 2.65 | 2653 | 321.2 |
| stack | semantic | 0 | 589 | 368 | 62.5% | 1.23 | 1.19 | 312 | 27.8 |
| stack | semantic | 3 | 2 | 0 | 0.0% | — | — | — | — |
| stack | semantic | 4 | 9 | 0 | 0.0% | — | — | — | — |
| stack | uniform | 0 | 222 | 117 | 52.7% | 22.16 | 1.03 | 11454 | 1340.5 |
