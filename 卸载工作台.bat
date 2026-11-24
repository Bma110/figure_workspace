@echo off
cd /d "%~dp0"
echo ==================================
echo   卸载 Figure 工作台
echo ==================================
echo 将要删除：
echo   1. 正在运行的服务进程
echo   2. 开始菜单里的快捷方式
echo   3. 整个 figure_workspace 文件夹
echo      （虚拟环境、数据库、代码都在里面）
echo.
echo 文件夹会进「回收站」，可以随时恢复。
echo 科研数据（如 D:\ResearchData）不在这个文件夹里，不受影响。
echo.
set /p ans=确认卸载请输入 Y 然后回车：
if /i not "%ans%"=="Y" (
    echo 已取消，什么都没删。
    pause >nul
    exit /b
)

echo.
echo 正在关闭服务...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'fw_server' }); $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo 正在删除快捷方式...
del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Figure 工作台.lnk" >nul 2>nul
del /f /q "%~dp0Figure 工作台.lnk" >nul 2>nul

set "FW_UNINSTALL_DIR=%~dp0."
cd /d "%SystemRoot%"
echo 正在把文件夹移入回收站，这个窗口会自动关闭...
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Add-Type -AssemblyName Microsoft.VisualBasic; $ok = $false; for ($i = 1; $i -le 3; $i++) { try { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($env:FW_UNINSTALL_DIR, 'OnlyErrorDialogs', 'SendToRecycleBin'); $ok = $true; break } catch { Start-Sleep -Seconds 2 } }; if (-not $ok) { Add-Type -AssemblyName System.Windows.Forms; [void][System.Windows.Forms.MessageBox]::Show('自动删除失败，请手动删除这个文件夹：' + $env:FW_UNINSTALL_DIR, 'Figure 工作台卸载') }"
exit /b
