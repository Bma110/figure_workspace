param([string]$Title = "Figure 工作台启动", [string]$Caption = "Research figures, local and simple.")

$settings = Get-ItemProperty "HKCU:\Console\VirtualTerminalProcessing" -ErrorAction SilentlyContinue
$modern = $false
if ($PSVersionTable.PSVersion.Major -ge 6 -and $env:WT_SESSION) { $modern = $true }
if ($modern) {
    try {
        Write-Output "  $('─' * 72)"
        Write-Output "   $Title  "
        Write-Output "  $('─' * 72)"
        Write-Output "   $Caption  "
        Write-Output ""
    }
    catch { $modern = $false }
}
