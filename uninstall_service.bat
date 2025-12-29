@echo off
chcp 65001 >nul
echo ========================================
echo    Gemini API 服务卸载脚本
echo ========================================
echo.

REM 检查管理员权限
net session >nul 2>&1
if errorlevel 1 (
    echo [错误] 需要管理员权限才能卸载服务
    echo [提示] 请右键点击此脚本，选择"以管理员身份运行"
    pause
    exit /b 1
)

REM 停止服务
echo [信息] 正在停止服务...
call stop_service.bat

REM 删除任务计划
echo [信息] 正在删除开机自启动任务...
schtasks /query /TN "GeminiAPIService" >nul 2>&1
if not errorlevel 1 (
    schtasks /delete /TN "GeminiAPIService" /F >nul 2>&1
    if errorlevel 1 (
        echo [错误] 删除任务失败
        pause
        exit /b 1
    )
    echo [成功] 已删除开机自启动任务
) else (
    echo [信息] 未找到已安装的任务
)

REM 删除启动脚本
set "SCRIPT_DIR=%~dp0"
if exist "%SCRIPT_DIR%start_service_hidden.bat" (
    del /F /Q "%SCRIPT_DIR%start_service_hidden.bat" >nul 2>&1
    echo [成功] 已删除启动脚本
)

echo.
echo [成功] 服务已完全卸载！
echo.
pause


