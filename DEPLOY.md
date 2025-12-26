# 服务器部署指南

本指南将帮助你将 Gemini API 服务部署到服务器上，支持手机和其他设备访问。

## 📋 目录

- [Linux 服务器部署](#linux-服务器部署)
- [Windows 服务器部署](#windows-服务器部署)
- [后台运行方案](#后台运行方案)
- [防火墙配置](#防火墙配置)
- [域名配置（可选）](#域名配置可选)
- [常见问题](#常见问题)

---

## 🐧 Linux 服务器部署

### 1. 连接服务器

使用 SSH 连接到你的 Linux 服务器：

```bash
ssh username@your-server-ip
```

### 2. 安装 Python 和依赖

#### Ubuntu/Debian 系统：

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Python 3 和 pip
sudo apt install python3 python3-pip python3-venv -y

# 安装 git（如果需要从仓库克隆）
sudo apt install git -y
```

#### CentOS/RHEL 系统：

```bash
# 更新系统
sudo yum update -y

# 安装 Python 3 和 pip
sudo yum install python3 python3-pip -y

# 或使用 dnf（较新版本）
sudo dnf install python3 python3-pip -y
```

### 3. 上传项目文件

#### 方法一：使用 SCP（从本地电脑上传）

在**本地电脑**上执行：

```bash
# Windows PowerShell
scp -r "E:\gemininixiang - 副本" username@your-server-ip:/home/username/gemini-api

# Linux/Mac
scp -r /path/to/gemininixiang username@your-server-ip:/home/username/gemini-api
```

#### 方法二：使用 Git（如果项目在 Git 仓库）

```bash
cd ~
git clone your-repo-url gemini-api
cd gemini-api
```

#### 方法三：使用 FTP/SFTP 工具

使用 FileZilla、WinSCP 等工具上传项目文件夹到服务器。

### 4. 创建虚拟环境并安装依赖

```bash
# 进入项目目录
cd ~/gemini-api  # 或你上传的目录

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 5. 测试运行

```bash
# 确保虚拟环境已激活
source venv/bin/activate

# 运行服务器
python server.py
```

如果看到启动信息，说明运行成功。按 `Ctrl+C` 停止。

### 6. 配置防火墙

```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 8001/tcp
sudo ufw reload

# CentOS/RHEL (firewalld)
sudo firewall-cmd --add-port=8001/tcp --permanent
sudo firewall-cmd --reload

# 或使用 iptables
sudo iptables -A INPUT -p tcp --dport 8001 -j ACCEPT
sudo iptables-save
```

---

## 🪟 Windows 服务器部署

### 1. 安装 Python

1. 下载 Python 3.8+：https://www.python.org/downloads/
2. 安装时勾选 "Add Python to PATH"
3. 验证安装：打开 PowerShell，运行 `python --version`

### 2. 上传项目文件

使用远程桌面连接服务器，然后：
- 使用 FTP 工具上传
- 或直接在服务器上下载/克隆项目

### 3. 安装依赖

在项目目录打开 PowerShell：

```powershell
# 创建虚拟环境（可选）
python -m venv venv
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 4. 配置防火墙

1. 打开 "Windows Defender 防火墙"
2. 点击 "高级设置"
3. 入站规则 → 新建规则
4. 选择 "端口" → TCP → 特定本地端口：8001
5. 允许连接 → 完成

### 5. 测试运行

```powershell
python server.py
```

---

## 🔄 后台运行方案

### 方案一：使用 systemd（推荐，Linux）

创建系统服务，自动启动和管理：

```bash
# 创建服务文件
sudo nano /etc/systemd/system/gemini-api.service
```

粘贴以下内容（**记得修改路径和用户名**）：

```ini
[Unit]
Description=Gemini OpenAI API Server
After=network.target

[Service]
Type=simple
User=your-username  # 改为你的用户名
WorkingDirectory=/home/your-username/gemini-api  # 改为项目路径
Environment="PATH=/home/your-username/gemini-api/venv/bin"
ExecStart=/home/your-username/gemini-api/venv/bin/python /home/your-username/gemini-api/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用并启动服务：

```bash
# 重新加载 systemd
sudo systemctl daemon-reload

# 启用服务（开机自启）
sudo systemctl enable gemini-api

# 启动服务
sudo systemctl start gemini-api

# 查看状态
sudo systemctl status gemini-api

# 查看日志
sudo journalctl -u gemini-api -f
```

常用命令：

```bash
# 停止服务
sudo systemctl stop gemini-api

# 重启服务
sudo systemctl restart gemini-api

# 禁用开机自启
sudo systemctl disable gemini-api
```

### 方案二：使用 screen（简单，适合临时运行）

```bash
# 安装 screen（如果没有）
sudo apt install screen -y  # Ubuntu/Debian
sudo yum install screen -y  # CentOS/RHEL

# 创建新的 screen 会话
screen -S gemini-api

# 激活虚拟环境并运行
source venv/bin/activate
python server.py

# 按 Ctrl+A 然后按 D 退出 screen（服务继续运行）

# 重新连接 screen
screen -r gemini-api

# 查看所有 screen 会话
screen -ls

# 结束 screen 会话
screen -X -S gemini-api quit
```

### 方案三：使用 nohup（最简单）

```bash
# 激活虚拟环境
source venv/bin/activate

# 后台运行
nohup python server.py > server.log 2>&1 &

# 查看进程
ps aux | grep server.py

# 查看日志
tail -f server.log

# 停止服务（找到进程 ID 后）
kill <PID>
```

### 方案四：使用 Supervisor（功能强大）

```bash
# 安装 supervisor
sudo apt install supervisor -y  # Ubuntu/Debian
sudo yum install supervisor -y   # CentOS/RHEL

# 创建配置文件
sudo nano /etc/supervisor/conf.d/gemini-api.conf
```

粘贴以下内容：

```ini
[program:gemini-api]
command=/home/your-username/gemini-api/venv/bin/python /home/your-username/gemini-api/server.py
directory=/home/your-username/gemini-api
user=your-username
autostart=true
autorestart=true
stderr_logfile=/var/log/gemini-api.err.log
stdout_logfile=/var/log/gemini-api.out.log
```

启动服务：

```bash
# 重新加载配置
sudo supervisorctl reread
sudo supervisorctl update

# 启动服务
sudo supervisorctl start gemini-api

# 查看状态
sudo supervisorctl status gemini-api

# 查看日志
sudo tail -f /var/log/gemini-api.out.log
```

---

## 🔥 防火墙配置

### Linux 防火墙

#### UFW (Ubuntu/Debian)

```bash
# 允许端口
sudo ufw allow 8001/tcp

# 查看状态
sudo ufw status

# 如果防火墙未启用，可以启用
sudo ufw enable
```

#### Firewalld (CentOS/RHEL)

```bash
# 允许端口
sudo firewall-cmd --add-port=8001/tcp --permanent

# 重新加载
sudo firewall-cmd --reload

# 查看开放的端口
sudo firewall-cmd --list-ports
```

#### iptables

```bash
# 允许端口
sudo iptables -A INPUT -p tcp --dport 8001 -j ACCEPT

# 保存规则（Debian/Ubuntu）
sudo iptables-save > /etc/iptables/rules.v4

# 保存规则（CentOS/RHEL）
sudo service iptables save
```

### Windows 防火墙

1. 打开 "Windows Defender 防火墙"
2. 点击 "高级设置"
3. 入站规则 → 新建规则
4. 选择 "端口" → TCP → 特定本地端口：8001
5. 允许连接 → 完成

### 云服务器安全组

如果使用阿里云、腾讯云、AWS 等云服务器，还需要在**安全组**中开放端口：

- 登录云服务器控制台
- 找到安全组设置
- 添加入站规则：TCP 协议，端口 8001，源地址 0.0.0.0/0

---

## 🌐 域名配置（可选）

### 使用 Nginx 反向代理

安装 Nginx：

```bash
# Ubuntu/Debian
sudo apt install nginx -y

# CentOS/RHEL
sudo yum install nginx -y
```

创建 Nginx 配置：

```bash
sudo nano /etc/nginx/sites-available/gemini-api
```

粘贴以下内容：

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 改为你的域名或 IP

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket 支持（如果需要）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

启用配置：

```bash
# Ubuntu/Debian
sudo ln -s /etc/nginx/sites-available/gemini-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# CentOS/RHEL（配置文件路径不同）
sudo cp /etc/nginx/sites-available/gemini-api /etc/nginx/conf.d/gemini-api.conf
sudo nginx -t
sudo systemctl restart nginx
```

### 配置 HTTPS（使用 Let's Encrypt）

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx -y  # Ubuntu/Debian
sudo yum install certbot python3-certbot-nginx -y  # CentOS/RHEL

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

---

## ✅ 验证部署

部署完成后，验证服务是否正常运行：

1. **检查服务状态**：
   ```bash
   # systemd
   sudo systemctl status gemini-api
   
   # supervisor
   sudo supervisorctl status gemini-api
   ```

2. **测试本地访问**：
   ```bash
   curl http://localhost:8001/v1/models
   ```

3. **测试外部访问**：
   - 在手机浏览器访问：`http://服务器IP:8001/admin`
   - 或使用电脑访问：`http://服务器IP:8001/admin`

4. **查看日志**：
   ```bash
   # systemd
   sudo journalctl -u gemini-api -f
   
   # supervisor
   sudo tail -f /var/log/gemini-api.out.log
   
   # nohup
   tail -f server.log
   ```

---

## ❓ 常见问题

### Q1: 无法从外部访问？

**检查清单：**
1. ✅ 服务器防火墙是否开放 8001 端口？
2. ✅ 云服务器安全组是否开放端口？
3. ✅ 服务是否绑定到 `0.0.0.0`？（已默认配置）
4. ✅ 手机和服务器是否在同一网络？（内网访问）
5. ✅ 如果跨网络访问，服务器是否有公网 IP？

### Q2: 服务启动后立即退出？

**可能原因：**
- 端口被占用：`sudo lsof -i :8001` 或 `netstat -tulpn | grep 8001`
- Python 依赖未安装：重新运行 `pip install -r requirements.txt`
- 配置文件错误：检查 `config_data.json`

### Q3: 如何修改端口？

编辑 `server.py`，修改：
```python
PORT = 8001  # 改为其他端口，如 8080
```

然后重启服务。

### Q4: 如何更新代码？

```bash
# 停止服务
sudo systemctl stop gemini-api  # 或 supervisorctl stop gemini-api

# 更新代码（如果使用 Git）
cd ~/gemini-api
git pull

# 更新依赖（如果有新依赖）
source venv/bin/activate
pip install -r requirements.txt

# 重启服务
sudo systemctl start gemini-api  # 或 supervisorctl start gemini-api
```

### Q5: 如何查看实时日志？

```bash
# systemd
sudo journalctl -u gemini-api -f

# supervisor
sudo tail -f /var/log/gemini-api.out.log

# screen
screen -r gemini-api

# nohup
tail -f server.log
```

### Q6: 内存占用过高？

可以限制 Python 进程的内存使用，在 systemd 配置中添加：

```ini
[Service]
MemoryLimit=512M
```

### Q7: 如何备份配置？

```bash
# 备份配置文件
cp config_data.json config_data.json.backup

# 恢复配置
cp config_data.json.backup config_data.json
```

---

## 📝 快速部署脚本（Linux）

创建一个快速部署脚本：

```bash
nano deploy.sh
```

粘贴以下内容：

```bash
#!/bin/bash

# 配置变量
PROJECT_DIR="$HOME/gemini-api"
SERVICE_USER=$(whoami)

echo "开始部署 Gemini API 服务..."

# 1. 创建项目目录
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 创建 systemd 服务文件
sudo tee /etc/systemd/system/gemini-api.service > /dev/null <<EOF
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

[Install]
WantedBy=multi-user.target
EOF

# 5. 配置防火墙
sudo ufw allow 8001/tcp 2>/dev/null || sudo firewall-cmd --add-port=8001/tcp --permanent 2>/dev/null

# 6. 启用并启动服务
sudo systemctl daemon-reload
sudo systemctl enable gemini-api
sudo systemctl start gemini-api

# 7. 显示状态
echo ""
echo "部署完成！"
echo "服务状态："
sudo systemctl status gemini-api --no-pager

echo ""
echo "查看日志：sudo journalctl -u gemini-api -f"
echo "停止服务：sudo systemctl stop gemini-api"
echo "重启服务：sudo systemctl restart gemini-api"
```

赋予执行权限并运行：

```bash
chmod +x deploy.sh
./deploy.sh
```

---

## 🎉 完成！

部署完成后，你可以：

1. 在浏览器访问：`http://服务器IP:8001/admin`
2. 使用 API：`http://服务器IP:8001/v1`
3. 在手机或其他设备上访问服务

如有问题，请查看日志排查错误。

