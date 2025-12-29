@echo off
chcp 65001 >nul
echo ========================================
echo    Gemini API 服务启动脚本
echo ========================================
echo.

REM 获取脚本所在目录
cd /d "%~dp0"

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python
    pause
    exit /b 1
)

REM 检查 server.py 是否存在
if not exist "server.py" (
    echo [错误] 未找到 server.py 文件
    pause
    exit /b 1
)

REM 检查是否已安装依赖
if not exist "requirements.txt" (
    echo [警告] 未找到 requirements.txt 文件
) else (
    echo [信息] 检查依赖包...
    python -c "import fastapi" >nul 2>&1
    if errorlevel 1 (
        echo [信息] 正在安装依赖包...
        pip install -r requirements.txt -q
        if errorlevel 1 (
            echo [错误] 依赖包安装失败
            pause
            exit /b 1
        )
    )
)

echo [信息] 正在启动 Gemini API 服务...
echo [信息] 服务地址: http://localhost:8000
echo [信息] 后台管理: http://localhost:8000/admin
echo [信息] API Key: sk-gemini
echo.
echo [提示] 按 Ctrl+C 可停止服务
echo ========================================
echo.

REM 检查服务是否已在运行
netstat -an | findstr ":8000" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo [警告] 服务已在运行中（端口 8000 已被占用）
    echo [信息] 如需重启服务，请先运行 stop_service.bat
    exit /b 0
)

REM 使用 VBScript 启动服务（完全隐藏窗口，输出到日志文件）
set "VBS_SCRIPT=%~dp0start_service_wrapper.vbs"
cscript //nologo "%VBS_SCRIPT%" >nul 2>&1

REM 等待一下确保服务启动
echo [信息] 等待服务启动...
timeout /t 3 /nobreak >nul

REM 检查服务是否启动成功
netstat -an | findstr ":8000" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo [错误] 服务启动失败，请检查：
    echo   1. Python 是否正确安装
    echo   2. 端口 8000 是否被其他程序占用
    echo   3. 依赖包是否已安装（运行: pip install -r requirements.txt）
    echo   4. 查看 Python 错误信息
    pause
    exit /b 1
) else (
    echo [成功] 服务已启动！
    echo [信息] 服务正在后台运行
    echo [信息] 访问地址: http://localhost:8000
    echo [信息] 后台管理: http://localhost:8000/admin
    echo [信息] 可以使用 stop_service.bat 停止服务
)

exit /b 0


