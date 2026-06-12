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
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def get_local_ip():
    """获取局域网 IP"""
    for line in subprocess.check_output("ipconfig", shell=True, text=True).split("\n"):
        if "IPv4" in line:
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
            if m:
                ip = m.group(1)
                if ip.startswith("172.") or ip.startswith("192.168.") or ip.startswith("10."):
                    return ip
    return socket.gethostbyname(socket.gethostname())


def send_bark(url, title, body):
    try:
        full = url.rstrip("/")
        p = urllib.parse.urlencode({"title": title, "body": body, "group": "Claude Code", "isArchive": "1"})
        urllib.request.urlopen(f"{full}/{urllib.parse.quote(title)}/{urllib.parse.quote(body)}?{p}", timeout=8)
    except:
        pass


def main():
    # 未启用 → 不输出任何内容, Claude Code 退回到键盘确认
    if not enabled():
        return

    # 读取 Claude Code 传入的 JSON
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except:
        data = {}

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

    # 发 Bark 通知
    env = load_env()
    bark = os.environ.get("BARK_URL") or env.get("BARK_URL", "")
    ip = get_local_ip()
    approve_url = f"http://{ip}:{PORT}"

    if bark:
        body = f"{detail}\n\n🌐 审批: {approve_url}"
        send_bark(bark, f"🔐 {tool}", body)

    # 等待审批结果
    fpath = os.path.join(QUEUE_DIR, pid)
    deadline = time.time() + 180  # 3 分钟超时

    while time.time() < deadline:
        try:
            with open(fpath, encoding="utf-8") as f:
                dd = json.load(f)
            if dd.get("result") == "approve":
                print(json.dumps({"decision": "approve"}))
                return
            elif dd.get("result") == "deny":
                print(json.dumps({"decision": "block"}))
                return
        except:
            pass
        time.sleep(1.5)

    # 超时 = 拒绝
    print(json.dumps({"decision": "block"}))


if __name__ == "__main__":
    main()
