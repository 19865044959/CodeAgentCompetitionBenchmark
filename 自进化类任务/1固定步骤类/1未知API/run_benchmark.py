#!/usr/bin/env python3
"""
自进化任务 Benchmark 自动化脚本
================================
启动 GA (GenericAgent)，依次完成 3 个自进化任务，
统计每个任务的回合数和成功与否。
"""

import subprocess
import threading
import re
import json
import time
import os
import sys
import signal
import argparse
from datetime import datetime

# ── 配置 ──────────────────────────────────────────────────
GA_DIR = "/mnt/d/work/Hackthon/GenericAgent"
GA_SCRIPT = "agentmain.py"

# 任务描述文件
TASK_FILES = [
    "/mnt/d/work/temp/task_1_beijing.md",
    "/mnt/d/work/temp/task_2_nanjing.md",
    "/mnt/d/work/temp/task_3_chengdu.md",
]

# 答案文件（Agent 产出的）
ANSWER_FILES = [
    "/mnt/d/work/temp/answer_1.json",
    "/mnt/d/work/temp/answer_2.json",
    "/mnt/d/work/temp/answer_3.json",
]

TIMEOUT_PER_TASK = 300  # 每题最长 5 分钟
INTER_TASK_DELAY = 3    # 题间等待秒数


def parse_output(output: str):
    """
    解析 GA 的 verbose 输出，提取每个 task 的:
      - turns: LLM 调用次数
      - turns_detail: 每轮的 summary 和工具调用
    """
    turns = []
    current_turn = None

    # 匹配 "LLM Running (Turn N) ..." 或 "Turn N ..."
    for line in output.split("\n"):
        m = re.match(r".*LLM Running \(Turn (\d+)\)", line)
        if not m:
            m = re.match(r"\*\*Turn (\d+) \.\.\.\*\*", line)
        if m:
            if current_turn:
                turns.append(current_turn)
            current_turn = {"num": int(m.group(1)), "summary": "", "tools": []}
            continue

        if current_turn is None:
            continue

        # 提取 summary
        sm = re.match(r"<summary>(.*?)</summary>", line.strip())
        if sm:
            current_turn["summary"] = sm.group(1).strip()

        # 提取工具调用
        tm = re.match(r"🛠️ (\w+)\(.*", line.strip())
        if tm:
            current_turn["tools"].append(tm.group(1))

    if current_turn:
        turns.append(current_turn)

    return turns


def run_benchmark():
    """主流程: 启动 GA interactive 模式, 依次喂入任务, 收集结果"""

    # 清除旧答案文件
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
        bufsize=1,
    )

    all_output = []
    results = []
    output_lock = threading.Lock()
    current_task_idx = [0]
    task_segments = [[] for _ in TASK_FILES]  # 每个 task 对应的输出行
    prompt_seen = [False] * len(TASK_FILES)

    def read_stdout():
        """后台线程: 持续读取 GA 输出"""
        for line in iter(proc.stdout.readline, ""):
            with output_lock:
                all_output.append(line)
                idx = current_task_idx[0]
                if idx < len(task_segments):
                    task_segments[idx].append(line)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()

    def wait_for_prompt(timeout=60):
        """等待 GA 输出 '> ' 提示符 (表示当前任务完成)"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with output_lock:
                # 检查最近几行是否出现了独立的 '> '
                recent = "".join(all_output[-5:] if len(all_output) >= 5 else all_output)
                # GA prompt 特征: 行尾出现 '> ' (单独一行)
                lines = all_output[-10:] if len(all_output) >= 10 else all_output
                for ln in lines:
                    if ln.rstrip() == ">":
                        return True
            time.sleep(1)
        return False

    def wait_for_answer_file(expected_file, timeout=120):
        """等待答案文件出现"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if os.path.exists(expected_file):
                return True
            time.sleep(1)
        return False

    try:
        # ── Task 1 ──
        print(f"[{datetime.now():%H:%M:%S}] 发送 Task 1: {os.path.basename(TASK_FILES[0])}")
        current_task_idx[0] = 0
        proc.stdin.write(f"'{TASK_FILES[0]}'\n")
        proc.stdin.flush()

        # 等待答案文件 (更可靠的完成信号)
        ok = wait_for_answer_file(ANSWER_FILES[0], timeout=TIMEOUT_PER_TASK)
        # 额外等一小段等 prompt 回来
        wait_for_prompt(timeout=30)

        turns_detail = parse_output("".join(task_segments[0]))
        results.append({
            "task": 1,
            "task_file": TASK_FILES[0],
            "success": ok and os.path.exists(ANSWER_FILES[0]),
            "turns": len(turns_detail),
            "turns_detail": turns_detail,
        })
        print(f"[{datetime.now():%H:%M:%S}] Task 1 {'✓' if results[-1]['success'] else '✗'} — {results[-1]['turns']} turns")

        # ── Task 2 ──
        print(f"[{datetime.now():%H:%M:%S}] 发送 Task 2: {os.path.basename(TASK_FILES[1])}")
        current_task_idx[0] = 1
        proc.stdin.write(f"'{TASK_FILES[1]}'\n")
        proc.stdin.flush()

        ok = wait_for_answer_file(ANSWER_FILES[1], timeout=TIMEOUT_PER_TASK)
        wait_for_prompt(timeout=30)

        turns_detail = parse_output("".join(task_segments[1]))
        results.append({
            "task": 2,
            "task_file": TASK_FILES[1],
            "success": ok and os.path.exists(ANSWER_FILES[1]),
            "turns": len(turns_detail),
            "turns_detail": turns_detail,
        })
        print(f"[{datetime.now():%H:%M:%S}] Task 2 {'✓' if results[-1]['success'] else '✗'} — {results[-1]['turns']} turns")

        # ── Task 3 ──
        print(f"[{datetime.now():%H:%M:%S}] 发送 Task 3: {os.path.basename(TASK_FILES[2])}")
        current_task_idx[0] = 2
        proc.stdin.write(f"'{TASK_FILES[2]}'\n")
        proc.stdin.flush()

        ok = wait_for_answer_file(ANSWER_FILES[2], timeout=TIMEOUT_PER_TASK)
        wait_for_prompt(timeout=30)

        turns_detail = parse_output("".join(task_segments[2]))
        results.append({
            "task": 3,
            "task_file": TASK_FILES[2],
            "success": ok and os.path.exists(ANSWER_FILES[2]),
            "turns": len(turns_detail),
            "turns_detail": turns_detail,
        })
        print(f"[{datetime.now():%H:%M:%S}] Task 3 {'✓' if results[-1]['success'] else '✗'} — {results[-1]['turns']} turns")

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        # 清理
        try:
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    # ── 输出报告 ──
    print("\n" + "=" * 70)
    print("  Benchmark 结果")
    print("=" * 70)

    for r in results:
        status = "✅ PASS" if r["success"] else "❌ FAIL"
        print(f"\n  Task {r['task']}: {status} | Turns: {r['turns']}")
        print(f"  文件: {os.path.basename(r['task_file'])}")
        if r["turns_detail"]:
            print(f"  回合详情:")
            for t in r["turns_detail"]:
                tools_str = " → ".join(t["tools"]) if t["tools"] else "(无工具调用)"
                summary = t["summary"][:100] if t["summary"] else "(无summary)"
                print(f"    Turn {t['num']:2d}: {summary}")
                if t["tools"]:
                    print(f"           🛠️  {tools_str}")

    # 自进化评估
    if all(r["success"] for r in results):
        t1, t2, t3 = [r["turns"] for r in results]
        print(f"\n  ── 自进化评估 ──")
        print(f"  Task 1 (探索期): {t1} turns  (基准 exp=20)")
        print(f"  Task 2 (复用期): {t2} turns  (基准 exp=1)")
        print(f"  Task 3 (复用期): {t3} turns  (基准 exp=1)")

        # 按公式打分
        scores = []
        exps = [20, 1, 1]
        for i, (r, exp) in enumerate(zip(results, exps)):
            actual = max(r["turns"], 1)
            score = round(exp / actual * 20, 1)
            scores.append(score)
            print(f"  Task {i+1} 得分: {exp}/{actual} × 20 = {score}")
        print(f"  总分: {sum(scores):.1f} / 60")

    # 保存详细结果
    report_file = f"/mnt/d/work/temp/benchmark_report_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "full_output": "".join(all_output),
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  详细报告已保存至: {report_file}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent 自进化 Benchmark")
    parser.add_argument("--timeout", type=int, default=300, help="每题超时秒数")
    args = parser.parse_args()

    TIMEOUT_PER_TASK = args.timeout  # type: ignore

    run_benchmark()
