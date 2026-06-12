# Claude Code → Apple Watch / 手机通知 (Windows 版)

Bark 推送 + 本地网页审批。离开电脑也能知道 Claude 在干嘛，手机上点"批准/拒绝"。

## 功能

| 场景 | 通知 | 能交互 |
|------|------|:---:|
| Claude 回答完成 | "✅ 回答完成" | — |
| Claude 等你输入 | "🔔 等待输入" | — |
| Claude 需要你批准命令 | "🔐 需要批准: Bash `xxx`" | ✅ 手机网页点批准/拒绝 |

## 原理

```
                  ┌─ Stop 钩子        → Bark → 你的手机/手表
                  │
Windows PC ───────┼─ Notification 钩子 → Bark → 你的手机/手表
(Claude Code)     │
                  └─ Permission 钩子   → Bark + ask_phone.py
                                         ↓
                                    手机浏览器打开 172.20.x.x:9876
                                         ↓
                                    点 "✓ 批准" 或 "✕ 拒绝"
                                         ↓
                                    Claude Code 继续执行
```

## 安装 (4 步)

### Step 1: iPhone 装 Bark

App Store 搜索 **Bark** (开发者: Fin), 免费安装。

### Step 2: 配置 .env

```powershell
notepad E:\potato_prceed\claude-watch-win\.env
```

```
BARK_URL=https://api.day.app/你的密钥
```

### Step 3: 启动审批服务器

```powershell
D:\py\anaconda3\envs\yolo8\python.exe E:\potato_prceed\claude-watch-win\approve_server.py
```

服务器启动后会显示局域网 IP, 比如 `http://172.20.10.2:9876`。

### Step 4: 配置 hooks

在 `~/.claude/settings.json` 的 `hooks` 中加入:

```json
"Notification": [{
  "matcher": "",
  "hooks": [{ "type": "command",
    "command": "D:/py/anaconda3/envs/yolo8/python.exe E:/potato_prceed/claude-watch-win/claude_notify.py --event notify"
  }]
}],
"Stop": [{
  "matcher": "",
  "hooks": [{ "type": "command",
    "command": "D:/py/anaconda3/envs/yolo8/python.exe E:/potato_prceed/claude-watch-win/claude_notify.py --event complete"
  }]
}],
"PermissionRequest": [{
  "matcher": "",
  "hooks": [{ "type": "command",
    "command": "D:/py/anaconda3/envs/yolo8/python.exe E:/potato_prceed/claude-watch-win/ask_phone.py",
    "timeout": 200
  }]
}]
```

## 开机自启（可选）

审批服务器已加到 Windows 启动文件夹，开机自动运行。

手动启动/停止:
```powershell
# 启动
Start-Process D:\py\anaconda3\envs\yolo8\python.exe -Args "E:\potato_prceed\claude-watch-win\approve_server.py" -WindowStyle Hidden

# 停止
Get-Process python | Where-Object { $_.MainWindowTitle -like '*approve*' } | Stop-Process
```

## 开关

```powershell
# 开启通知
echo "" > E:\potato_prceed\claude-watch-win\enabled

# 关闭通知
del E:\potato_prceed\claude-watch-win\enabled
```

## 测试

```powershell
# 测试推送通知
D:/py/anaconda3/envs/yolo8/python.exe E:/potato_prceed/claude-watch-win/test_notify.py

# 测试审批系统（先开服务器）
# 手机浏览器打开 http://你的IP:9876
# 应该看到空白的审批页面
```

## 使用方式

1. Claude Code 需要执行带风险的操作时，你的手机/手表会收到 Bark 通知
2. 通知里有 URL: `http://172.20.10.2:9876`
3. 手机浏览器打开，看到 "🔐 需要批准" 卡片
4. 点 **✓ 批准** 或 **✕ 拒绝**
5. Claude Code 继续执行（或取消）

## 文件

```
claude-watch-win/
├── claude_notify.py    # 推送通知 (Notification/Stop hook)
├── ask_phone.py        # 手机审批 (PermissionRequest hook, 阻塞等待)
├── approve_server.py   # 本地 Web 审批服务器
├── test_notify.py      # 测试推送
├── .env.example        # 配置模板
├── .env                # 你的配置 (不提交)
├── .gitignore
├── enabled             # 开关
└── README.md
```

## FAQ

**Q: 免费?** A: 全部免费。Bark 免费, 审批服务器跑在你电脑上不花钱。

**Q: Apple Watch?** A: Bark 通知跟普通消息一样, iPhone 锁屏时自动镜像到 Watch。

**Q: 必须同一 WiFi?** A: 审批网页需要手机和电脑在同一网络（局域网）。Bark 通知不需要, 走互联网。

**Q: 安全?** A: 审批网页只在局域网可访问, 外人连不上。也支持关闭后自动回退到键盘确认。

**Q: 服务器没开怎么办?** A ask_phone.py 会自动回退到正常键盘确认, 不会卡住。
