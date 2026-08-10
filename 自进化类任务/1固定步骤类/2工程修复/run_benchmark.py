#!/usr/bin/env python3
"""
自进化任务 Benchmark 自动化脚本
================================
依次完成 3 个自进化任务（文件修复类），
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

TASK_FILES = [
    "/mnt/d/work/CodeAgentCompetitionBenchmark/self_evolution_b_fix/task_1_alpha.md",
    "/mnt/d/work/CodeAgentCompetitionBenchmark/self_evolution_b_fix/task_2_beta.md",
    "/mnt/d/work/CodeAgentCompetitionBenchmark/self_evolution_b_fix/task_3_gamma.md",
]

BENCH_DIR = "/mnt/d/work/CodeAgentCompetitionBenchmark/self_evolution_b_fix"
EXPECTED_FILES = [
    f"{BENCH_DIR}/expected_1.json",
    f"{BENCH_DIR}/expected_2.json",
    f"{BENCH_DIR}/expected_3.json",
]

TIMEOUT_PER_TASK = 300
INTER_TASK_DELAY = 3


def load_expected_token(expected_path):
    """从 expected_N.json 读取 token"""
    return json.loads(open(expected_path).read())["token"]


def token_found(output_lines, expected_token):
    """检查输出中是否包含正确的 TOKEN"""
    for line in output_lines:
        if f"TOKEN: {expected_token}" in line:
            return True
    return False


def parse_output(output: str):
    """解析 GA 输出，提取回合信息"""
    turns = []
    current_turn = None
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
        sm = re.match(r"<summary>(.*?)</summary>", line.strip())
        if sm:
            current_turn["summary"] = sm.group(1).strip()
    if current_turn:
        turns.append(current_turn)
    return turns


def run_benchmark():
    """主流程"""

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
    task_segments = [[] for _ in TASK_FILES]
    current_task_idx = [0]
    output_lock = threading.Lock()

    def read_stdout():
        for line in iter(proc.stdout.readline, ""):
            with output_lock:
                all_output.append(line)
                idx = current_task_idx[0]
                if idx < len(task_segments):
                    task_segments[idx].append(line)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()

    def wait_for_token(expected_token, timeout=120):
        """等待输出中出现 TOKEN: xxx"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with output_lock:
                lines = list(task_segments[current_task_idx[0]])
            if token_found(lines, expected_token):
                return True
            time.sleep(1)
        return False

    try:
        for i in range(3):
            task_file = TASK_FILES[i]
            expected_token = load_expected_token(EXPECTED_FILES[i])

            print(f"[{datetime.now():%H:%M:%S}] 发送 Task {i+1}: {os.path.basename(task_file)}")
            current_task_idx[0] = i
            proc.stdin.write(f"'{task_file}'\n")
            proc.stdin.flush()

            ok = wait_for_token(expected_token, timeout=TIMEOUT_PER_TASK)
            time.sleep(INTER_TASK_DELAY)

            turns_detail = parse_output("".join(task_segments[i]))
            msg = "通过" if ok else "超时或 token 不匹配"

            results.append({
                "task": i + 1,
                "task_file": task_file,
                "success": ok,
                "eval_msg": msg,
                "turns": len(turns_detail),
                "turns_detail": turns_detail,
            })
            status = "PASS" if ok else "FAIL"
            print(f"[{datetime.now():%H:%M:%S}] Task {i+1} {status} ({msg}) — {results[-1]['turns']} turns")

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
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
        status = "PASS" if r["success"] else "FAIL"
        print(f"\n  Task {r['task']}: {status} | Turns: {r['turns']} | {r['eval_msg']}")
        if r["turns_detail"]:
            for t in r["turns_detail"]:
                summary = t["summary"][:100] if t["summary"] else "(无summary)"
                print(f"    Turn {t['num']:2d}: {summary}")

    # 自进化评估
    if all(r["success"] for r in results):
        t1, t2, t3 = [r["turns"] for r in results]
        print(f"\n  ── 自进化评估 ──")
        exps = [20, 1, 1]
        scores = []
        for i, (r, exp) in enumerate(zip(results, exps)):
            actual = max(r["turns"], 1)
            score = round(exp / actual * 20, 1)
            scores.append(score)
            print(f"  Task {i+1} 得分: {exp}/{actual} × 20 = {score}")
        print(f"  总分: {sum(scores):.1f} / 60")

    report_file = f"/tmp/benchmark_report_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "full_output": "".join(all_output),
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  详细报告: {report_file}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent 自进化 Benchmark")
    parser.add_argument("--timeout", type=int, default=300, help="每题超时秒数")
    args = parser.parse_args()
    TIMEOUT_PER_TASK = args.timeout
    run_benchmark()
