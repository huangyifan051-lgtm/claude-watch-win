#!/usr/bin/env python3
"""
本地审批 Web 服务器 — 手机浏览器打开就能点批准/拒绝
====================================================
启动: python approve_server.py
手机访问: http://你的电脑IP:9876

Claude Code 需要批准时:
1. 创建审批请求文件 → 2. Bark 通知你 → 3. 你打开手机网页点按钮 → 4. Claude 继续执行
"""
import json
import os
import time
import sys
import re
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE_DIR = os.path.join(HERE, "approvals")
os.makedirs(QUEUE_DIR, exist_ok=True)

PORT = 9876

HTML = r"""
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>Claude Code 审批</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;
     background:#1a1a2e;color:#eee;min-height:100vh;padding:16px}
.header{text-align:center;padding:20px 0 10px}
.header h1{font-size:24px;color:#e94560}
.header p{font-size:13px;color:#888;margin-top:4px}
.card{background:#16213e;border-radius:12px;padding:16px;margin:12px 0;
      border:1px solid #0f3460}
.card .tool{font-size:13px;color:#e94560;font-weight:bold;margin-bottom:4px}
.card .detail{font-size:14px;color:#ccc;word-break:break-all;margin-bottom:4px}
.card .meta{font-size:11px;color:#666}
.card .actions{margin-top:12px;display:flex;gap:10px}
.btn{flex:1;padding:14px;border:none;border-radius:10px;font-size:16px;
     font-weight:bold;cursor:pointer;transition:0.2s}
.btn-approve{background:#00b894;color:#fff}
.btn-approve:active{background:#00a381}
.btn-deny{background:#e94560;color:#fff}
.btn-deny:active{background:#d63031}
.empty{text-align:center;padding:60px 20px;color:#555}
.empty .icon{font-size:60px;margin-bottom:16px}
.history{margin-top:20px}
.history .item{font-size:12px;color:#555;padding:4px 0;border-bottom:1px solid #0f3460}
.status-approved{color:#00b894}
.status-denied{color:#e94560}
.refresh{position:fixed;bottom:16px;right:16px;background:#0f3460;color:#fff;
         border:none;border-radius:50%;width:48px;height:48px;font-size:24px;cursor:pointer}
</style>
</head>
<body>
<div class="header"><h1>🍎 Claude Code 审批</h1><p id="stat">就绪</p></div>
<div id="list"></div>
<div id="history" class="history"></div>
<button class="refresh" onclick="load()">↻</button>
<script>
const BASE = location.pathname.replace(/\/+$/,'');
async function load(){
  try{
    let r=await fetch(BASE+'/api/list');
    let data=await r.json();
    document.getElementById('stat').textContent=data.items.length+' 个待审批';
    let html='';
    if(data.items.length===0){
      html='<div class="empty"><div class="icon">✅</div><div>没有待审批的操作</div></div>';
    }
    for(let item of data.items){
      html+=`<div class="card">
        <div class="tool">${item.tool}</div>
        <div class="detail">${item.detail}</div>
        <div class="meta">${item.time} · ${item.project}</div>
        <div class="actions">
          <button class="btn btn-deny" onclick="decide('${item.id}','deny')">✕ 拒绝</button>
          <button class="btn btn-approve" onclick="decide('${item.id}','approve')">✓ 批准</button>
        </div>
      </div>`;
    }
    document.getElementById('list').innerHTML=html;
    // history
    let hh='';
    for(let h of data.history.slice(0,20)){
      let cls=h.result==='approve'?'status-approved':'status-denied';
      hh+=`<div class="item"><span class="${cls}">${h.result==='approve'?'✓':'✕'}</span> ${h.tool}: ${h.detail.substring(0,50)}</div>`;
    }
    document.getElementById('history').innerHTML=hh;
  }catch(e){
    document.getElementById('stat').textContent='连接失败: '+e.message;
  }
}
async function decide(id,result){
  await fetch(BASE+'/api/decide',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id,result})});
  load();
}
setInterval(load,3000);
load();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # 安静模式

    def _send(self, content, ct="text/html; charset=utf-8", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if isinstance(content, str):
            content = content.encode("utf-8")
        self.wfile.write(content)

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/" or p.path == "":
            self._send(HTML)
        elif p.path == "/api/list":
            items = []
            history = []
            for fname in sorted(os.listdir(QUEUE_DIR)):
                fpath = os.path.join(QUEUE_DIR, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        d = json.load(f)
                    d["id"] = fname
                    if d.get("result"):
                        history.append(d)
                    else:
                        items.append(d)
                except:
                    pass
            self._send(json.dumps({"items": items, "history": history}), "application/json")
        else:
            self._send("404", code=404)

    def do_POST(self):
        p = urlparse(self.path)
        if p.path == "/api/decide":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            data = json.loads(body)
            fid = data.get("id", "")
            result = data.get("result", "deny")
            fpath = os.path.join(QUEUE_DIR, re.sub(r"[^a-zA-Z0-9_.-]", "_", fid))
            if os.path.exists(fpath):
                with open(fpath, encoding="utf-8") as f:
                    d = json.load(f)
                d["result"] = result
                d["decided_at"] = time.time()
                with open(fpath + ".tmp", "w", encoding="utf-8") as f:
                    json.dump(d, f)
                os.replace(fpath + ".tmp", fpath)
            self._send(json.dumps({"ok": True}), "application/json")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def create_approval(tool_name, detail, project="", timeout=120):
    """创建一个审批请求，返回请求 ID。Claude Code hook 调用此函数。"""
    pid = f"{int(time.time())}_{os.urandom(3).hex()}.json"
    d = {
        "tool": tool_name,
        "detail": detail[:500],
        "project": project,
        "time": time.strftime("%H:%M:%S"),
        "created_at": time.time(),
        "timeout": timeout,
        "result": None,
    }
    with open(os.path.join(QUEUE_DIR, pid), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    return pid


def wait_approval(pid, poll_interval=1):
    """等待审批结果。返回 'approve' 或 'deny' 或 None(超时)"""
    fpath = os.path.join(QUEUE_DIR, pid)
    if not os.path.exists(fpath):
        return None
    with open(fpath, encoding="utf-8") as f:
        d = json.load(f)
    timeout = d.get("timeout", 120)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with open(fpath, encoding="utf-8") as f:
                d = json.load(f)
            if d.get("result"):
                return d["result"]
        except:
            pass
        time.sleep(poll_interval)
    # 超时 = 视为拒绝
    return "deny"


def cleanup_old():
    """清理过期审批"""
    now = time.time()
    for fname in os.listdir(QUEUE_DIR):
        fpath = os.path.join(QUEUE_DIR, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                d = json.load(f)
            if d.get("result") or (now - d.get("created_at", 0) > 3600):
                os.remove(fpath)
        except:
            try:
                os.remove(fpath)
            except:
                pass


def run_server():
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    hostname = socket.gethostname()
    # 获取局域网 IP
    import subprocess
    ip = "localhost"
    try:
        for line in subprocess.check_output("ipconfig", shell=True, text=True).split("\n"):
            if "IPv4" in line and "172" in line:
                m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                if m:
                    ip = m.group(1)
                    break
    except:
        pass
    print(f"✅ 审批服务器已启动!")
    print(f"   手机浏览器打开: http://{ip}:{PORT}")
    print(f"   按 Ctrl+C 停止")
    try:
        while True:
            server.handle_request()
    except KeyboardInterrupt:
        print("\n服务器已停止")

if __name__ == "__main__":
    run_server()
