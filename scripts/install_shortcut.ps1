# 创建「Figure 工作台」快捷方式：仓库根一份、开始菜单一份（供固定到任务栏）。
param([switch]$Quiet)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$icon = Join-Path $root 'static\icon.ico'
$launcher = Join-Path $root 'scripts\launch.vbs'
$wscript = Join-Path $env:WINDIR 'System32\wscript.exe'

foreach ($path in @($icon, $launcher, $wscript)) {
    if (-not (Test-Path $path)) { throw "缺少文件：$path" }
}

$shell = New-Object -ComObject WScript.Shell

function New-Shortcut([string]$dir) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $path = Join-Path $dir 'Figure 工作台.lnk'
    $shortcut = $shell.CreateShortcut($path)
    $shortcut.TargetPath = $wscript
    $shortcut.Arguments = '"{0}"' -f $launcher
    $shortcut.WorkingDirectory = $root
    $shortcut.IconLocation = "$icon,0"
    $shortcut.Description = 'Figure 工作台 — 本地科研图管理'
    $shortcut.WindowStyle = 1
    $shortcut.Save()
    return $path
}

$repoShortcut = New-Shortcut $root
$startMenuDir = [Environment]::GetFolderPath('Programs')
$startMenuShortcut = New-Shortcut $startMenuDir

if (-not $Quiet) {
    Write-Output "已创建快捷方式："
    Write-Output "  $repoShortcut"
    Write-Output "  $startMenuShortcut"
    Write-Output ""
    Write-Output "固定到任务栏：打开开始菜单搜索「Figure 工作台」，右键 → 固定到任务栏。"
    Write-Output "（Windows 11 需先点「显示更多选项」，再选「固定到任务栏」。）"
}
