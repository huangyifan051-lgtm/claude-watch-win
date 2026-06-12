#!/usr/bin/env python3
"""
PermissionRequest 钩子 — 手机网页审批
======================================
1. 收到 Claude 的审批请求
2. 发 Bark 通知到手机，附带审批网址
3. 等你在手机上点"批准"或"拒绝"
4. 返回结果给 Claude Code
"""
import sys, os, json, time, urllib.request, urllib.parse, re, socket, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE_DIR = os.path.join(HERE, "approvals")
os.makedirs(QUEUE_DIR, exist_ok=True)
ENABLED_FILE = os.path.join(HERE, "enabled")
PORT = 9876


def enabled():
    return os.path.exists(ENABLED_FILE)


def load_env():
    env = {}
    env_path = os.path.join(HERE, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def get_local_ip():
    """获取局域网 IP — 优先 WLAN/Wi-Fi，跳过虚拟网卡"""
    VIRTUAL = ("hyper-v", "wsl", "vethernet", "virtual", "loopback", "bluetooth")
    output = subprocess.check_output("ipconfig", shell=True, text=True)
    lines = output.split("\n")
    best_ip = None
    current_adapter = ""

    for line in lines:
        low = line.lower()
        if "adapter" in low:
            current_adapter = low
        if "IPv4" in line:
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
            if m:
                ip = m.group(1)
                # 跳过虚拟网卡
                if any(v in current_adapter for v in VIRTUAL):
                    continue
                # 跳过 APIPA (169.254.x.x)
                if ip.startswith("169.254."):
                    continue
                # 优先局域网地址
                if any(ip.startswith(p) for p in ("172.", "192.168.", "10.")):
                    # 优先 WLAN
                    if "wlan" in current_adapter or "wi-fi" in current_adapter or "无线" in current_adapter:
                        return ip
                    best_ip = best_ip or ip

    if best_ip:
        return best_ip
    return socket.gethostbyname(socket.gethostname())


def send_bark(url, title, body):
    """通过 Bark 发送通知 — 使用系统 curl 避免 Python SSL 兼容问题"""
    import subprocess as _sp
    full = url.rstrip("/")
    try:
        _sp.run([
            "curl", "-s", "-X", "POST",
            f"{full}/{title}/{body}?title={title}&body={body}&group=Claude+Code&isArchive=1",
            "--max-time", "8"
        ], timeout=10, capture_output=True, creationflags=0x08000000)
    except:
        pass


def main():
    # 调试日志
    import datetime
    log_path = os.path.join(HERE, "ask_phone_debug.log")
    def dlog(msg):
        try:
            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        except:
            pass
    dlog("ask_phone.py 被调用")

    # 未启用 → 不输出任何内容, Claude Code 退回到键盘确认
    if not enabled():
        dlog("enabled=false, 退出")
        return

    # 读取 Claude Code 传入的 JSON
    raw = sys.stdin.read()
    dlog(f"stdin 长度: {len(raw)}, 内容: {raw[:300]}")
    try:
        data = json.loads(raw) if raw.strip() else {}
    except:
        data = {}
        dlog(f"JSON 解析失败, raw={raw[:200]}")

    tool = data.get("tool_name", "unknown")
    ti = data.get("tool_input", {})
    cwd = data.get("cwd", "") or ""
    proj = os.path.basename(cwd.rstrip("/")) if cwd else ""

    # 构建可读描述
    if tool == "Bash":
        cmd = (ti.get("command") or "").strip()[:200]
        detail = "Bash: " + cmd
    elif tool in ("Write", "Edit", "MultiEdit"):
        fp = os.path.basename((ti.get("file_path") or ""))
        detail = f"{tool}: {fp}"
    elif tool == "NotebookEdit":
        fp = os.path.basename((ti.get("notebook_path") or ""))
        detail = f"{tool}: {fp}"
    else:
        detail = tool

    # 创建审批文件
    pid = f"{int(time.time())}_{os.urandom(3).hex()}.json"
    d = {
        "tool": tool,
        "detail": detail,
        "project": proj,
        "time": time.strftime("%H:%M:%S"),
        "created_at": time.time(),
        "result": None,
    }
    with open(os.path.join(QUEUE_DIR, pid), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)

    # 检查自动批准模式
    auto_file = os.path.join(HERE, "auto_approve.json")
    auto_approved = False
    if os.path.exists(auto_file):
        try:
            with open(auto_file, encoding="utf-8") as f:
                aa = json.load(f)
            if aa.get("enabled") and time.time() < aa.get("until", 0):
                auto_approved = True
        except:
            pass

    fpath = os.path.join(QUEUE_DIR, pid)

    if auto_approved:
        # 自动批准：直接写结果，不等待手机
        dlog("自动批准模式，跳过手机确认")
        with open(fpath, encoding="utf-8") as f:
            dd = json.load(f)
        dd["result"] = "approve"
        dd["auto"] = True
        with open(fpath + ".tmp", "w", encoding="utf-8") as f:
            json.dump(dd, f)
        os.replace(fpath + ".tmp", fpath)
        print(json.dumps({"decision": "approve"}))
        dlog("输出 decision=approve (自动)")
        return

    # 发 Bark 通知
    env = load_env()
    bark = os.environ.get("BARK_URL") or env.get("BARK_URL", "")
    ip = get_local_ip()
    approve_url = f"http://{ip}:{PORT}"

    if bark:
        body = f"{detail}\n\n🌐 审批: {approve_url}"
        send_bark(bark, f"🔐 {tool}", body)
    dlog(f"Bark已发, IP={ip}, 开始轮询 {fpath}")

    # 等待审批结果
    deadline = time.time() + 180  # 3 分钟超时
    poll_count = 0

    while time.time() < deadline:
        poll_count += 1
        try:
            with open(fpath, encoding="utf-8") as f:
                dd = json.load(f)
            if dd.get("result") == "approve":
                dlog(f"轮询{poll_count}次检测到 approve")
                print(json.dumps({"decision": "approve"}))
                return
            elif dd.get("result") == "deny":
                dlog(f"轮询{poll_count}次检测到 deny")
                print(json.dumps({"decision": "block"}))
                return
        except:
            pass
        time.sleep(1.5)

    # 超时 = 拒绝，并标记文件避免僵尸卡
    dlog(f"超时！轮询{poll_count}次未检测到结果")
    try:
        with open(fpath, encoding="utf-8") as f:
            dd = json.load(f)
        dd["result"] = "deny"
        dd["auto"] = True
        with open(fpath + ".tmp", "w", encoding="utf-8") as f:
            json.dump(dd, f)
        os.replace(fpath + ".tmp", fpath)
    except:
        pass
    print(json.dumps({"decision": "block"}))


if __name__ == "__main__":
    main()
