# Summary table — sweep_2026-05-12_22-31-58_random-pairs

## Aggregate by (goal, baseline)

| goal | baseline | n_cells | success | success_rate | mean plan_time (s) | mean plan_count | mean init_facts | mean total_boxels |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| find-and-tray-stack | semantic | 15 | 6 | 40.0% | 9.82 | 1.83 | 558 | 41.8 |
| find-and-tray-stack | uniform | 15 | 0 | 0.0% | — | — | 3567 | 347.9 |
| holding | semantic | 15 | 12 | 80.0% | 3.37 | 1.42 | 309 | 32.2 |
| holding | uniform | 15 | 13 | 86.7% | 33.99 | 1.38 | 2654 | 336.9 |
| stack | semantic | 5 | 5 | 100.0% | 1.19 | 1.00 | 294 | 26.8 |
| stack | uniform | 5 | 5 | 100.0% | 22.27 | 1.00 | 11242 | 1341.4 |

## Per-occluder breakdown

Note: stack-scene cells log `n_occluders=0` because stack_scene has no occluders by construction (the matrix-axis value is tag-only and is not passed through to the pipeline).

| goal | baseline | n_occluders | n_cells | success | success_rate | mean plan_time (s) | mean plan_count | mean init_facts | mean total_boxels |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| find-and-tray-stack | semantic | 2 | 5 | 2 | 40.0% | 3.96 | 1.50 | 354 | 33.5 |
| find-and-tray-stack | semantic | 3 | 5 | 2 | 40.0% | 14.38 | 2.50 | 536 | 39.5 |
| find-and-tray-stack | semantic | 4 | 5 | 2 | 40.0% | 11.13 | 1.50 | 859 | 56.0 |
| find-and-tray-stack | uniform | 2 | 5 | 0 | 0.0% | — | — | 3098 | 355.5 |
| find-and-tray-stack | uniform | 3 | 5 | 0 | 0.0% | — | — | 3568 | 340.2 |
| find-and-tray-stack | uniform | 4 | 5 | 0 | 0.0% | — | — | 4191 | 348.0 |
| holding | semantic | 2 | 5 | 4 | 80.0% | 2.05 | 1.50 | 165 | 22.8 |
| holding | semantic | 3 | 5 | 5 | 100.0% | 2.69 | 1.20 | 288 | 31.8 |
| holding | semantic | 4 | 5 | 3 | 60.0% | 6.29 | 1.67 | 475 | 42.0 |
| holding | uniform | 2 | 5 | 4 | 80.0% | 11.78 | 1.25 | 2242 | 346.8 |
| holding | uniform | 3 | 5 | 5 | 100.0% | 15.29 | 1.20 | 2589 | 332.4 |
| holding | uniform | 4 | 5 | 4 | 80.0% | 79.56 | 1.75 | 3129 | 331.4 |
| stack | semantic | 0 | 5 | 5 | 100.0% | 1.19 | 1.00 | 294 | 26.8 |
| stack | uniform | 0 | 5 | 5 | 100.0% | 22.27 | 1.00 | 11242 | 1341.4 |
