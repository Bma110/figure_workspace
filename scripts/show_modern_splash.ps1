param([string]$Title = "Figure startup", [string]$Caption = "Research figures, local and simple.")

$modern = $false
if ($PSVersionTable.PSVersion.Major -ge 6 -and $env:WT_SESSION) {
    $modern = $true
}
if ($modern) {
    Write-Output "  +$('-' * 72)+"
    Write-Output "  $Title"
    Write-Output "  +$('-' * 72)+"
    Write-Output "  $Caption"
    Write-Output ""
}
