# 无窗口启动 Figure 工作台：已运行则直接打开浏览器，否则隐藏拉起服务再打开。
param(
    [switch]$NoBrowser,
    [switch]$NoDialog
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

$logDir = Join-Path $root 'data'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$launcherLog = Join-Path $logDir 'launcher.log'
$setupOut = Join-Path $logDir 'setup.out.log'
$setupErr = Join-Path $logDir 'setup.err.log'
$outLog = Join-Path $logDir 'server.out.log'
$errLog = Join-Path $logDir 'server.err.log'

function Write-Log([string]$text) {
    Add-Content -Path $launcherLog -Value ("[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $text) -ErrorAction SilentlyContinue
}

function Fail([string]$message) {
    Write-Log "ERROR $message"
    if (-not $NoDialog) {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
        [void][System.Windows.Forms.MessageBox]::Show($message, 'Figure 工作台', 'OK', 'Error')
    }
    exit 1
}

# 直接读 HTTP 响应，避免 Invoke-WebRequest 走系统代理导致 localhost 失败。
function Get-Http([int]$port, [string]$path, [int]$timeoutMs = 2000) {
    $client = $null
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.ReceiveTimeout = $timeoutMs
        $client.SendTimeout = $timeoutMs
        $client.Connect('127.0.0.1', $port)
        $stream = $client.GetStream()
        $request = "GET $path HTTP/1.0`r`nHost: 127.0.0.1:$port`r`nConnection: close`r`n`r`n"
        $bytes = [System.Text.Encoding]::ASCII.GetBytes($request)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush()
        $reader = New-Object System.IO.StreamReader($stream)
        return $reader.ReadToEnd()
    } catch {
        return $null
    } finally {
        if ($client) { $client.Close() }
    }
}

function Test-OurServer([int]$port) {
    $response = Get-Http $port '/api/settings'
    if (-not $response) { return $false }
    return ($response -match 'HTTP/\d(\.\d)?\s+200' -and $response -match '"root"' -and $response -match '"db"')
}

function Test-PortFree([int]$port) {
    $listener = $null
    try {
        $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) { $listener.Stop() }
    }
}

$mutex = New-Object System.Threading.Mutex($false, 'Local\FigureWorkspaceLauncher')
if (-not $mutex.WaitOne(15000)) { exit 0 }
try {
    Write-Log "launcher start (NoBrowser=$NoBrowser)"

    # 0) 首次启动自动生成开始菜单快捷方式（固定到任务栏仍由用户完成）。
    $startMenuLink = Join-Path ([Environment]::GetFolderPath('Programs')) 'Figure 工作台.lnk'
    if (-not (Test-Path $startMenuLink)) {
        try {
            $installer = Join-Path $PSScriptRoot 'install_shortcut.ps1'
            $installProc = Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') `
                -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "{0}" -Quiet' -f $installer) `
                -WindowStyle Hidden -PassThru -Wait
            Write-Log "shortcut installer exit=$($installProc.ExitCode)"
        } catch {
            Write-Log "shortcut installer failed: $($_.Exception.Message)"
        }
    }

    # 1) 已有实例：直接打开，避免重复起进程。
    for ($port = 8000; $port -le 8010; $port++) {
        if (Test-OurServer $port) {
            Write-Log "reuse server on port $port"
            if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$port/" | Out-Null }
            exit 0
        }
    }

    # 2) 数据根目录：与 启动工作台.bat 保持一致。
    if (-not $env:FW_ROOT) {
        if (Test-Path 'D:\') {
            $env:FW_ROOT = 'D:\ResearchData'
        } else {
            $env:FW_ROOT = Join-Path $env:USERPROFILE 'ResearchData'
        }
    }
    if (-not (Test-Path $env:FW_ROOT)) { New-Item -ItemType Directory -Force -Path $env:FW_ROOT | Out-Null }
    Write-Log "FW_ROOT=$env:FW_ROOT"

    # 3) 首次运行按需建 venv、装依赖（requirements 更新后也会重装）。
    $venvPython = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPython)) {
        Write-Log 'creating venv'
        $created = $false
        foreach ($name in @('python', 'py')) {
            $cmd = Get-Command $name -ErrorAction SilentlyContinue
            if (-not $cmd) { continue }
            $venvArgs = '-m venv "{0}"' -f (Join-Path $root '.venv')
            $venvProc = Start-Process -FilePath $cmd.Source -ArgumentList $venvArgs `
                -WindowStyle Hidden -RedirectStandardOutput $setupOut -RedirectStandardError $setupErr -PassThru -Wait
            if ($venvProc.ExitCode -eq 0 -and (Test-Path $venvPython)) { $created = $true; break }
        }
        if (-not $created) { Fail "创建虚拟环境失败，请确认已安装 Python 3.10+ 并加入 PATH。日志：$setupErr" }
    }

    $requirements = Join-Path $root 'requirements.txt'
    $depsMarker = Join-Path $root '.venv\.deps-ok'
    $depsStale = $true
    if (Test-Path $depsMarker) {
        $depsStale = (Get-Item $requirements).LastWriteTime -gt (Get-Item $depsMarker).LastWriteTime
    }
    if ($depsStale) {
        Write-Log 'installing requirements'
        $pipArgs = '-m pip install -q -r "{0}"' -f $requirements
        $pipProc = Start-Process -FilePath $venvPython -ArgumentList $pipArgs `
            -WindowStyle Hidden -RedirectStandardOutput $setupOut -RedirectStandardError $setupErr -PassThru -Wait
        if ($pipProc.ExitCode -ne 0) {
            # 离线或网络波动时，只要现有环境能导入依赖就继续。
            $importProc = Start-Process -FilePath $venvPython -ArgumentList '-c "import fastapi, uvicorn, multipart, PIL"' `
                -WindowStyle Hidden -PassThru -Wait
            if ($importProc.ExitCode -ne 0) { Fail "依赖安装失败，请检查网络或查看日志：$setupErr" }
            Write-Log 'pip failed but existing packages are importable; continue'
        }
        New-Item -ItemType File -Force -Path $depsMarker | Out-Null
    }

    # 4) 选一个空闲端口（8000 被别的程序占用时顺延）。
    $port = 0
    for ($p = 8000; $p -le 8010; $p++) {
        if (Test-PortFree $p) { $port = $p; break }
    }
    if ($port -eq 0) { Fail '8000-8010 端口都被占用，请先释放端口再启动。' }
    Write-Log "starting server on port $port"

    # 5) 隐藏启动服务，输出写日志，退出启动器不影响服务。
    $proc = Start-Process -FilePath $venvPython `
        -ArgumentList @('-m', 'uvicorn', 'fw_server:app', '--host', '127.0.0.1', '--port', "$port") `
        -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru

    $deadline = (Get-Date).AddSeconds(30)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        if (Test-OurServer $port) { $ready = $true; break }
        if ($proc.HasExited) { break }
        Start-Sleep -Milliseconds 300
    }
    if (-not $ready) {
        $tail = Get-Content $errLog -Tail 15 -ErrorAction SilentlyContinue | Out-String
        Fail ("服务启动失败（端口 $port）。日志：$errLog`n$tail")
    }

    Write-Log "server ready on port $port"
    if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$port/" | Out-Null }
}
finally {
    try { $mutex.ReleaseMutex() } catch { }
    $mutex.Dispose()
}
