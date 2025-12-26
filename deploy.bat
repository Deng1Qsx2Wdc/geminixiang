@echo off
chcp 65001 >nul
echo ==========================================
echo   Gemini API 服务器部署脚本 (Windows)
echo ==========================================
echo.

set PROJECT_DIR=%~dp0
set SERVICE_NAME=GeminiAPI

echo 配置信息：
echo   项目目录: %PROJECT_DIR%
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/5] 检查 Python 环境...
python --version
echo    ✓ Python 已安装
echo.

echo [2/5] 创建虚拟环境...
if not exist "venv" (
    python -m venv venv
    echo    ✓ 虚拟环境已创建
) else (
    echo    ✓ 虚拟环境已存在
)
echo.

echo [3/5] 安装依赖...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q
echo    ✓ 依赖已安装
echo.

echo [4/5] 配置防火墙...
netsh advfirewall firewall show rule name="Gemini API Port 8001" >nul 2>&1
if errorlevel 1 (
    netsh advfirewall firewall add rule name="Gemini API Port 8001" dir=in action=allow protocol=TCP localport=8001
    echo    ✓ 防火墙规则已添加
) else (
    echo    ✓ 防火墙规则已存在
)
echo.

echo [5/5] 创建 Windows 服务...
echo.
echo 提示：创建 Windows 服务需要管理员权限
echo 如果当前不是管理员，请右键"以管理员身份运行"
echo.
pause

REM 检查是否安装了 NSSM (Non-Sucking Service Manager)
where nssm >nul 2>&1
if errorlevel 1 (
    echo.
    echo [可选] 安装 NSSM 以创建 Windows 服务...
    echo 下载地址: https://nssm.cc/download
    echo.
    echo 或者使用以下方法手动运行：
    echo   1. 打开命令提示符（管理员）
    echo   2. cd /d "%PROJECT_DIR%"
    echo   3. venv\Scripts\activate
    echo   4. python server.py
    echo.
    echo 或者使用任务计划程序创建开机自启任务
    echo.
) else (
    echo 检测到 NSSM，正在创建服务...
    nssm install %SERVICE_NAME% "%PROJECT_DIR%venv\Scripts\python.exe" "%PROJECT_DIR%server.py"
    nssm set %SERVICE_NAME% AppDirectory "%PROJECT_DIR%"
    nssm set %SERVICE_NAME% DisplayName "Gemini API Server"
    nssm set %SERVICE_NAME% Description "Gemini OpenAI Compatible API Server"
    nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
    nssm start %SERVICE_NAME%
    echo    ✓ 服务已创建并启动
    echo.
    echo 服务管理命令：
    echo   启动服务: nssm start %SERVICE_NAME%
    echo   停止服务: nssm stop %SERVICE_NAME%
    echo   重启服务: nssm restart %SERVICE_NAME%
    echo   删除服务: nssm remove %SERVICE_NAME% confirm
    echo.
)

REM 获取本机 IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set SERVER_IP=%%a
    set SERVER_IP=!SERVER_IP: =!
    goto :found_ip
)
:found_ip

echo ==========================================
echo   部署完成！
echo ==========================================
echo.
echo 服务信息：
echo   本地访问: http://localhost:8001/admin
if defined SERVER_IP (
    echo   外部访问: http://%SERVER_IP%:8001/admin
) else (
    echo   外部访问: http://服务器IP:8001/admin
)
echo   API 地址: http://服务器IP:8001/v1
echo   API Key:  sk-gemini
echo.
echo 项目目录: %PROJECT_DIR%
echo 配置文件: %PROJECT_DIR%config_data.json
echo.
echo 提示：
echo   1. 首次访问需要在后台配置 Cookie
echo   2. 确保手机和服务器在同一网络（WiFi）
echo   3. 如果无法访问，检查防火墙设置
echo.
pause

