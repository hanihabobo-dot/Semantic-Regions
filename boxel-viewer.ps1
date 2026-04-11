# Boxel 3D viewer: serves this folder and opens boxel_viewer.html in the default browser.
# Usage:  .\boxel-viewer.ps1
#         .\boxel-viewer.ps1 9000   # custom port
# Optional global alias — add to $PROFILE (replace path):
#   function bv { & 'C:\Users\HaniAlassiriAlhabbou\git\Semantic_Boxels\boxel-viewer.ps1' @args }

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location $PSScriptRoot

$port = 8000
if ($args.Count -ge 1) { $port = [int]$args[0] }
elseif ($env:BOXEL_VIEWER_PORT) { $port = [int]$env:BOXEL_VIEWER_PORT }

$url = "http://localhost:$port/boxel_viewer.html"

Start-Process powershell -ArgumentList @(
    '-NoProfile',
    '-WindowStyle', 'Hidden',
    '-Command',
    "Start-Sleep -Seconds 1; Start-Process '$url'"
) | Out-Null

Write-Host "Serving $PSScriptRoot on http://localhost:$port/ — open: $url" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray

python -m http.server $port
