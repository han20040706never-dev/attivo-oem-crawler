# Windows一键修复：杀掉旧daemon，保活脚本自动重启
# 用法：powershell -c "iwr https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main/fix_restart.ps1 -UseBasicParsing | iex"

Write-Host "=== 一键修复启动 ==="
Set-Location "C:\attivo-collab" -ErrorAction SilentlyContinue
if (-not (Test-Path "daemon.py")) { Set-Location "$env:USERPROFILE\attivo-collab" -ErrorAction SilentlyContinue }
if (-not (Test-Path "daemon.py")) { Write-Host "找不到attivo-collab目录"; exit 1 }

Write-Host "1. 杀掉旧daemon进程..."
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

Write-Host "2. 拉取最新代码..."
$files = @('daemon.py', 'sharedtask.py', 'common.py', 'health.py', 'auto_dispatch.py')
foreach ($f in $files) {
    try {
        Invoke-WebRequest -Uri "https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main/$f" -OutFile $f -UseBasicParsing -TimeoutSec 30
        Write-Host "   $f OK"
    } catch { Write-Host "   $f 失败: $_" }
}

Write-Host "3. 验证语法..."
python -m py_compile daemon.py
if ($LASTEXITCODE -eq 0) { Write-Host "   语法OK" } else { Write-Host "   语法错误!" }

Write-Host "4. 启动daemon..."
$instance = "云电脑 价格监控"
Start-Process -FilePath python -ArgumentList "daemon.py --instance `"$instance`" --tags `"价格监控,公开信息调研,数据整理`" --interval 300" -WindowStyle Hidden
Start-Sleep -Seconds 3

if (Get-Process python -ErrorAction SilentlyContinue) {
    Write-Host "   daemon已启动"
} else {
    Write-Host "   启动失败"
}

Write-Host "=== 修复完成，5分钟内心跳会更新 ==="
