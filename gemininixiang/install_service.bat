@echo off
chcp 65001 >nul
echo ========================================
echo    Gemini API 服务安装脚本（开机自启动）
echo ========================================
echo.

REM 检查管理员权限
net session >nul 2>&1
if errorlevel 1 (
    echo [错误] 需要管理员权限才能安装服务
    echo [提示] 请右键点击此脚本，选择"以管理员身份运行"
    pause
    exit /b 1
)

REM 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

REM 获取 Python 路径
echo [信息] 正在查找 Python 路径...
where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python
    pause
    exit /b 1
)

for /f "delims=" %%i in ('where python') do set "PYTHON_PATH=%%i"

REM 检查是否已存在任务
schtasks /query /TN "GeminiAPIService" >nul 2>&1
if not errorlevel 1 (
    echo [信息] 检测到已存在的任务，正在删除...
    schtasks /delete /TN "GeminiAPIService" /F >nul 2>&1
)

REM 创建启动脚本（用于任务计划程序）
set "START_SCRIPT=%SCRIPT_DIR%\start_service_hidden.bat"
(
echo @echo off
echo cd /d "%%SCRIPT_DIR%%"
echo start /B "%%PYTHON_PATH%%" server.py
) > "%START_SCRIPT%"

REM 创建任务计划（开机自启动 + 唤醒后重启）
echo [信息] 正在创建开机自启动任务...
schtasks /create /TN "GeminiAPIService" /TR "\"%START_SCRIPT%\"" /SC ONLOGON /RU SYSTEM /RL HIGHEST /F >nul 2>&1

if errorlevel 1 (
    echo [错误] 创建任务失败，尝试使用当前用户...
    schtasks /create /TN "GeminiAPIService" /TR "\"%START_SCRIPT%\"" /SC ONLOGON /F >nul 2>&1
    if errorlevel 1 (
        echo [错误] 任务创建失败
        pause
        exit /b 1
    )
)

REM 添加唤醒后重启触发器
echo [信息] 正在添加唤醒后自动重启服务...
schtasks /change /TN "GeminiAPIService" /RU SYSTEM /RL HIGHEST /F >nul 2>&1
schtasks /change /TN "GeminiAPIService" /ENABLE >nul 2>&1

REM 创建唤醒后重启服务的任务
schtasks /query /TN "GeminiAPIServiceWake" >nul 2>&1
if not errorlevel 1 (
    schtasks /delete /TN "GeminiAPIServiceWake" /F >nul 2>&1
)

REM 创建唤醒后重启服务的任务（使用 ONEVENT 触发器）
schtasks /create /TN "GeminiAPIServiceWake" /TR "\"%START_SCRIPT%\"" /SC ONEVENT /EC System /MO "*[System[EventID=1074]]" /RU SYSTEM /RL HIGHEST /F >nul 2>&1
if errorlevel 1 (
    echo [警告] 无法创建唤醒后重启任务，服务将在唤醒后需要手动启动
)

echo [成功] 服务已安装为开机自启动！
echo.
echo ========================================
echo   安装信息
echo ========================================
echo 服务名称: GeminiAPIService
echo 启动方式: 开机自动启动
echo 服务目录: %SCRIPT_DIR%
echo Python路径: %PYTHON_PATH%
echo.
echo [提示] 可以使用以下命令管理服务：
echo   查看任务: schtasks /query /TN "GeminiAPIService"
echo   立即运行: schtasks /run /TN "GeminiAPIService"
echo   删除任务: uninstall_service.bat
echo.
echo [提示] 服务将在下次开机时自动启动
echo [提示] 如需立即启动，请运行: start_service.bat
echo.
pause


