param([switch]$Banner)

$Version = "unknown"
$source = Get-Content "fw_server.py" -Raw -ErrorAction SilentlyContinue
if ($source -match 'version\s*=\s*"([^"]+)"') { $Version = $Matches[1] }
$Root = $env:FW_ROOT
if (-not $Root) { $Root = "(default)" }

if ($Banner) {
    Write-Output ""
    Write-Output "=============================================================="
    Write-Output "Figure Workspace  $Version - Local research figure manager"
    Write-Output "=============================================================="
}
else {
    Write-Output "[Figure Workspace] Starting..."
    Write-Output "[Version] $Version"
}
Write-Output "[Data dir] $Root"
Write-Output "[URL] http://127.0.0.1:8000   Press Ctrl+C to exit"
Write-Output ""
