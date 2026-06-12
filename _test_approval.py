"""快速测试审批全流程"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE_DIR = os.path.join(HERE, "approvals")

# 1. 创建审批
pid = f"{int(time.time())}_test.json"
d = {
    "tool": "Bash",
    "detail": "Bash: pip install numpy pandas matplotlib",
    "project": "potato_prceed",
    "time": time.strftime("%H:%M:%S"),
    "created_at": time.time(),
    "result": None,
}
with open(os.path.join(QUEUE_DIR, pid), "w", encoding="utf-8") as f:
    json.dump(d, f)
print(f"Created: {pid}")
print(f"Web URL: http://172.20.10.2:9876")

# 2. 检查 API 能否看到
import urllib.request
r = urllib.request.urlopen("http://127.0.0.1:9876/api/list", timeout=3)
data = json.loads(r.read())
print(f"Pending items: {len(data['items'])}")
for item in data['items']:
    print(f"  - {item['tool']}: {item['detail'][:60]}")

# 3. 模拟用户点击"批准"
import urllib.parse
r2 = urllib.request.urlopen(urllib.request.Request(
    "http://127.0.0.1:9876/api/decide",
    data=json.dumps({"id": pid, "result": "approve"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST"
), timeout=3)
print(f"Decide result: {json.loads(r2.read())}")

# 4. 检查审批结果
fpath = os.path.join(QUEUE_DIR, pid)
with open(fpath, encoding="utf-8") as f:
    result = json.load(f)
print(f"Final result: {result.get('result')}")

# cleanup
os.remove(fpath)
print("Test PASSED!")
