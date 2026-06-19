# Operit Bridge

> Linux 桌面桥接服务 —— 让 Android AI Agent 直接操控你的 Linux 桌面

一个轻量级的 HTTP 桥接服务（134行 Python），运行在 Linux 桌面端，让手机上的 AI Agent 可以通过 HTTP API 在桌面执行 Shell 命令、读写文件、管理进程。

**零依赖**，Python 3 标准库直跑。

---

## ✨ 功能

| 动作 | 说明 |
|------|------|
| `exec` | 执行 Shell 命令，返回 stdout/stderr/exit_code |
| `exec_bg` | 后台启动进程（GUI 应用、服务等） |
| `read` | 读取文件内容（支持偏移和截断） |
| `write` | 写入/追加文件（支持 chmod） |
| `delete` | 删除文件或目录（支持递归） |
| `env` | 获取桌面环境变量（DISPLAY、DBUS 等） |
| `ping` | 健康检查 |

所有操作都在桌面用户的环境中执行，具有完整的 GUI 应用启动能力和文件系统访问权限。

---

## 📦 人类安装

### 1. 下载

```bash
wget https://raw.githubusercontent.com/kars/operit-bridge/main/operit_bridge.py -O ~/.local/bin/operit-bridge
chmod +x ~/.local/bin/operit-bridge
```

> 确保 `~/.local/bin` 在你的 `PATH` 里（大多数 Linux 发行版默认包含）

### 2. 启动

**临时测试：**
```bash
python3 ~/.local/bin/operit-bridge
```

**systemd 用户服务（推荐，开机自启）：**
```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/operit-bridge.service << 'EOF'
[Unit]
Description=Operit Bridge - Linux Desktop Bridge for AI Agent
After=network.target

[Service]
ExecStart=python3 %h/.local/bin/operit-bridge
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now operit-bridge
```

### 3. 防火墙（可选）

服务监听 `0.0.0.0:21073`，如需局域网访问：
```bash
# firewalld
sudo firewall-cmd --add-port=21073/tcp --permanent
sudo firewall-cmd --reload

# ufw
sudo ufw allow 21073/tcp

# iptables
sudo iptables -A INPUT -p tcp --dport 21073 -j ACCEPT
```

---

## 🌐 API 格式

所有请求为 `POST`，Body 为 JSON：

```json
{
  "action": "exec",
  "command": "echo hello",
  "cwd": "/home/user",
  "timeout_ms": 15000,
  "env": {"KEY": "value"}
}
```

响应：

```json
{
  "ok": true,
  "id": null,
  "exit_code": 0,
  "stdout": "hello\n",
  "stderr": "",
  "pid": 12345,
  "elapsed_ms": 350427
}
```

完整 API 参见源码 `operit_bridge.py`。

---

## 📡 客户端示例

```bash
# 执行命令
curl -X POST http://127.0.0.1:21073 \
  -H 'Content-Type: application/json' \
  -d '{"action":"exec","command":"neofetch"}'

# 启动 GUI 应用
curl -X POST http://127.0.0.1:21073 \
  -H 'Content-Type: application/json' \
  -d '{"action":"exec_bg","command":"firefox"}'

# 读取文件
curl -X POST http://127.0.0.1:21073 \
  -H 'Content-Type: application/json' \
  -d '{"action":"read","path":"/etc/os-release"}'
```

---

## 🤖 给 AI Agent 的一键安装 Prompt

将此 prompt 发给你的 AI Agent，它会自动完成安装：

```text
install operit-bridge on this linux desktop:

1. download operit_bridge.py from https://raw.githubusercontent.com/kars/operit-bridge/main/operit_bridge.py
   save to ~/.local/bin/operit-bridge and chmod +x

2. create systemd user service at ~/.config/systemd/user/operit-bridge.service:
   [Unit]
   Description=Operit Bridge - Linux Desktop Bridge for AI Agent
   After=network.target
   [Service]
   ExecStart=python3 %h/.local/bin/operit-bridge
   Restart=always
   RestartSec=5
   [Install]
   WantedBy=default.target

3. run: systemctl --user daemon-reload && systemctl --user enable --now operit-bridge

4. verify with curl POST to http://127.0.0.1:21073 action=ping, expect {"ok":true,"pong":true}

5. optional: open firewall port 21073/tcp for LAN access
```

---

## 🔒 安全

- 服务监听 `0.0.0.0`，建议放在可信网络或使用防火墙限制来源 IP
- 不内置认证，信任边界由网络层控制
- 仅在有需求的机器上运行，勿暴露到公网

---

## 🪪 许可

MIT
