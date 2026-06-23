# Operit Linux Bridge

> Linux 桌面桥接服务：让 Android/Operit AI Agent 通过局域网 HTTP API 稳定控制 Linux 桌面。

`operit-bridge` 是一个轻量 Python 服务端，运行在 Linux 桌面用户会话中，配合 Operit 沙盒包 `linux_bridge` 使用。它可以让 AI Agent 直接执行命令、读写文件、管理进程、读取桌面环境、发送通知、操作剪贴板和监听文件变化。

## 特性

- **轻量可控**：Python 3 标准库为主，单文件部署，易审计。
- **桌面会话能力**：继承 `DISPLAY`、`DBUS_SESSION_BUS_ADDRESS` 等环境变量，可启动 GUI 应用。
- **文件系统操作**：读写、追加、删除、复制、移动、统计、列目录，支持 UTF-8/base64。
- **进程管理**：进程列表、进程详情、后台启动、终止进程。
- **桌面集成**：剪贴板读取/写入、`notify-send` 桌面通知。
- **文件监控**：基于 `inotifywait` 的 watch 能力，返回 PID，可手动停止。
- **稳定运行**：推荐 systemd --user 托管，支持自启、自愈、日志与内存限制。

## API Actions

| Action | 功能 |
| --- | --- |
| `ping` | 健康检查、版本、PID、运行时间 |
| `exec` | 执行 Shell 命令，返回 stdout/stderr/exit_code |
| `exec_bg` | 后台启动命令，立即返回 PID |
| `exec_stream` | 流式执行占位接口（当前返回完整输出） |
| `read` | 读取文件，支持 offset/limit/base64 |
| `write` | 写入文件，自动创建父目录，支持 append/base64/mode |
| `delete` | 删除文件或目录，支持递归 |
| `list_dir` | 列出目录内容和元数据 |
| `stat` | 获取文件/目录 size/mode/mtime/atime/type |
| `mkdir` | 创建目录，支持递归 |
| `move` | 移动或重命名文件/目录 |
| `copy` | 复制文件或目录 |
| `exists` | 检查路径是否存在 |
| `process_list` | 列出进程，支持 keyword/sort/limit |
| `process_info` | 获取单个进程详情 |
| `process_kill` | 发送信号终止进程 |
| `sysinfo` | 获取 hostname/kernel/python/user/memory/disk |
| `env` | 获取完整桌面环境变量 |
| `clipboard_read` | 读取 Wayland/X11 剪贴板 |
| `clipboard_write` | 写入 Wayland/X11 剪贴板 |
| `notify` | 发送桌面通知 |
| `watch` | 监听文件/目录变动，返回 watch PID |

## 快速安装

```bash
mkdir -p ~/.local/bin
wget https://raw.githubusercontent.com/Karzzzzz520/operit-linux-bridge/main/operit_bridge.py -O ~/.local/bin/operit-bridge
chmod +x ~/.local/bin/operit-bridge
```

临时启动：

```bash
python3 ~/.local/bin/operit-bridge
```

## systemd 用户服务（推荐）

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/operit-bridge.service << 'EOF'
[Unit]
Description=Operit Bridge - Local command executor for AI agent
Documentation=https://github.com/AAswordman/Operit
After=network.target
Wants=network.target
StartLimitIntervalSec=60
StartLimitBurst=10

[Service]
Type=simple
ExecStart=%h/.local/bin/operit-bridge
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal
SyslogIdentifier=operit-bridge
MemoryMax=64M

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now operit-bridge
systemctl --user status operit-bridge --no-pager -l
```

## 验证

```bash
curl -s -X POST http://127.0.0.1:21073/ \
  -H 'Content-Type: application/json' \
  -d '{"action":"ping"}'
```

期望返回：

```json
{"ok": true, "pong": true}
```

## 使用示例

执行命令：

```bash
curl -s -X POST http://127.0.0.1:21073/ \
  -H 'Content-Type: application/json' \
  -d '{"action":"exec","command":"uname -a"}'
```

读取文件：

```bash
curl -s -X POST http://127.0.0.1:21073/ \
  -H 'Content-Type: application/json' \
  -d '{"action":"read","path":"/etc/os-release"}'
```

发送通知：

```bash
curl -s -X POST http://127.0.0.1:21073/ \
  -H 'Content-Type: application/json' \
  -d '{"action":"notify","summary":"Operit","body":"Bridge online"}'
```

监听文件：

```bash
curl -s -X POST http://127.0.0.1:21073/ \
  -H 'Content-Type: application/json' \
  -d '{"action":"watch","path":"/home/user/.bashrc"}'
```

## 防火墙

服务默认监听 `0.0.0.0:21073`。若需要局域网访问，请放行端口：

```bash
# firewalld
sudo firewall-cmd --add-port=21073/tcp --permanent
sudo firewall-cmd --reload

# ufw
sudo ufw allow 21073/tcp
```

## 安全说明

该桥接服务能执行本机用户权限下的命令，**不要暴露到公网**。建议：

- 仅在可信局域网使用。
- 通过防火墙限制来源 IP。
- 不需要时关闭服务：`systemctl --user stop operit-bridge`。
- 配合 Operit 沙盒包 `linux_bridge` 使用时，确认 `linux_bridge_url` 指向可信主机。

## 对应 Operit 沙盒包

推荐搭配沙盒包：`linux_bridge`。

沙盒包提供 22 个工具：命令执行、文件读写、目录操作、进程管理、系统信息、桌面通知、剪贴板、文件监控等。

## License

MIT
