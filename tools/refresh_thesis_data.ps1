<#
.SYNOPSIS  Refresh all eval-derived data + plots and rebuild thesis/main.pdf in one go.
           NO simulation reruns -- re-reads existing per-cell results only.
.DESCRIPTION
  1. Re-aggregate eval_results/sweep_anytime from cells/*/timing_summary.json (eval_runner.aggregate).
  2. Regenerate sweep_anytime plots from that CSV (eval_plotter.py).
  3. Regenerate resolution-subdir plots (incl. boxel_count_vs_resolution.png).
  4. Sync the regenerated PNGs the thesis uses into thesis/graphics/ (overwrites; git keeps history).
  5. Recompile thesis/main.pdf (latexmk/LuaLaTeX) and open it.
  Steps 1-3 run in the WSL wsl_env venv; step 5 uses Windows TeX Live. Does NOT git-commit.
.PARAMETER NoOpen  Skip opening main.pdf at the end.
#>
param([switch]$NoOpen)
$ErrorActionPreference = 'Stop'
$RepoWin = 'C:\Users\HaniAlassiriAlhabbou\git\Semantic_Boxels'
$RepoWsl = '/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels'
$PddlWsl = '/mnt/c/Users/HaniAlassiriAlhabbou/git/pddlstream_lib'
$TexBin  = 'C:\Users\HaniAlassiriAlhabbou\texlive\2026\bin\windows'
function Step($n,$m){ Write-Host "`n=== [$n] $m ===" -ForegroundColor Cyan }

Step 1 'Re-aggregate + replot (WSL venv; no simulation)'
$wsl = @"
set -e
cd $RepoWsl
source wsl_env/bin/activate
export PYTHONPATH=${RepoWsl}:$PddlWsl
echo '--- aggregate sweep_anytime ---'
python3 -c "from pathlib import Path; import eval_runner; eval_runner.aggregate(Path('eval_results/sweep_anytime')); print('ok')"
echo '--- plot sweep_anytime (headline: drop coarse-resolution arms) ---'
python3 eval_plotter.py eval_results/sweep_anytime/aggregated.csv --drop-coarse-resolution
echo '--- plot resolution subdir (all arms; source of boxel_count_vs_resolution) ---'
python3 eval_plotter.py eval_results/sweep_anytime/resolution/aggregated.csv
"@ -replace "`r",""
wsl bash -lc $wsl
if ($LASTEXITCODE -ne 0) { throw "WSL aggregate/plot failed (exit $LASTEXITCODE)" }

Step 4 'Sync regenerated plots into thesis/graphics'
$sweep = Join-Path $RepoWin 'eval_results\sweep_anytime'
$gfx   = Join-Path $RepoWin 'thesis\graphics'
Get-ChildItem $gfx -Filter *.png | ForEach-Object {
    if ($_.Name -eq 'boxel_count_vs_resolution.png') { return }
    $src = Join-Path $sweep $_.Name
    if (Test-Path $src) { Copy-Item $src $_.FullName -Force; Write-Host "  synced $($_.Name)" }
}
$rsrc = Join-Path $sweep 'resolution\boxel_count_vs_resolution.png'
if (Test-Path $rsrc) { Copy-Item $rsrc (Join-Path $gfx 'boxel_count_vs_resolution.png') -Force
    Write-Host '  synced boxel_count_vs_resolution.png (from resolution/)' }

Step 5 'Recompile thesis/main.pdf (latexmk / LuaLaTeX)'
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

Write-Host "`nDONE -- main.pdf refreshed from current cell data." -ForegroundColor Green
if (-not $NoOpen) { Invoke-Item (Join-Path $RepoWin 'thesis\main.pdf') }
