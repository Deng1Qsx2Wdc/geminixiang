# 🚀 一键自动部署 - 复制粘贴即可

## 最简单的方式

### 第一步：上传项目到服务器

**从你的本地电脑（Windows）执行：**

```powershell
scp -r "E:\gemininixiang - 副本" username@服务器IP:/home/username/
```

**或者使用 FTP 工具上传整个文件夹**

---

### 第二步：SSH 连接并一键安装

**复制下面这行命令，粘贴到服务器执行：**

```bash
cd ~/gemininixiang\ -\ 副本 && chmod +x 一键安装.sh && bash 一键安装.sh
```

**就这么简单！** 脚本会自动完成所有配置。

---

## 📋 完整的一键命令（包含上传）

如果你想一条命令完成所有操作，可以使用以下方式：

### 方式一：使用 install.sh（推荐）

```bash
# 1. 上传项目后，SSH 连接服务器
ssh username@服务器IP

# 2. 复制粘贴这一行：
cd ~ && [ -d "gemininixiang - 副本" ] && cd "gemininixiang - 副本" || (echo "请先上传项目文件" && exit 1) && chmod +x 一键安装.sh && bash 一键安装.sh
```

### 方式二：完全自动化脚本

如果你想要一个包含所有步骤的脚本，可以创建一个 `auto-install.sh`：

```bash
#!/bin/bash
# 自动检测项目目录并安装

# 查找项目目录
PROJECT_DIR=$(find ~ -name "server.py" -type f 2>/dev/null | head -1 | xargs dirname)

if [ -z "$PROJECT_DIR" ]; then
    echo "错误：未找到项目文件，请先上传项目到服务器"
    exit 1
fi

cd "$PROJECT_DIR"
chmod +x 一键安装.sh
bash 一键安装.sh
```

---

## 🎯 最简化的部署流程

### 1. 上传项目（本地电脑）
```powershell
scp -r "E:\gemininixiang - 副本" username@服务器IP:/home/username/
```

### 2. 连接服务器
```bash
ssh username@服务器IP
```

### 3. 一键安装（复制粘贴）
```bash
cd ~/gemininixiang\ -\ 副本 && chmod +x 一键安装.sh && bash 一键安装.sh
```

### 4. 完成！

脚本会自动：
- ✅ 安装 Python3（如果没有）
- ✅ 创建虚拟环境
- ✅ 安装依赖
- ✅ 配置防火墙
- ✅ 创建系统服务
- ✅ 启动服务

完成后会显示访问地址。

---

## 📱 访问服务

部署完成后，在手机浏览器输入显示的地址即可访问。

---

## ❓ 遇到问题？

查看详细日志：
```bash
sudo journalctl -u gemini-api -f
```

查看服务状态：
```bash
sudo systemctl status gemini-api
```

