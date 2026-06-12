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
MAILBOX_DIR = os.path.join(HERE, "mailbox")
AUTO_FILE = os.path.join(HERE, "auto_approve.json")
STATUS_FILE = os.path.join(HERE, "status.json")
os.makedirs(QUEUE_DIR, exist_ok=True)
os.makedirs(MAILBOX_DIR, exist_ok=True)

PORT = 9876

HTML = r"""
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>Claude Code 遥控器</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;
     background:#1a1a2e;color:#eee;min-height:100vh;padding:16px;padding-bottom:130px}
.header{text-align:center;padding:16px 0 8px}
.header h1{font-size:22px;color:#e94560}
.header p{font-size:12px;color:#888;margin-top:2px}
/* 状态栏 */
.status-bar{background:#16213e;border-radius:10px;padding:10px 14px;margin:8px 0;
            border:1px solid #0f3460;font-size:13px;display:flex;align-items:center;justify-content:space-between}
.status-bar .left{display:flex;align-items:center;gap:6px}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%}
.dot.busy{background:#e94560;animation:pulse 1.5s infinite}
.dot.idle{background:#555}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
/* 自动批准 */
.auto-bar{background:#16213e;border-radius:10px;padding:10px 14px;margin:8px 0;
          border:1px solid #0f3460;display:flex;align-items:center;justify-content:space-between}
.auto-bar .label{font-size:14px}
.auto-bar .desc{font-size:11px;color:#888;margin-top:2px}
.auto-bar .countdown{font-size:11px;color:#00b894;margin-top:2px}
.auto-bar.active{border-color:#00b894}
.toggle{position:relative;width:48px;height:26px;flex-shrink:0}
.toggle input{opacity:0;width:0;height:0}
.toggle .slider{position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;
                background:#555;border-radius:26px;transition:.3s}
.toggle .slider:before{content:"";position:absolute;height:20px;width:20px;
                        left:3px;bottom:3px;background:#fff;border-radius:50%;transition:.3s}
.toggle input:checked+.slider{background:#00b894}
.toggle input:checked+.slider:before{transform:translateX(22px)}
/* 卡片 */
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
.empty{text-align:center;padding:50px 20px;color:#555}
.empty .icon{font-size:60px;margin-bottom:16px}
.history{margin-top:16px}
.history .item{font-size:12px;color:#555;padding:4px 0;border-bottom:1px solid #0f3460}
.status-approved{color:#00b894}
.status-denied{color:#e94560}
/* 消息框 */
.msg-bar{position:fixed;bottom:0;left:0;right:0;background:#16213e;
         padding:10px 16px;border-top:1px solid #0f3460;display:flex;gap:8px;z-index:100}
.msg-bar input{flex:1;padding:12px;border-radius:10px;border:1px solid #0f3460;
               background:#1a1a2e;color:#eee;font-size:15px;outline:none}
.msg-bar input:focus{border-color:#e94560}
.msg-bar button{padding:12px 16px;border-radius:10px;border:none;background:#e94560;
                color:#fff;font-size:15px;font-weight:bold;cursor:pointer}
.msg-bar button:active{background:#d63031}
.toast{position:fixed;bottom:72px;left:50%;transform:translateX(-50%);
       background:#00b894;color:#fff;padding:8px 22px;border-radius:20px;
       font-size:13px;z-index:200;pointer-events:none;transition:opacity .3s}
.refresh{position:fixed;bottom:72px;right:16px;background:#0f3460;color:#fff;
         border:none;border-radius:50%;width:40px;height:40px;font-size:20px;cursor:pointer;z-index:50}
</style>
</head>
<body>
<div class="header"><h1>🍎 Claude Code 遥控器</h1><p id="stat">就绪</p></div>

<div class="status-bar">
  <div class="left">
    <span class="dot idle" id="statusDot"></span>
    <span id="statusText" style="font-size:13px">空闲</span>
  </div>
  <span style="font-size:11px;color:#666" id="statusTime"></span>
</div>

<div class="auto-bar" id="autoBar">
  <div>
    <div class="label">⚡ 自动批准</div>
    <div class="desc" id="autoDesc">关闭 · 每次手动确认</div>
    <div class="countdown" id="autoCountdown" style="display:none"></div>
  </div>
  <label class="toggle">
    <input type="checkbox" id="autoToggle" onchange="toggleAuto()">
    <span class="slider"></span>
  </label>
</div>

<div id="list"></div>
<div id="history" class="history"></div>
<button class="refresh" onclick="load()">↻</button>

<div class="msg-bar">
  <input type="text" id="msgInput" placeholder="给 Claude 发消息..." onkeydown="if(event.key==='Enter')sendMsg()">
  <button onclick="sendMsg()">发送</button>
</div>
<div class="toast" id="toast" style="opacity:0"></div>

<script>
const BASE=location.pathname.replace(/\/+$/,'');
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
    let hh='';
    for(let h of data.history.slice(0,20)){
      let cls=h.result==='approve'?'status-approved':'status-denied';
      let icon=h.auto?'⚡':'';
      hh+=`<div class="item"><span class="${cls}">${h.result==='approve'?'✓':'✕'}${icon}</span> ${h.tool}: ${h.detail.substring(0,50)}</div>`;
    }
    document.getElementById('history').innerHTML=hh;
  }catch(e){
    document.getElementById('stat').textContent='连接失败: '+e.message;
  }
  // 加载状态 + 自动批准
  try{
    let s=await fetch(BASE+'/api/status');
    let st=await s.json();
    let dot=document.getElementById('statusDot');
    let txt=document.getElementById('statusText');
    let tm=document.getElementById('statusTime');
    if(st.last_event&&st.last_time){
      dot.className='dot busy';
      txt.textContent=st.last_event;
      tm.textContent=st.last_time;
    }else{
      dot.className='dot idle';
      txt.textContent='空闲';
      tm.textContent='';
    }
    // 自动批准
    if(st.auto&&st.auto.enabled){
      document.getElementById('autoToggle').checked=true;
      document.getElementById('autoBar').classList.add('active');
      let remain=Math.max(0,Math.ceil((st.auto.until-Date.now()/1000)/60));
      document.getElementById('autoDesc').textContent='开启 · '+st.auto.minutes+'分钟';
      if(remain>0){
        document.getElementById('autoCountdown').style.display='block';
        document.getElementById('autoCountdown').textContent='剩余约 '+remain+' 分钟';
      }
    }else{
      document.getElementById('autoToggle').checked=false;
      document.getElementById('autoBar').classList.remove('active');
      document.getElementById('autoDesc').textContent='关闭 · 每次手动确认';
      document.getElementById('autoCountdown').style.display='none';
    }
  }catch(e){}
}
async function toggleAuto(){
  let on=document.getElementById('autoToggle').checked;
  await fetch(BASE+'/api/auto-approve',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({enabled:on,minutes:5})});
  load();
}
async function decide(id,result){
  await fetch(BASE+'/api/decide',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id,result})});
  load();
}
async function sendMsg(){
  let input=document.getElementById('msgInput');
  let text=input.value.trim();
  if(!text)return;
  try{
    let r=await fetch(BASE+'/api/message',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text})});
    if(r.ok){input.value='';toast('✅ 已发送给 Claude')}
    else{toast('❌ 失败')}
  }catch(e){toast('❌ 连接失败')}
}
function toast(msg){
  let t=document.getElementById('toast');
  t.textContent=msg;t.style.opacity=1;
  setTimeout(()=>t.style.opacity=0,2000);
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
        elif p.path == "/api/status":
            # 合并状态信息
            status = {}
            if os.path.exists(STATUS_FILE):
                try:
                    with open(STATUS_FILE, encoding="utf-8") as f:
                        status = json.load(f)
                except:
                    pass
            # 自动批准状态
            auto = None
            if os.path.exists(AUTO_FILE):
                try:
                    with open(AUTO_FILE, encoding="utf-8") as f:
                        auto = json.load(f)
                except:
                    pass
            # 未读消息数
            unread = 0
            try:
                for fn in os.listdir(MAILBOX_DIR):
                    fpath = os.path.join(MAILBOX_DIR, fn)
                    with open(fpath, encoding="utf-8") as f:
                        md = json.load(f)
                    if not md.get("read"):
                        unread += 1
            except:
                pass
            status["auto"] = auto
            status["unread_messages"] = unread
            self._send(json.dumps(status), "application/json")
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
        elif p.path == "/api/auto-approve":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            data = json.loads(body)
            enabled = data.get("enabled", False)
            minutes = data.get("minutes", 5)
            if enabled:
                aa = {
                    "enabled": True,
                    "minutes": minutes,
                    "until": time.time() + minutes * 60,
                    "started_at": time.strftime("%H:%M:%S"),
                }
                with open(AUTO_FILE + ".tmp", "w", encoding="utf-8") as f:
                    json.dump(aa, f)
                os.replace(AUTO_FILE + ".tmp", AUTO_FILE)
            else:
                if os.path.exists(AUTO_FILE):
                    os.remove(AUTO_FILE)
            self._send(json.dumps({"ok": True, "auto": aa if enabled else None}), "application/json")
        elif p.path == "/api/message":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            data = json.loads(body)
            text = data.get("text", "").strip()
            if text:
                mid = f"{int(time.time())}_{os.urandom(3).hex()}.json"
                msg = {
                    "text": text[:1000],
                    "time": time.strftime("%m-%d %H:%M:%S"),
                    "created_at": time.time(),
                    "read": False,
                }
                with open(os.path.join(MAILBOX_DIR, mid), "w", encoding="utf-8") as f:
                    json.dump(msg, f, ensure_ascii=False)
                self._send(json.dumps({"ok": True}), "application/json")
            else:
                self._send(json.dumps({"ok": False, "error": "empty"}), "application/json")

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
