@echo off
chcp 65001 >nul
echo ========================================
echo    Gemini API 服务停止脚本
echo ========================================
echo.

REM 查找并停止 Python server.py 进程
echo [信息] 正在查找服务进程...

REM 方法1: 通过端口查找进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo [信息] 找到进程 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
    if errorlevel 1 (
        echo [警告] 无法停止进程 %%a，可能需要管理员权限
    ) else (
        echo [成功] 已停止进程 %%a
    )
)

REM 方法2: 通过进程名查找
echo [信息] 正在查找 Python server.py 进程...
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| findstr "PID"') do (
    wmic process where "ProcessId=%%a" get CommandLine 2>nul | findstr "server.py" >nul
    if not errorlevel 1 (
        echo [信息] 找到 server.py 进程 PID: %%a
        taskkill /F /PID %%a >nul 2>&1
        if errorlevel 1 (
            echo [警告] 无法停止进程 %%a，可能需要管理员权限
        ) else (
            echo [成功] 已停止进程 %%a
        )
    )
)

REM 等待一下确保进程已停止
timeout /t 1 /nobreak >nul

REM 再次检查端口是否还在使用
netstat -an | findstr ":8000" >nul
if errorlevel 1 (
    echo [成功] 服务已完全停止
) else (
    echo [警告] 端口 8000 仍在使用中，可能需要手动检查
)

echo.
echo ========================================
pause


