#!/usr/bin/env python3
"""
Claude Code → Windows → iPhone/Apple Watch 通知
================================================
通过 Bark (免费 iOS App) 或 ntfy.sh 将 Claude Code 状态推送到手机/手表。

用法 (在 ~/.claude/settings.json 的 hooks 中配置):
    python claude_notify.py --event notify     # 等待输入
    python claude_notify.py --event complete   # 回答完成
    python claude_notify.py --event permission # 需要批准

支持两种推送通道 (在 .env 中选一种):
    A) Bark - 安装免费 iOS App, 拿到 URL 即用, 零配置
    B) ntfy.sh - 开源推送服务, Android/iOS 都支持
"""
import sys, os, json, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
ENABLED_FILE = os.path.join(HERE, "enabled")
ENV_FILE = os.path.join(HERE, ".env")


def load_env():
    """读取 .env 配置"""
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def enabled():
    """检查 enabled 文件是否存在 (触摸开关)"""
    return os.path.exists(ENABLED_FILE)


def send_bark(bark_url, title, body, group="Claude Code"):
    """通过 Bark 发送通知 (免费 iOS App) — 使用系统 curl 避免 Python SSL 兼容问题"""
    import subprocess as _sp
    full_url = bark_url.rstrip("/")
    try:
        _sp.run([
            "curl", "-s", "-X", "POST",
            f"{full_url}/{title}/{body}?title={title}&body={body}&group={group}&sound=telegraph&isArchive=1",
            "--max-time", "10"
        ], timeout=12, capture_output=True, creationflags=0x08000000)
        return True
    except Exception:
        return False


def send_ntfy(ntfy_topic, title, body):
    """通过 ntfy.sh 发送通知"""
    import urllib.request
    import json
    url = f"https://ntfy.sh/{ntfy_topic}"
    data = json.dumps({
        "topic": ntfy_topic,
        "title": title,
        "message": body,
        "tags": ["robot"],
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def send_notification(env, title, body):
    """根据配置选择推送通道"""
    bark_url = os.environ.get("BARK_URL") or env.get("BARK_URL", "")
    ntfy_topic = os.environ.get("NTFY_TOPIC") or env.get("NTFY_TOPIC", "")

    if bark_url:
        return send_bark(bark_url, title, body)
    elif ntfy_topic:
        return send_ntfy(ntfy_topic, title, body)
    return False


def read_hook_json():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8-sig")
        if raw.strip():
            return json.loads(raw)
    except Exception:
        pass
    return {}


def get_arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def main():
    if not enabled():
        return

    env = load_env()
    event = get_arg("--event", "notify")

    # server event 不走 stdin
    if event == "server":
        import socket as _sock
        ip = "?"
        try:
            s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except:
            pass
        title = "审批地址"
        body = f"http://{ip}:9876  (收藏备用)"
        send_notification(env, title, body)
        return

    data = read_hook_json()
    cwd = data.get("cwd", "") or ""
    proj = os.path.basename(cwd.rstrip("/")) if cwd else ""

    if event == "complete":
        flag = os.environ.get("NOTIFY_COMPLETE") or env.get("NOTIFY_COMPLETE", "1")
        if str(flag) in ("0", "false", "False", "no"):
            return
        title = "✅ 回答完成"
        body = "Claude Code 应答已完成"
        if proj:
            body += f"\n📂 {proj}"

    elif event == "permission":
        tool = data.get("tool_name", "")
        ti = data.get("tool_input", {})
        if tool == "Bash":
            cmd = (ti.get("command") or "").strip()[:200]
            detail = f"Bash: {cmd}"
        elif tool in ("Write", "Edit"):
            fp = os.path.basename((ti.get("file_path") or ""))
            detail = f"{tool}: {fp}"
        else:
            detail = tool or "工具操作"
        title = "🔐 需要批准"
        body = f"{detail}\n请在电脑上确认"
        if proj:
            body += f"\n📂 {proj}"

    elif event == "notify":
        msg = data.get("message", "等待中...")
        low = msg.lower()
        if "permission" in low or "approve" in low or "许可" in msg:
            return  # 许可类留给 permission 钩子处理
        title = "🔔 等待输入"
        body = msg[:300]
        if proj:
            body += f"\n📂 {proj}"

    else:
        title = "Claude Code"
        body = event

    send_notification(env, title, body)

    # 写入状态文件（手机仪表盘可见）
    try:
        status = {
            "last_event": title,
            "last_time": time.strftime("%H:%M:%S"),
            "last_project": proj,
        }
        with open(os.path.join(HERE, "status.json"), "w", encoding="utf-8") as f:
            json.dump(status, f)
    except:
        pass


if __name__ == "__main__":
    main()
