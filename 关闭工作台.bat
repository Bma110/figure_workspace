@echo off
echo 正在关闭 Figure 工作台...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'fw_server' }); if ($p.Count -gt 0) { $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Write-Host ('已关闭（结束了 ' + $p.Count + ' 个进程）') } else { Write-Host 'Figure 工作台本来就没有在运行。' }"
echo.
echo 按任意键关闭这个窗口。
pause >nul
