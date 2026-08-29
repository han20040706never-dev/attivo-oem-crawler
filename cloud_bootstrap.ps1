# cloud_bootstrap.ps1 — 豆包云电脑一键拉起 OEM 爬虫（无人值守、断点续爬）
$ErrorActionPreference = "Stop"
$dir = "C:\oem-crawler"
New-Item -ItemType Directory -Force $dir | Out-Null
Set-Location $dir
$base = "https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main/"
foreach ($f in @("crawl_oem_tree.py", "crawl_full.py", "oemkb.db")) {
    Invoke-WebRequest -Uri ($base + $f) -OutFile $f -UseBasicParsing
}
# 确认 python
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { Write-Output "NO_PYTHON: 请先安装 Python3 并勾选 pip/PATH 后重跑本脚本"; exit 2 }
python -m pip install requests -q
# 已在跑就不重复拉起
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "crawl_full" }
if (-not $running) {
    Start-Process -WindowStyle Hidden python -ArgumentList "crawl_full.py" `
        -RedirectStandardOutput run.log -RedirectStandardError err.log
    Write-Output "已后台启动 crawl_full.py"
} else { Write-Output "已在运行，跳过重复启动" }
Start-Sleep 6
python crawl_oem_tree.py stats
Write-Output "---- run.log 末尾 ----"
if (Test-Path run.log) { Get-Content run.log -Tail 15 }
