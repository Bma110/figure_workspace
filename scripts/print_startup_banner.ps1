param([switch]$Banner)

$Version = "0.2.2"
$VersionInfo = Get-Item "fw_server.py" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty VersionInfo
if ($VersionInfo) { $Version = $VersionInfo.ProductVersion }

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
Write-Output "[Data dir] ..."
Write-Output "[URL] http://127.0.0.1:8000   Press Ctrl+C to exit"
Write-Output ""
