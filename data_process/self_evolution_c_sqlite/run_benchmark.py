#!/usr/bin/env python3
"""
自进化 Benchmark C — SQLite数据库类
===================================
在同一个 GA 进程中依次完成 3 个任务，
考察 Agent 复用数据库探索和SQL查询经验的能力。
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

TASK_FILES = [
    "/mnt/d/work/temp/task_c1.md",
    "/mnt/d/work/temp/task_c2.md",
    "/mnt/d/work/temp/task_c3.md",
]
ANSWER_FILES = [
    "/mnt/d/work/temp/answer_c1.json",
    "/mnt/d/work/temp/answer_c2.json",
    "/mnt/d/work/temp/answer_c3.json",
]
EXPECTED_DIR = "/mnt/d/work/temp/ans"
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


def deep_compare(ans, exp):
    """递归比较 JSON 结构"""
    if isinstance(exp, dict):
        if not isinstance(ans, dict):
            return False
        for k in exp:
            if k not in ans:
                return False
            if not deep_compare(ans[k], exp[k]):
                return False
        return True
    elif isinstance(exp, list):
        if not isinstance(ans, list) or len(ans) != len(exp):
            return False
        for a, e in zip(ans, exp):
            if not deep_compare(a, e):
                return False
        return True
    else:
        return ans == exp


def verify_answer(answer_file, expected_file):
    try:
        ans = json.load(open(answer_file))
        exp = json.load(open(expected_file))
        return deep_compare(ans, exp)
    except Exception:
        return False


def run_benchmark():
    for f in ANSWER_FILES:
        if os.path.exists(f):
            os.remove(f)

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

    def read_until_prompt(answer_file, timeout_sec):
        buf = ""
        deadline = time.time() + timeout_sec
        answer_seen = False
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
                    return os.path.exists(answer_file), buf
            else:
                if os.path.exists(answer_file) and not answer_seen:
                    answer_seen = True
                    deadline = min(deadline, time.time() + 10)
        return os.path.exists(answer_file), buf

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

    expected_map = {
        0: "answer_c1.json",
        1: "answer_c2.json",
        2: "answer_c3.json",
    }

    try:
        for i in range(3):
            print(f"[{datetime.now():%H:%M:%S}] Task {i+1}: {os.path.basename(TASK_FILES[i])} ", end="", flush=True)
            proc.stdin.write(f"'{TASK_FILES[i]}'\n")
            proc.stdin.flush()

            found, output = read_until_prompt(ANSWER_FILES[i], TIMEOUT_PER_TASK)
            turns = parse_output(output)
            verified = False
            if found:
                verified = verify_answer(
                    ANSWER_FILES[i],
                    os.path.join(EXPECTED_DIR, expected_map[i])
                )

            status = "✓" if verified else "✗"
            print(f"{status}  turns={len(turns)}")

            results.append({
                "task": i + 1,
                "task_file": TASK_FILES[i],
                "success": verified,
                "turns": len(turns),
                "turns_detail": turns,
            })

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
    print("  Benchmark C — 自进化评估")
    print("=" * 70)
    for r in results:
        s = "✅" if r["success"] else "❌"
        print(f"  Task {r['task']}: {s} | Turns: {r['turns']}")

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

    report_file = f"/mnt/d/work/temp/benchmark_c_report_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "track": "C",
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "full_output": "".join(all_output),
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  报告: {report_file}")
    return results


if __name__ == "__main__":
    run_benchmark()
