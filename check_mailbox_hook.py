#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PreToolUse hook — 每次工具执行前检查手机消息
用时间戳文件限制频率，避免每次都读磁盘
"""
import sys, os, json, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
MAILBOX_DIR = os.path.join(HERE, "mailbox")
STAMP_FILE = os.path.join(HERE, ".last_mailbox_check")
CHECK_INTERVAL = 30  # 每30秒才检查一次

os.makedirs(MAILBOX_DIR, exist_ok=True)

# 频率限制
if os.path.exists(STAMP_FILE):
    try:
        with open(STAMP_FILE) as f:
            last = float(f.read().strip())
        if time.time() - last < CHECK_INTERVAL:
            sys.exit(0)  # 刚查过，跳过
    except:
        pass

# 更新时间戳
with open(STAMP_FILE, "w") as f:
    f.write(str(time.time()))

# 检查未读消息
msgs = []
try:
    for fn in sorted(os.listdir(MAILBOX_DIR)):
        fpath = os.path.join(MAILBOX_DIR, fn)
        try:
            with open(fpath, encoding="utf-8") as f:
                d = json.load(f)
            if not d.get("read"):
                d["id"] = fn
                msgs.append(d)
        except:
            pass
except:
    pass

if not msgs:
    sys.exit(0)

# 有消息！输出+标记已读
lines = []
for i, m in enumerate(msgs, 1):
    lines.append(f"[手机 {m['time']}] {m['text']}")
    # 标记已读
    fpath = os.path.join(MAILBOX_DIR, m["id"])
    try:
        with open(fpath, encoding="utf-8") as f:
            d = json.load(f)
        d["read"] = True
        with open(fpath + ".tmp", "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(fpath + ".tmp", fpath)
    except:
        pass

output = "\n".join(lines)
# 输出到 stdout — Claude Code 会捕获并展示
print(output)
