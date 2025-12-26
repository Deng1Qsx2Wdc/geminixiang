#!/bin/bash

# ============================================
# Gemini API 一键自动部署脚本
# 使用方法：复制以下命令到服务器执行
# curl -fsSL https://raw.githubusercontent.com/your-repo/install.sh | bash
# 或直接运行：bash <(curl -fsSL https://raw.githubusercontent.com/your-repo/install.sh)
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 打印带颜色的消息
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warning() { echo -e "${YELLOW}[⚠]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }

# 检查是否为 root
if [ "$EUID" -eq 0 ]; then 
   error "请不要使用 root 用户运行此脚本"
   exit 1
fi

# 配置
PROJECT_NAME="gemini-api"
PROJECT_DIR="$HOME/$PROJECT_NAME"
SERVICE_USER=$(whoami)
PORT=8001

echo ""
echo "=========================================="
echo "  Gemini API 一键自动部署"
echo "=========================================="
echo ""
info "项目目录: $PROJECT_DIR"
info "运行用户: $SERVICE_USER"
info "服务端口: $PORT"
echo ""

# 检测系统
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    else
        error "无法检测系统类型"
        exit 1
    fi
    info "检测到系统: $OS $OS_VERSION"
}

# 安装系统依赖
install_system_deps() {
    info "检查系统依赖..."
    
    local need_install=false
    
    if ! command -v python3 &> /dev/null; then need_install=true; fi
    if ! command -v pip3 &> /dev/null; then need_install=true; fi
    
    if [ "$need_install" = true ]; then
        info "正在安装 Python3 和 pip..."
        if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
            sudo apt update -qq
            sudo apt install -y python3 python3-pip python3-venv git curl
        elif [[ "$OS" == "centos" ]] || [[ "$OS" == "rhel" ]]; then
            sudo yum install -y python3 python3-pip git curl
        elif [[ "$OS" == "fedora" ]]; then
            sudo dnf install -y python3 python3-pip git curl
        else
            error "不支持的系统类型: $OS"
            exit 1
        fi
        success "系统依赖已安装"
    else
        success "系统依赖已满足"
    fi
}

# 下载项目文件
download_project() {
    info "准备项目文件..."
    
    # 检查当前目录是否已有项目文件
    if [ -f "server.py" ] && [ -f "requirements.txt" ]; then
        info "检测到当前目录已有项目文件，使用当前目录"
        PROJECT_DIR=$(pwd)
        success "使用项目目录: $PROJECT_DIR"
        return
    fi
    
    # 如果目录已存在，询问是否覆盖
    if [ -d "$PROJECT_DIR" ]; then
        warning "目录已存在: $PROJECT_DIR"
        read -p "是否删除并重新创建？(y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$PROJECT_DIR"
        else
            info "使用现有目录"
            return
        fi
    fi
    
    # 创建目录
    mkdir -p "$PROJECT_DIR"
    
    # 如果当前目录有文件，复制过去
    if [ -f "server.py" ]; then
        info "复制项目文件到 $PROJECT_DIR"
        cp -r . "$PROJECT_DIR/" 2>/dev/null || true
    else
        # 尝试从 Git 下载（如果有）
        warning "未找到项目文件，请确保在项目目录运行此脚本"
        warning "或手动上传项目文件到服务器"
        exit 1
    fi
    
    success "项目文件已准备"
}

# 创建虚拟环境
setup_venv() {
    info "创建 Python 虚拟环境..."
    cd "$PROJECT_DIR"
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        success "虚拟环境已创建"
    else
        success "虚拟环境已存在"
    fi
    
    # 激活并升级 pip
    source venv/bin/activate
    pip install --upgrade pip -q
}

# 安装 Python 依赖
install_python_deps() {
    info "安装 Python 依赖包..."
    
    if [ ! -f "requirements.txt" ]; then
        error "未找到 requirements.txt 文件"
        exit 1
    fi
    
    pip install -r requirements.txt -q
    success "Python 依赖已安装"
}

# 配置防火墙
setup_firewall() {
    info "配置防火墙规则..."
    
    if command -v ufw &> /dev/null; then
        if sudo ufw status | grep -q "Status: active"; then
            sudo ufw allow $PORT/tcp > /dev/null 2>&1
            success "UFW 防火墙规则已添加"
        else
            warning "UFW 防火墙未启用，跳过"
        fi
    elif command -v firewall-cmd &> /dev/null; then
        sudo firewall-cmd --add-port=$PORT/tcp --permanent > /dev/null 2>&1
        sudo firewall-cmd --reload > /dev/null 2>&1
        success "Firewalld 防火墙规则已添加"
    elif command -v iptables &> /dev/null; then
        sudo iptables -A INPUT -p tcp --dport $PORT -j ACCEPT > /dev/null 2>&1
        success "iptables 防火墙规则已添加（请手动保存）"
    else
        warning "未检测到防火墙，请手动开放端口 $PORT"
    fi
}

# 创建 systemd 服务
create_service() {
    info "创建系统服务..."
    
    SERVICE_FILE="/etc/systemd/system/gemini-api.service"
    
    # 检查服务是否已存在
    if [ -f "$SERVICE_FILE" ]; then
        warning "服务文件已存在，正在更新..."
        sudo systemctl stop gemini-api 2>/dev/null || true
    fi
    
    # 创建服务文件
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
    
    success "服务文件已创建"
    
    # 重新加载并启用
    sudo systemctl daemon-reload
    sudo systemctl enable gemini-api > /dev/null 2>&1
    success "服务已启用（开机自启）"
}

# 启动服务
start_service() {
    info "启动服务..."
    
    sudo systemctl start gemini-api
    sleep 3
    
    if sudo systemctl is-active --quiet gemini-api; then
        success "服务已启动"
    else
        error "服务启动失败"
        error "查看日志: sudo journalctl -u gemini-api -n 50"
        exit 1
    fi
}

# 显示结果
show_result() {
    # 获取服务器 IP
    SERVER_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "")
    if [ -z "$SERVER_IP" ]; then
        SERVER_IP=$(ip route get 8.8.8.8 2>/dev/null | awk '{print $7}' | head -1 || echo "服务器IP")
    fi
    
    echo ""
    echo "=========================================="
    success "部署完成！"
    echo "=========================================="
    echo ""
    echo "📋 服务信息："
    echo "  本地访问: http://localhost:$PORT/admin"
    echo "  外部访问: http://$SERVER_IP:$PORT/admin"
    echo "  API 地址: http://$SERVER_IP:$PORT/v1"
    echo "  API Key:  sk-gemini"
    echo ""
    echo "📁 项目目录: $PROJECT_DIR"
    echo "📝 配置文件: $PROJECT_DIR/config_data.json"
    echo ""
    echo "🔧 常用命令："
    echo "  查看状态: sudo systemctl status gemini-api"
    echo "  查看日志: sudo journalctl -u gemini-api -f"
    echo "  重启服务: sudo systemctl restart gemini-api"
    echo "  停止服务: sudo systemctl stop gemini-api"
    echo ""
    echo "💡 提示："
    echo "  1. 首次访问需要在后台配置 Cookie"
    echo "  2. 确保手机和服务器在同一网络（WiFi）"
    echo "  3. 如果无法访问，检查防火墙和安全组设置"
    echo ""
}

# 主函数
main() {
    detect_os
    install_system_deps
    download_project
    setup_venv
    install_python_deps
    setup_firewall
    create_service
    start_service
    show_result
}

# 运行主函数
main

