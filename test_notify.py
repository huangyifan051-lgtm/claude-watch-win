#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试通知是否正常 — 跑一下看看手机收不收得到
用法: python test_notify.py
"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claude_notify import load_env, send_notification, enabled

HOME = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(HOME, ".env")

# 1. 检查配置
if not os.path.exists(env_path):
    print("❌ 请先配置 .env 文件:")
    print("   cp D:\\claude-watch-win\\.env.example .env")
    print("   编辑 .env, 填入你的 BARK_URL 或 NTFY_TOPIC")
    sys.exit(1)

env = load_env()
bark = env.get("BARK_URL", "")
ntfy = env.get("NTFY_TOPIC", "")

if not bark and not ntfy:
    print("❌ .env 中 BARK_URL 和 NTFY_TOPIC 都为空, 请至少填一个")
    sys.exit(1)

# 2. 检查 enabled
e = os.path.join(HOME, "enabled")
if not os.path.exists(e):
    print("⚠️  enabled 文件不存在, 正在创建...")
    open(e, "w").close()
    print("✅ 已启用!")

# 3. 发送测试通知
print("📤 发送测试通知...")
print(f"   通道: {'Bark' if bark else 'ntfy'}")
ok = send_notification(env, "🧪 测试通知", "如果你看到这条消息, 说明配置成功!\n来自 Claude Code (Windows)")
if ok:
    print("✅ 发送成功! 检查你的手机/手表")
else:
    print("❌ 发送失败")
    if bark:
        print(f"   Bark URL: {bark[:40]}...")
        print("   请确认: 1) Bark App 已安装 2) URL 正确 3) 网络正常")
    elif ntfy:
        print(f"   ntfy topic: {ntfy}")
        print("   请确认: 1) ntfy App 已安装 2) 已订阅此 topic")
