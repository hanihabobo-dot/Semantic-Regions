<#
.SYNOPSIS  Refresh thesis eval plots from a NEW sweep, preserving the old build's
           stack + resolution figures, and rebuild thesis/main.pdf.  NO simulation reruns.
.DESCRIPTION
  Re-reads an existing sweep's per-cell results (no PyBullet), regenerates its plots,
  backs up the current thesis figures, then swaps in ONLY the figures the new sweep
  has valid data for.  Everything the new sweep does NOT cover is left untouched, so
  nothing regresses.

  This sweep (sweep_full_2026-05-28) has all THREE goals (holding,
  find-and-tray-stack, stack) complete at the three core variants
  {semantic, +mbs0.05, uniform} (90 cells each).  Only the coarse
  free-space-resolution arms (mbs 0.135 / 0.18 / ...) are still running, so:
    REFRESHED from the new sweep (all 3 goals; coarse arms filtered out):
      - success_rate_vs_n_occluders__holding.png
      - success_rate_vs_n_occluders__find-and-tray-stack.png
      - success_rate_vs_n_occluders__stack.png
      - planning_time_vs_n_occluders__holding.png
      - boxel_count_breakdown__holding.png
      - tampura_wallclock_comparison.png            (holding-derived)
      - failure_modes.png                            (all 3 goals present)
      - solved_vs_time.png                           (all 3 goals present)
    PRESERVED from the previous build (NOT overwritten):
      - boxel_count_vs_resolution.png                (coarse mbs arms still running)

  Steps:
    1. Aggregate + plot the NEW sweep in its OWN dir (WSL venv).  sweep_anytime
       (the old data feeding the preserved figures) is NOT touched.
    2. Back up the entire thesis/graphics dir to a timestamped folder.
    3. Copy ONLY the refresh-list figures into thesis/graphics.
    4. Recompile thesis/main.pdf (latexmk/LuaLaTeX) and open it.
  Does NOT git-commit.

  NOTE: the new sweep's success rates differ substantially from the old build
  (e.g. holding-semantic ~66% vs the old 42.3%, after the #107 replan-cap removal).
  The hand-typed headline TABLE and quoted numbers in results.tex / discussion.tex
  are NOT updated by this script -- update them manually after reviewing the plots.

.PARAMETER SweepDir  Sweep dir to refresh FROM (relative to repo root).  Default = the new sweep.
.PARAMETER NoOpen    Skip opening main.pdf at the end.
#>
param(
    [string]$SweepDir = 'eval_results/sweep_full_2026-05-28',
    [switch]$NoOpen
)
$ErrorActionPreference = 'Stop'
$RepoWin = 'C:\Users\HaniAlassiriAlhabbou\git\Semantic_Boxels'
$RepoWsl = '/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels'
$PddlWsl = '/mnt/c/Users/HaniAlassiriAlhabbou/git/pddlstream_lib'
$TexBin  = 'C:\Users\HaniAlassiriAlhabbou\texlive\2026\bin\windows'
$SweepWsl = ($SweepDir -replace '\\','/')
function Step($n,$m){ Write-Host "`n=== [$n] $m ===" -ForegroundColor Cyan }

# Figures the thesis uses that THIS sweep can validly regenerate.  All 3 goals
# at the core variants are complete; only boxel_count_vs_resolution (coarse mbs
# arms) is excluded -- it stays from the previous build until the arms finish.
$RefreshList = @(
    'success_rate_vs_n_occluders__holding.png',
    'success_rate_vs_n_occluders__find-and-tray-stack.png',
    'success_rate_vs_n_occluders__stack.png',
    'planning_time_vs_n_occluders__holding.png',
    'boxel_count_breakdown__holding.png',
    'tampura_wallclock_comparison.png',
    'failure_modes.png',
    'solved_vs_time.png'
)

Step 1 "Aggregate + plot NEW sweep '$SweepDir' (WSL venv; no simulation, sweep_anytime untouched)"
$wsl = @"
set -e
cd $RepoWsl
source wsl_env/bin/activate
export PYTHONPATH=${RepoWsl}:$PddlWsl
echo '--- aggregate $SweepWsl ---'
python3 -c "from pathlib import Path; import eval_runner; eval_runner.aggregate(Path('$SweepWsl')); print('ok')"
echo '--- plot $SweepWsl (drop any coarse-resolution arms; headline = 3 variants) ---'
python3 eval_plotter.py $SweepWsl/aggregated.csv --drop-coarse-resolution
"@ -replace "`r",""
wsl bash -lc $wsl
if ($LASTEXITCODE -ne 0) { throw "WSL aggregate/plot failed (exit $LASTEXITCODE)" }

Step 2 'Back up current thesis/graphics (nothing overwritten until this succeeds)'
$gfx = Join-Path $RepoWin 'thesis\graphics'
$stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$backup = Join-Path $RepoWin "backups\thesis_graphics_$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Copy-Item (Join-Path $gfx '*.png') $backup -Force
Write-Host "  backed up $(@(Get-ChildItem $backup -Filter *.png).Count) PNGs -> $backup"

Step 3 "Swap in ONLY the new-sweep figures ($($RefreshList.Count) files); preserve stack / resolution / cross-goal"
$sweep = Join-Path $RepoWin ($SweepDir -replace '/','\')
foreach ($name in $RefreshList) {
    $src = Join-Path $sweep $name
    $dst = Join-Path $gfx $name
    if (Test-Path $src) { Copy-Item $src $dst -Force; Write-Host "  refreshed $name" }
    else { Write-Warning "  MISSING in sweep, kept old: $name" }
}
Write-Host '  preserved (from previous build): boxel_count_vs_resolution (coarse mbs arms still running)' -ForegroundColor DarkGray

Step 4 'Recompile thesis/main.pdf (latexmk / LuaLaTeX)'
$env:PATH = "$TexBin;$env:PATH"
Push-Location (Join-Path $RepoWin 'thesis')
try {
    # Clean aux/out first: a stale or concurrently-written .aux/.out leaves
    # latexmk with "Missing \begin{document}" / runaway-argument errors (seen
    # when another build touched the dir).  -c keeps main.pdf.
    latexmk -c | Out-Null
    latexmk main.tex
    if ($LASTEXITCODE -ne 0) { throw "latexmk failed (exit $LASTEXITCODE)" }
} finally { Pop-Location }

Write-Host "`nDONE -- thesis figures refreshed from $SweepDir; old figures backed up to:" -ForegroundColor Green
Write-Host "  $backup" -ForegroundColor Green
Write-Host "REMINDER: update the hand-typed success-rate table/numbers in results.tex manually." -ForegroundColor Yellow
if (-not $NoOpen) { Invoke-Item (Join-Path $RepoWin 'thesis\main.pdf') }
