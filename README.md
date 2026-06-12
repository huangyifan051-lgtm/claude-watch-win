# Claude Code → Apple Watch (Windows 版)

通过 Bark 免费 iOS App，把 Claude Code 的状态实时推送到你的 iPhone 和 Apple Watch。

## 原理

```
Windows PC (Claude Code)
  │
  ├─ Stop 钩子          → Bark API → iPhone → Apple Watch  "✅ 回答完成"
  ├─ Notification 钩子   → Bark API → iPhone → Apple Watch  "🔔 等待输入"
  └─ Permission 钩子     → Bark API → iPhone → Apple Watch  "🔐 需要批准"
```

## 安装 (3 步, 2 分钟)

### Step 1: iPhone 上装 Bark

App Store 搜索 **"Bark"** (开发者: Fin), 免费, 安装后打开。

### Step 2: 复制 Bark URL

打开 Bark App → 你会看到一个 URL, 类似:
```
https://api.day.app/AbCdEf123456
```
这就是你的推送地址。**不要分享给任何人!**

### Step 3: 配置 Claude Code

```powershell
# 创建配置文件
copy E:\potato_prceed\claude-watch-win\.env.example E:\potato_prceed\claude-watch-win\.env

# 编辑 .env, 把 BARK_URL 改成你的
notepad E:\potato_prceed\claude-watch-win\.env
```

```
BARK_URL=https://api.day.app/你的密钥
```

然后在 `~/.claude/settings.json` 加入 hooks:

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [{
          "type": "command",
          "command": "D:/py/anaconda3/envs/yolo8/python.exe E:/potato_prceed/claude-watch-win/claude_notify.py --event notify"
        }]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [{
          "type": "command",
          "command": "D:/py/anaconda3/envs/yolo8/python.exe E:/potato_prceed/claude-watch-win/claude_notify.py --event complete"
        }]
      }
    ],
    "PermissionRequest": [
      {
        "matcher": "",
        "hooks": [{
          "type": "command",
          "command": "D:/py/anaconda3/envs/yolo8/python.exe E:/potato_prceed/claude-watch-win/claude_notify.py --event permission"
        }]
      }
    ]
  }
}
```

### 开启/关闭

```powershell
# 开启通知 (创建 enabled 文件)
echo "" > E:\potato_prceed\claude-watch-win\enabled

# 关闭通知 (删除 enabled 文件)
del E:\potato_prceed\claude-watch-win\enabled
```

### 测试

```powershell
D:/py/anaconda3/envs/yolo8/python.exe E:/potato_prceed/claude-watch-win/test_notify.py
```

手机收到 "🧪 测试通知" 就是配置成功了!

## 文件清单

```
claude-watch-win/
├── claude_notify.py    # 主程序 (读取钩子JSON, 发通知)
├── test_notify.py      # 测试脚本
├── .env.example        # 配置模板
├── .env                # 你的配置 (BARK_URL)
├── enabled             # 触摸开关 (有此文件=开启)
└── README.md           # 本文件
```

## FAQ

**Q: 免费吗?** A: 是。Bark 完全免费, 无需注册。

**Q: Apple Watch 收得到吗?** A: 跟 iMessage 一样, iPhone 锁屏时自动镜像到 Watch。

**Q: 办公室网络能通吗?** A: Bark 走 HTTPS(443), 你的网络能访问 GitHub 就能用。

**Q: 不想用 Bark 可以用别的吗?** A: 也支持 ntfy.sh, .env 里填 NTFY_TOPIC 即可。
