@echo off
chcp 65001 >nul
REM Windows云电脑一键保活脚本
REM 运行一次即可，安装计划任务每5分钟自动检查并重启daemon

setlocal
set "WORKDIR=C:\attivo-collab"
set "PYTHON=python"
set "INSTANCE=%~1"
set "TAGS=%~2"

if "%INSTANCE%"=="" (
    echo 用法: setup_keepalive.bat "实例名" "标签1,标签2"
    echo 示例: setup_keepalive.bat "云电脑 价格监控" "价格监控,公开信息调研,数据整理"
    exit /b 1
)

if "%TAGS%"=="" set "TAGS=通用"

echo ========================================
echo  云电脑一键保活配置
echo  实例: %INSTANCE%
echo  标签: %TAGS%
echo ========================================

REM 1. 创建保活检查脚本
set "WATCHDOG=%WORKDIR%\watchdog.bat"
echo @echo off > "%WATCHDOG%"
echo chcp 65001 ^>nul >> "%WATCHDOG%"
echo tasklist /fi "imagename eq python.exe" /v ^| findstr /c:"daemon.py" ^>nul >> "%WATCHDOG%"
echo if errorlevel 1 ( >> "%WATCHDOG%"
echo     cd /d "%WORKDIR%" >> "%WATCHDOG%"
echo     start /b "" "%PYTHON%" daemon.py --instance "%INSTANCE%" --tags "%TAGS%" --interval 300 >> "%WORKDIR%\daemon_keepalive.log" 2^>^&1 >> "%WATCHDOG%"
echo     echo [%date% %time%] daemon已自动重启 >> "%WORKDIR%\keepalive.log" >> "%WATCHDOG%"
echo ) >> "%WATCHDOG%"

REM 2. 创建启动脚本
set "STARTER=%WORKDIR%\start_daemon.bat"
echo @echo off > "%STARTER%"
echo chcp 65001 ^>nul >> "%STARTER%"
echo cd /d "%WORKDIR%" >> "%STARTER%"
echo start /b "" "%PYTHON%" daemon.py --instance "%INSTANCE%" --tags "%TAGS%" --interval 300 >> "%WORKDIR%\daemon.log" 2^>^&1 >> "%STARTER%"

REM 3. 安装计划任务（每5分钟运行watchdog）
schtasks /create /tn "AttivoDaemonWatchdog" /tr "\"%WATCHDOG%\"" /sc minute /mo 5 /f >nul 2>&1
if errorlevel 1 (
    echo [警告] 计划任务创建失败，尝试用当前用户权限...
    schtasks /create /tn "AttivoDaemonWatchdog" /tr "\"%WATCHDOG%\"" /sc minute /mo 5 /f /ru "%USERNAME%" >nul 2>&1
)

REM 4. 立即启动daemon
call "%STARTER%"
timeout /t 3 /nobreak >nul

REM 5. 验证
tasklist /fi "imagename eq python.exe" /v | findstr /c:"daemon.py" >nul
if errorlevel 1 (
    echo [失败] daemon启动失败，请检查日志: %WORKDIR%\daemon.log
) else (
    echo [成功] daemon已启动，保活计划任务已安装（每5分钟检查）
    echo 以后daemon崩溃会自动重启，无需手动操作
)

endlocal
