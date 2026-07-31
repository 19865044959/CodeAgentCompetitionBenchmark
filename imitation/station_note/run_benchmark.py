#!/usr/bin/env python3
"""
自进化 Benchmark D — 仿照样板类
===============================
在同一个 GA 进程中依次完成 3 个任务，
考察 Agent 复用CSV转换规则归纳能力。
"""

import subprocess
import re
import json
import time
import os
import sys
import signal
from datetime import datetime

GA_DIR = "/mnt/d/work/Hackthon/GenericAgent"
GA_SCRIPT = "agentmain.py"

# 任务描述文件 (spec.md)
TASK_SPECS = [
    "/mnt/d/work/temp/cases/ws_1/spec.md",
    "/mnt/d/work/temp/cases/ws_2/spec.md",
    "/mnt/d/work/temp/cases/ws_3/spec.md",
]
# 工作目录
WORK_DIRS = [
    "/mnt/d/work/temp/cases/ws_1",
    "/mnt/d/work/temp/cases/ws_2",
    "/mnt/d/work/temp/cases/ws_3",
]
TIMEOUT_PER_TASK = 300


def parse_output(text: str):
    turns = []
    cur = None
    for line in text.split("\n"):
        m = re.match(r".*LLM Running \(Turn (\d+)\)", line)
        if m:
            if cur:
                turns.append(cur)
            cur = {"num": int(m.group(1)), "summary": "", "tools": []}
            continue
        if cur is None:
            continue
        sm = re.match(r"<summary>(.*?)</summary>", line.strip())
        if sm:
            cur["summary"] = sm.group(1).strip()
        tm = re.match(r"🛠️ (\w+)\(.*", line.strip())
        if tm:
            cur["tools"].append(tm.group(1))
    if cur:
        turns.append(cur)
    return turns


def extract_token(output_text: str):
    """从输出中提取 TOKEN: xxx"""
    for line in output_text.split("\n"):
        m = re.search(r"TOKEN:\s*([a-f0-9]+)", line)
        if m:
            return m.group(1)
    return None


def run_benchmark():
    print(f"[{datetime.now():%H:%M:%S}] 启动 GenericAgent ...")
    proc = subprocess.Popen(
        [sys.executable, GA_SCRIPT],
        cwd=GA_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=0,
    )

    all_output = []
    results = []

    import select

    def read_until_token(timeout_sec):
        buf = ""
        deadline = time.time() + timeout_sec
        fd = proc.stdout.fileno()
        while time.time() < deadline:
            r, _, _ = select.select([fd], [], [], 0.3)
            if r:
                chunk = os.read(fd, 4096).decode("utf-8", errors="replace")
                if not chunk:
                    break
                buf += chunk
                all_output.append(chunk)
                if buf.endswith("> "):
                    time.sleep(0.3)
                    return buf
            else:
                # Check if TOKEN appeared in output
                if "TOKEN:" in buf:
                    deadline = min(deadline, time.time() + 5)
        return buf

    # 等待 GA 就绪
    print(f"[{datetime.now():%H:%M:%S}] 等待 GA 就绪 ...")
    init_buf = ""
    fd = proc.stdout.fileno()
    while True:
        r, _, _ = select.select([fd], [], [], 0.5)
        if r:
            chunk = os.read(fd, 4096).decode("utf-8", errors="replace")
            if not chunk:
                break
            init_buf += chunk
            all_output.append(chunk)
            if init_buf.endswith("> "):
                break
    print(f"[{datetime.now():%H:%M:%S}] GA 就绪")

    try:
        for i in range(3):
            print(f"[{datetime.now():%H:%M:%S}] Task {i+1}: {os.path.basename(TASK_SPECS[i])} ", end="", flush=True)
            proc.stdin.write(f"'{TASK_SPECS[i]}'\n")
            proc.stdin.flush()

            output = read_until_token(TIMEOUT_PER_TASK)
            turns = parse_output(output)
            token = extract_token(output)

            results.append({
                "task": i + 1,
                "spec_file": TASK_SPECS[i],
                "work_dir": WORK_DIRS[i],
                "success": token is not None,
                "token": token,
                "turns": len(turns),
                "turns_detail": turns,
            })

            status = f"✓ TOKEN={token}" if token else "✗"
            print(f"{status}  turns={len(turns)}")

            for t in turns:
                summary = t["summary"][:120] if t["summary"] else "(无summary)"
                tools = " → ".join(t["tools"]) if t["tools"] else "(无工具)"
                print(f"    Turn {t['num']:2d}: {summary}")
                if t["tools"]:
                    print(f"           🛠️  {tools}")

    except Exception as e:
        print(f"\n[ERROR] {e}")
    finally:
        try:
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    print("\n" + "=" * 70)
    print("  Benchmark D (station_note) — 自进化评估")
    print("=" * 70)
    for r in results:
        s = "✅" if r["success"] else "❌"
        print(f"  Task {r['task']}: {s} | Turns: {r['turns']} | Token: {r.get('token','N/A')}")

    if len(results) >= 1:
        print(f"\n  ── 自进化评估 ──")
        exps = [20, 1, 1]
        for i, r in enumerate(results):
            exp = exps[i]
            print(f"  Task {r['task']}: {r['turns']} turns  (exp={exp})")
        scores = []
        for i, r in enumerate(results):
            actual = max(r["turns"], 1)
            score = round(exps[i] / actual * 20, 1)
            scores.append(score)
            print(f"  Task {r['task']} 得分: {exps[i]}/{actual}×20 = {score}")
        print(f"  总分: {sum(scores):.1f} / {len(exps[:len(results)])*20}")

    report_file = f"/mnt/d/work/temp/benchmark_d_report_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "track": "D",
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "full_output": "".join(all_output),
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  报告: {report_file}")
    return results


if __name__ == "__main__":
    run_benchmark()
