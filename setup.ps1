$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$python = $null
foreach ($version in @('3.11', '3.12')) {
    try {
        $candidate = & py ("-" + $version) -c "import sys; print(sys.executable if sys.version_info[:2] in ((3, 11), (3, 12)) else '')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $candidate) {
            $python = $candidate.Trim()
            break
        }
    } catch { }
}
if (-not $python) {
    throw '没有找到 Python 3.11 或 3.12。请先从 python.org 安装 64 位 Python，并勾选 Python Launcher，然后重新运行 setup_windows.cmd。'
}

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    & $python -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw '创建 Python 虚拟环境失败。' }
}
$env:MPLCONFIGDIR = Join-Path $PSScriptRoot '.cache\matplotlib'
$env:XDG_CACHE_HOME = Join-Path $PSScriptRoot '.cache'
$env:PIP_CACHE_DIR = Join-Path $PSScriptRoot '.cache\pip'
New-Item -ItemType Directory -Force -Path $env:MPLCONFIGDIR, $env:PIP_CACHE_DIR | Out-Null

& $venvPython -m pip install --disable-pip-version-check --upgrade pip
if ($LASTEXITCODE -ne 0) { throw '更新 pip 失败。' }
& $venvPython -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw '安装 Python 依赖失败。' }

$model = Join-Path $PSScriptRoot 'hand_landmarker.task'
$expectedHash = 'fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1'
$validModel = (Test-Path $model) -and ((Get-FileHash -Algorithm SHA256 $model).Hash.ToLowerInvariant() -eq $expectedHash)
if (-not $validModel) {
    $download = "$model.download"
    Invoke-WebRequest -UseBasicParsing -Uri 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task' -OutFile $download
    $actualHash = (Get-FileHash -Algorithm SHA256 $download).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) {
        Remove-Item $download -Force -ErrorAction SilentlyContinue
        throw "MediaPipe 模型 SHA-256 校验失败：$actualHash"
    }
    Move-Item -Force $download $model
}

& $venvPython doctor.py
if ($LASTEXITCODE -ne 0) { throw '环境检查未通过，请根据上方提示修复。' }
New-Item -ItemType File -Force (Join-Path $PSScriptRoot '.venv\.painter-ready') | Out-Null
Write-Host '安装完成。双击 start_windows.cmd 或运行 .\start_windows.cmd 启动。' -ForegroundColor Green
