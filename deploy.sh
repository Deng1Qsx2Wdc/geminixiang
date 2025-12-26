#!/bin/bash

# Gemini API 快速部署脚本
# 适用于 Ubuntu/Debian/CentOS 系统

set -e

echo "=========================================="
echo "  Gemini API 服务器部署脚本"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为 root 用户
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}错误：请不要使用 root 用户运行此脚本${NC}"
   echo "请使用普通用户运行，脚本会在需要时请求 sudo 权限"
   exit 1
fi

# 配置变量
PROJECT_NAME="gemini-api"
PROJECT_DIR="$HOME/$PROJECT_NAME"
SERVICE_USER=$(whoami)
CURRENT_DIR=$(pwd)

echo -e "${GREEN}配置信息：${NC}"
echo "  项目目录: $PROJECT_DIR"
echo "  运行用户: $SERVICE_USER"
echo "  当前目录: $CURRENT_DIR"
echo ""

# 检查当前目录是否包含 server.py
if [ ! -f "$CURRENT_DIR/server.py" ]; then
    echo -e "${RED}错误：未找到 server.py 文件${NC}"
    echo "请在项目根目录运行此脚本"
    exit 1
fi

# 询问是否继续
read -p "是否继续部署？(y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "部署已取消"
    exit 1
fi

echo ""
echo -e "${YELLOW}[1/7] 检查系统环境...${NC}"

# 检测系统类型
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo -e "${RED}无法检测系统类型${NC}"
    exit 1
fi

echo "  检测到系统: $OS"

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Python3 未安装，正在安装...${NC}"
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        sudo apt update
        sudo apt install -y python3 python3-pip python3-venv
    elif [[ "$OS" == "centos" ]] || [[ "$OS" == "rhel" ]] || [[ "$OS" == "fedora" ]]; then
        sudo yum install -y python3 python3-pip
    else
        echo -e "${RED}不支持的系统类型，请手动安装 Python3${NC}"
        exit 1
    fi
else
    echo "  ✓ Python3 已安装: $(python3 --version)"
fi

# 检查 pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${YELLOW}pip3 未安装，正在安装...${NC}"
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        sudo apt install -y python3-pip
    elif [[ "$OS" == "centos" ]] || [[ "$OS" == "rhel" ]] || [[ "$OS" == "fedora" ]]; then
        sudo yum install -y python3-pip
    fi
fi

echo ""
echo -e "${YELLOW}[2/7] 创建项目目录...${NC}"

# 创建项目目录
if [ -d "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}  目录已存在: $PROJECT_DIR${NC}"
    read -p "  是否覆盖？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$PROJECT_DIR"
    else
        echo "  跳过目录创建"
    fi
fi

if [ ! -d "$PROJECT_DIR" ]; then
    mkdir -p "$PROJECT_DIR"
    echo "  ✓ 目录已创建: $PROJECT_DIR"
fi

# 复制项目文件
echo ""
echo -e "${YELLOW}[3/7] 复制项目文件...${NC}"
cp -r "$CURRENT_DIR"/* "$PROJECT_DIR/" 2>/dev/null || {
    echo -e "${RED}  错误：无法复制文件${NC}"
    echo "  请确保有读取权限"
    exit 1
}
echo "  ✓ 文件已复制"

echo ""
echo -e "${YELLOW}[4/7] 创建虚拟环境并安装依赖...${NC}"

cd "$PROJECT_DIR"

# 创建虚拟环境
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✓ 虚拟环境已创建"
else
    echo "  ✓ 虚拟环境已存在"
fi

# 激活虚拟环境并安装依赖
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  ✓ 依赖已安装"

echo ""
echo -e "${YELLOW}[5/7] 配置防火墙...${NC}"

# 检测防火墙类型并配置
if command -v ufw &> /dev/null; then
    echo "  检测到 UFW 防火墙"
    sudo ufw allow 8001/tcp
    echo "  ✓ 端口 8001 已开放"
elif command -v firewall-cmd &> /dev/null; then
    echo "  检测到 Firewalld 防火墙"
    sudo firewall-cmd --add-port=8001/tcp --permanent
    sudo firewall-cmd --reload
    echo "  ✓ 端口 8001 已开放"
elif command -v iptables &> /dev/null; then
    echo "  检测到 iptables 防火墙"
    sudo iptables -A INPUT -p tcp --dport 8001 -j ACCEPT
    echo "  ✓ 端口 8001 已开放（请手动保存规则）"
else
    echo -e "${YELLOW}  ⚠ 未检测到防火墙，请手动配置端口 8001${NC}"
fi

echo ""
echo -e "${YELLOW}[6/7] 创建系统服务...${NC}"

# 创建 systemd 服务文件
SERVICE_FILE="/etc/systemd/system/gemini-api.service"

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Gemini OpenAI API Server
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "  ✓ 服务文件已创建: $SERVICE_FILE"

# 重新加载 systemd
sudo systemctl daemon-reload
echo "  ✓ systemd 已重新加载"

# 启用服务（开机自启）
sudo systemctl enable gemini-api
echo "  ✓ 服务已启用（开机自启）"

echo ""
echo -e "${YELLOW}[7/7] 启动服务...${NC}"

# 启动服务
sudo systemctl start gemini-api
sleep 2

# 检查服务状态
if sudo systemctl is-active --quiet gemini-api; then
    echo -e "  ${GREEN}✓ 服务已启动${NC}"
else
    echo -e "${RED}  ✗ 服务启动失败${NC}"
    echo "  查看日志: sudo journalctl -u gemini-api -n 50"
    exit 1
fi

# 获取服务器 IP
SERVER_IP=$(hostname -I | awk '{print $1}')
if [ -z "$SERVER_IP" ]; then
    SERVER_IP="服务器IP"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}  部署完成！${NC}"
echo "=========================================="
echo ""
echo "服务信息："
echo "  本地访问: http://localhost:8001/admin"
echo "  外部访问: http://$SERVER_IP:8001/admin"
echo "  API 地址: http://$SERVER_IP:8001/v1"
echo "  API Key:  sk-gemini"
echo ""
echo "常用命令："
echo "  查看状态: sudo systemctl status gemini-api"
echo "  查看日志: sudo journalctl -u gemini-api -f"
echo "  重启服务: sudo systemctl restart gemini-api"
echo "  停止服务: sudo systemctl stop gemini-api"
echo ""
echo "项目目录: $PROJECT_DIR"
echo "配置文件: $PROJECT_DIR/config_data.json"
echo ""
echo -e "${YELLOW}提示：${NC}"
echo "  1. 首次访问需要在后台配置 Cookie"
echo "  2. 确保手机和服务器在同一网络（WiFi）"
echo "  3. 如果无法访问，检查防火墙和安全组设置"
echo ""

