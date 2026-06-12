#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取手机发来的消息 — 供 Claude Code 使用
用法: python read_mailbox.py        # 读取并标记已读
     python read_mailbox.py --peek  # 只看不标记
     python read_mailbox.py --json  # JSON 输出(供hook用)
"""
import sys, os, json, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
MAILBOX_DIR = os.path.join(HERE, "mailbox")
os.makedirs(MAILBOX_DIR, exist_ok=True)


def list_unread():
    """返回所有未读消息"""
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
    return msgs


def mark_read(msg_id):
    """标记消息为已读"""
    fpath = os.path.join(MAILBOX_DIR, msg_id)
    if os.path.exists(fpath):
        try:
            with open(fpath, encoding="utf-8") as f:
                d = json.load(f)
            d["read"] = True
            with open(fpath + ".tmp", "w", encoding="utf-8") as f:
                json.dump(d, f)
            os.replace(fpath + ".tmp", fpath)
        except:
            pass


def main():
    peek = "--peek" in sys.argv
    json_out = "--json" in sys.argv

    msgs = list_unread()

    if json_out:
        print(json.dumps(msgs, ensure_ascii=False))
        if not peek:
            for m in msgs:
                mark_read(m["id"])
        return

    if not msgs:
        print("📭 没有新消息")
        return

    print(f"📬 {len(msgs)} 条来自手机的消息:\n")
    for i, m in enumerate(msgs, 1):
        print(f"  [{i}] {m['time']}")
        print(f"      {m['text']}")
        print()

    if not peek:
        for m in msgs:
            mark_read(m["id"])
        print("✅ 已标记为已读")


if __name__ == "__main__":
    main()
