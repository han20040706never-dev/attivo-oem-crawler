# cloud_setup.ps1 — 云电脑豆包一键部署脚本
# 用法: 在云电脑PowerShell中执行: iex (iwr "https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main/cloud_setup.ps1" -UseBasicParsing).Content
# 或者下载后: .\cloud_setup.ps1

$ErrorActionPreference = "Stop"
$WorkDir = "$env:USERPROFILE\attivo-cloud"
$Repo = "han20040706never-dev/attivo-oem-crawler"
$RawBase = "https://raw.githubusercontent.com/$Repo/main"
$Files = @("cloud_ax.py", "shared_mem.py", "sharedtask.py", "ai_router.py", "ds_harness.py", "config.example.py", ".gitignore")

Write-Host "=== attivoX 云电脑一键部署 ===" -ForegroundColor Cyan

# 1. 创建工作目录
if (!(Test-Path $WorkDir)) { New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null }
Set-Location $WorkDir
Write-Host "工作目录: $WorkDir"

# 2. 下载核心文件
Write-Host "下载核心脚本..."
foreach ($f in $Files) {
    try {
        Invoke-WebRequest -Uri "$RawBase/$f" -OutFile $f -UseBasicParsing -TimeoutSec 30
        Write-Host "  OK: $f"
    } catch {
        Write-Host "  FAIL: $f - $_" -ForegroundColor Red
    }
}

# 3. 生成config.py（如果不存在）
if (!(Test-Path "config.py")) {
    Copy-Item "config.example.py" "config.py"
    Write-Host "已生成 config.py，请编辑填入API密钥" -ForegroundColor Yellow
} else {
    Write-Host "config.py已存在，跳过"
}

# 4. 安装Python依赖
Write-Host "安装Python依赖..."
pip install requests 2>$null | Out-Null
Write-Host "  requests OK"

# 5. 检查并安装lark-cli
$larkOk = $false
try { $larkOk = (Get-Command lark-cli -ErrorAction Stop) -ne $null } catch {}
if ($larkOk) {
    Write-Host "  lark-cli OK"
} else {
    Write-Host "  安装lark-cli..."
    try {
        npm install -g @larksuite/lark-cli 2>&1 | Out-Null
        $larkOk = (Get-Command lark-cli -ErrorAction Stop) -ne $null
        if ($larkOk) { Write-Host "  lark-cli 安装成功" }
    } catch {
        Write-Host "  npm安装失败，尝试下载..." -ForegroundColor Yellow
    }
    if (-not $larkOk) {
        Write-Host "  警告: lark-cli安装失败，请手动安装: npm install -g @larksuite/lark-cli" -ForegroundColor Yellow
        Write-Host "  飞书共享任务/记忆功能将不可用" -ForegroundColor Yellow
    }
}

# 6. 验证
Write-Host "`n=== 验证 ==="
$py = "python"
try {
    $test = & $py -c "import requests; print('requests OK')" 2>&1
    Write-Host "  $test"
} catch {
    Write-Host "  Python环境异常: $_" -ForegroundColor Red
}

Write-Host "`n=== 部署完成 ===" -ForegroundColor Green
Write-Host "工作目录: $WorkDir"
Write-Host "下一步:"
Write-Host "  1. 编辑 config.py 填入API密钥"
Write-Host "  2. 执行: python cloud_ax.py bootstrap  (拉取共享记忆+待处理任务)"
Write-Host "  3. 认领任务: python cloud_ax.py task claim <任务ID> <你的实例名>"
Write-Host "  4. 完成任务: python cloud_ax.py task complete <任务ID> `"结果`" `"经验`""
Write-Host "`n常用命令:"
Write-Host "  python cloud_ax.py memory bootstrap   # 启动引导"
Write-Host "  python cloud_ax.py task pending       # 查看待处理任务"
Write-Host "  python cloud_ax.py think `"问题`"      # DeepSeek代码助手"
Write-Host "  python cloud_ax.py ai `"任务`"         # 免费AI处理"
