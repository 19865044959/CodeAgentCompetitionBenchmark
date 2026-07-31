#!/usr/bin/env python3
"""
推理类 & 长上下文类 Benchmark 运行器

测试 GA 的两项核心能力：
  1. 推理类：从世界新闻中识别供需变化，预测价格波动，制定交易策略
  2. 长上下文类：从跨天混杂传闻中拼凑信息，完成寻宝任务

用法:
  python3 run_benchmark.py                        # 运行全部测试
  python3 run_benchmark.py --type reasoning       # 仅运行推理类
  python3 run_benchmark.py --type long_context    # 仅运行长上下文类
  python3 run_benchmark.py --task treasure_hunt   # 运行单个任务
"""

import subprocess
import json
import time
import os
import sys
import signal
import re
import select
import shutil
from datetime import datetime
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────
GA_DIR = "/mnt/d/work/Hackthon/GenericAgent"
GA_SCRIPT = "agentmain.py"
BENCHMARK_BASE = "/mnt/d/work/CodeAgentCompetitionBenchmark/推理类&长上下文类"
TEMP_BASE = "/mnt/d/work/temp"
TIMEOUT_PER_TASK = 600  # 每题 10 分钟（推理类需要较长时间阅读和推理）

# ── 任务定义 ──────────────────────────────────────────────
TASKS = {
    "iron_price": {
        "name": "推理类 — 铁矿价格套利",
        "type": "reasoning",
        "src_dir": f"{BENCHMARK_BASE}/reasoning/iron_price_speculation",
        "task_file": "task.md",
        "answer_file": "answer.json",
        "expected_file": "ans/expected.json",
        "verify_script": "verify.py",
        "verify_method": "reasoning",
    },
    "treasure_hunt": {
        "name": "长上下文类 — 民间传闻拼图寻宝",
        "type": "long_context",
        "src_dir": f"{BENCHMARK_BASE}/long_context/treasure_hunt",
        "task_file": "task.md",
        "answer_file": "answer.json",
        "expected_file": "ans/expected.json",
        "verify_script": "verify.py",
        "verify_method": "long_context",
    },
}


def parse_output(text: str):
    """解析 GA 输出，提取每轮的 summary + tools"""
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


def setup_work_env(task_key, task_cfg):
    """设置工作环境"""
    temp_dir = TEMP_BASE
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(f"{temp_dir}/ans", exist_ok=True)

    src = task_cfg["src_dir"]

    # 拷贝任务文件
    task_file = f"{src}/{task_cfg['task_file']}"
    if os.path.exists(task_file):
        shutil.copy2(task_file, f"{temp_dir}/{task_cfg['task_file']}")

    # 拷贝期望答案到 ans/
    expected_file = f"{src}/{task_cfg['expected_file']}"
    if os.path.exists(expected_file):
        shutil.copy2(expected_file, f"{temp_dir}/ans/{os.path.basename(task_cfg['expected_file'])}")

    # 拷贝游戏状态文件（如果有）
    for subdir in ["day_states"]:
        subdir_path = f"{src}/{subdir}"
        if os.path.isdir(subdir_path):
            dest = f"{temp_dir}/{subdir}"
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(subdir_path, dest)

    # 拷贝 game_state.json（如果有）
    for extra in ["game_state.json"]:
        extra_path = f"{src}/{extra}"
        if os.path.exists(extra_path):
            shutil.copy2(extra_path, f"{temp_dir}/{extra}")

    # 清理旧答案
    answer_file = f"{temp_dir}/{task_cfg['answer_file']}"
    if os.path.exists(answer_file):
        os.remove(answer_file)


def run_verify(task_key, task_cfg, output_text):
    """运行验证脚本"""
    verify_script = f"{task_cfg['src_dir']}/{task_cfg['verify_script']}"
    answer_file = f"{TEMP_BASE}/{task_cfg['answer_file']}"

    if not os.path.exists(answer_file):
        # 搜索 GA 可能写入 answer.json 的位置
        search_dirs = [
            TEMP_BASE,
            f"{GA_DIR}/temp",
            GA_DIR,
            "/tmp",
        ]
        for search_dir in search_dirs:
            candidate = os.path.join(search_dir, task_cfg['answer_file'])
            if os.path.exists(candidate):
                shutil.copy2(candidate, answer_file)
                print(f"  📝 从 {candidate} 拷贝了 answer.json")
                break

    if not os.path.exists(answer_file):
        # 尝试从 GA 输出中提取 JSON 并保存
        json_match = re.search(r'```json\s*\n(.*?)\n```', output_text, re.DOTALL)
        if json_match:
            try:
                answer_data = json.loads(json_match.group(1))
                with open(answer_file, "w", encoding="utf-8") as f:
                    json.dump(answer_data, f, ensure_ascii=False, indent=2)
                print(f"  📝 从输出中提取并保存了 answer.json")
            except json.JSONDecodeError:
                pass
        else:
            # 尝试找到任何 JSON 对象
            for pattern in [r'\{[\s\S]*"task_id"[\s\S]*\}', r'\{[\s\S]*"question_1"[\s\S]*\}',
                          r'\{[\s\S]*"q1"[\s\S]*\}', r'\{[\s\S]*"price_prediction"[\s\S]*\}',
                          r'\{[\s\S]*"signal_detection"[\s\S]*\}']:
                json_match = re.search(pattern, output_text)
                if json_match:
                    try:
                        answer_data = json.loads(json_match.group(0))
                        with open(answer_file, "w", encoding="utf-8") as f:
                            json.dump(answer_data, f, ensure_ascii=False, indent=2)
                        print(f"  📝 从输出中提取并保存了 answer.json")
                        break
                    except json.JSONDecodeError:
                        continue

    if not os.path.exists(answer_file):
        return {
            "success": False,
            "error": "Answer file not generated",
            "details": "GA did not produce answer.json and no JSON could be extracted from output"
        }

    # 修复常见的 JSON 格式问题（中文引号等）
    try:
        with open(answer_file, "r", encoding="utf-8") as f:
            raw = f.read()
        fixed = raw.replace("\u201c", '\\"').replace("\u201d", '\\"')
        fixed = fixed.replace("\u2018", "\\'").replace("\u2019", "\\'")
        fixed = fixed.replace("\uff02", '\\"')
        with open(answer_file, "w", encoding="utf-8") as f:
            f.write(fixed)
    except Exception:
        pass
        pass  # 如果修复失败，保持原样

    # 运行验证
    expected_file = f"{task_cfg['src_dir']}/{task_cfg['expected_file']}"
    cmd = [sys.executable, verify_script, answer_file]
    if os.path.exists(expected_file):
        cmd.append(expected_file)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        # 解析 JSON 报告（最后一行非 JSON 之前）
        output_lines = result.stdout.strip().split("\n")
        json_start = 0
        json_end = len(output_lines)
        for i, line in enumerate(output_lines):
            if line.strip().startswith("{"):
                json_start = i
                break
        for i in range(len(output_lines) - 1, -1, -1):
            if output_lines[i].strip().startswith("}"):
                json_end = i + 1
                break

        json_text = "\n".join(output_lines[json_start:json_end])
        report = json.loads(json_text)
        return report
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return {"success": False, "error": str(e)}


def run_single_benchmark(task_key, task_cfg):
    """运行单个 benchmark"""
    print(f"\n{'='*70}")
    print(f"  {task_cfg['name']}")
    print(f"{'='*70}")

    # ── 启动 GA ──
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

    fd = proc.stdout.fileno()
    all_output = []

    # 等待 GA 就绪
    print(f"[{datetime.now():%H:%M:%S}] 等待 GA 就绪 ...")
    init_buf = ""
    while True:
        r, _, _ = select.select([fd], [], [], 0.5)
        if r:
            chunk = os.read(fd, 4096).decode("utf-8", errors="replace")
            if not chunk:
                break
            init_buf += chunk
            all_output.append(chunk)
            if init_buf.rstrip().endswith(">"):
                break

    # ── 执行任务 ──
    task_path = f"{TEMP_BASE}/{task_cfg['task_file']}"
    answer_file = f"{TEMP_BASE}/{task_cfg['answer_file']}"

    print(f"[{datetime.now():%H:%M:%S}] Task: {os.path.basename(task_path)}")
    proc.stdin.write(f"'{task_path}'\n")
    proc.stdin.flush()

    # 等待完成
    buf = ""
    deadline = time.time() + TIMEOUT_PER_TASK
    answer_seen = False

    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.5)
        if r:
            chunk = os.read(fd, 4096).decode("utf-8", errors="replace")
            if not chunk:
                break
            buf += chunk
            all_output.append(chunk)
            if buf.rstrip().endswith(">"):
                time.sleep(0.3)
                break
        else:
            if os.path.exists(answer_file) and not answer_seen:
                answer_seen = True
                deadline = min(deadline, time.time() + 30)

    output_text = "".join(all_output)
    turns = parse_output(output_text)

    # 打印回合详情
    for t in turns:
        summary = t["summary"][:150] if t["summary"] else "(无summary)"
        tools = " → ".join(t["tools"]) if t["tools"] else "(无工具)"
        print(f"  Turn {t['num']:2d}: {summary}")

    # ── 终止 GA ──
    try:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=5)
    except:
        proc.kill()

    # ── 验证 ──
    report = run_verify(task_key, task_cfg, output_text)

    # ── 结果 ──
    success = report.get("success", False)
    percentage = report.get("percentage", 0)
    status = "✅" if success else "❌"
    print(f"\n  {status} {task_cfg['name']}: {percentage}% (threshold: {report.get('passing_threshold', 70)}%)")

    if "questions" in report:
        for q_key, q_result in report["questions"].items():
            q_score = q_result.get("score", 0)
            q_max = q_result.get("max_score", 1)
            q_pct = round(q_score / q_max * 100, 1) if q_max > 0 else 0
            print(f"    {q_key}: {q_score}/{q_max} ({q_pct}%)")

    for d in report.get("diagnostics", []):
        print(f"    ⚠ {d}")

    return {
        "task_key": task_key,
        "task_name": task_cfg["name"],
        "task_type": task_cfg["type"],
        "success": success,
        "percentage": percentage,
        "turns": len(turns),
        "turns_detail": turns,
        "verification_report": report,
    }


def generate_report(results):
    """生成评测报告"""
    print("\n\n")
    print("=" * 80)
    print("  推理类 & 长上下文类 Benchmark — 综合评测报告")
    print("=" * 80)
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # ── 汇总 －
    reasoning_results = [r for r in results if r["task_type"] == "reasoning"]
    long_context_results = [r for r in results if r["task_type"] == "long_context"]

    print("─" * 80)
    print("  评测结果汇总")
    print("─" * 80)
    print(f"  {'任务':<30s} {'结果':>6s} {'得分':>8s} {'轮数':>6s}")
    print(f"  {'-'*30} {'-'*6} {'-'*8} {'-'*6}")

    all_pass = True
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"  {r['task_name']:<30s} {status:>6s} {r['percentage']:>7.1f}% {r['turns']:>5d}")
        if not r["success"]:
            all_pass = False

    # ── 能力维度分析 ──
    print()
    print("─" * 80)
    print("  能力维度分析")
    print("─" * 80)

    # 推理类
    if reasoning_results:
        r = reasoning_results[0]
        vr = r.get("verification_report", {})
        questions = vr.get("questions", {})
        print(f"\n  【推理类 — 经济推理能力】{'✅' if r['success'] else '❌'}")
        print(f"  综合得分: {r['percentage']}%")
        for q_key, qr in questions.items():
            q_score = qr.get("score", 0)
            q_max = qr.get("max_score", 1)
            print(f"    - {q_key}: {q_score}/{q_max}")

        # 推理深度分析
        print(f"\n  推理链检查:")
        q1 = questions.get("q1_price_prediction", {})
        q2 = questions.get("q2_hoarding_strategy", {})
        q3 = questions.get("q3_selling_strategy", {})
        q4 = questions.get("q4_profit_analysis", {})

        checks = [
            ("识别价格信号（Q1）", q1.get("score", 0) >= q1.get("max_score", 25) * 0.8),
            ("囤积策略（Q2）", q2.get("score", 0) >= q2.get("max_score", 25) * 0.8),
            ("高价卖出窗口（Q3）", q3.get("score", 0) >= q3.get("max_score", 30) * 0.8),
            ("利润分析（Q4）", q4.get("score", 0) >= q4.get("max_score", 20) * 0.8),
        ]
        for check_name, check_result in checks:
            print(f"    {'✅' if check_result else '❌'} {check_name}")

    # 长上下文类
    if long_context_results:
        r = long_context_results[0]
        vr = r.get("verification_report", {})
        questions = vr.get("questions", {})
        print(f"\n  【长上下文类 — 跨天信息串联能力】{'✅' if r['success'] else '❌'}")
        print(f"  综合得分: {r['percentage']}%")
        for q_key, qr in questions.items():
            q_score = qr.get("score", 0)
            q_max = qr.get("max_score", 1)
            print(f"    - {q_key}: {q_score}/{q_max}")

        # 能力层级分析
        print(f"\n  能力层级检查:")
        q1 = questions.get("q1_signal_detection", {})
        q2 = questions.get("q2_item_identification", {})
        q3 = questions.get("q3_location_deduction", {})
        q4 = questions.get("q4_action_plan", {})

        level_checks = [
            ("Lv1 信号识别（Q1）", q1.get("score", 0) >= q1.get("max_score", 15) * 0.6),
            ("Lv2 跨天串联（Q2）", q2.get("score", 0) >= q2.get("max_score", 35) * 0.6),
            ("Lv3 物品映射（Q2）", q2.get("score", 0) >= q2.get("max_score", 35) * 0.8),
            ("Lv4 位置推理（Q3）", q3.get("score", 0) >= q3.get("max_score", 20) * 0.6),
            ("Lv5 行动计划（Q4）", q4.get("score", 0) >= q4.get("max_score", 30) * 0.6),
        ]
        for check_name, check_result in level_checks:
            print(f"    {'✅' if check_result else '❌'} {check_name}")

    # ── 总结 ──
    print()
    print("─" * 80)
    print("  综合评估")
    print("─" * 80)

    if all_pass:
        print("  ✅ GA 通过了所有推理类与长上下文类测试")
        print("  GA 具备：经济因果推理能力、跨天信息记忆与串联能力")
    else:
        failed = [r for r in results if not r["success"]]
        print(f"  ❌ GA 在 {len(failed)} 个测试中未通过")
        for f in failed:
            print(f"    - {f['task_name']}: {f['percentage']}%")
        print()
        print("  建议改进方向:")
        if any(r["task_type"] == "reasoning" and not r["success"] for r in failed):
            print("    - 推理类：增强 GA 对世界新闻中因果链（停工→稀缺→涨价）的识别能力")
        if any(r["task_type"] == "long_context" and not r["success"] for r in failed):
            print("    - 长上下文类：增强 GA 的跨天记忆和噪声过滤能力")

    print()
    print("=" * 80)
    print("  报告生成完毕")
    print("=" * 80)

    # ── 保存 JSON 报告 ──
    report_data = {
        "title": "推理类 & 长上下文类 Benchmark 评测报告",
        "timestamp": datetime.now().isoformat(),
        "results": []
    }
    for r in results:
        report_data["results"].append({
            "task_key": r["task_key"],
            "task_name": r["task_name"],
            "task_type": r["task_type"],
            "success": r["success"],
            "percentage": r["percentage"],
            "turns": r["turns"],
            "verification": r.get("verification_report", {})
        })

    report_path = f"{BENCHMARK_BASE}/benchmark_report_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print(f"\n  JSON 报告: {report_path}")

    # 保存 Markdown 版本
    md_path = f"{BENCHMARK_BASE}/benchmark_report_{datetime.now():%Y%m%d_%H%M%S}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# 推理类 & 长上下文类 Benchmark 评测报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## 结果汇总\n\n")
        f.write(f"| 任务 | 类型 | 结果 | 得分 | 轮数 |\n")
        f.write(f"|---|---|---|---|---|\n")
        for r in results:
            status = "✅" if r["success"] else "❌"
            f.write(f"| {r['task_name']} | {r['task_type']} | {status} | {r['percentage']}% | {r['turns']} |\n")

        f.write(f"\n## 综合评估\n\n")
        if all_pass:
            f.write("✅ GA 通过了所有推理类与长上下文类测试\n\n")
            f.write("GA 具备以下能力：\n")
            f.write("- 经济因果推理能力（供需变化→价格波动→交易策略）\n")
            f.write("- 跨天信息记忆与串联能力（代号→外貌→封印→凹槽四重映射）\n")
            f.write("- 噪声识别与过滤能力\n")
        else:
            f.write("❌ GA 未完全通过测试\n\n")

    print(f"  MD 报告:  {md_path}")

    return report_path, md_path


def main():
    global TIMEOUT_PER_TASK
    import argparse
    parser = argparse.ArgumentParser(description="推理类 & 长上下文类 Benchmark")
    parser.add_argument("--type", type=str, choices=["reasoning", "long_context"],
                        help="仅运行指定类型的测试")
    parser.add_argument("--task", type=str, choices=list(TASKS.keys()),
                        help="运行指定的单个任务")
    parser.add_argument("--timeout", type=int, default=TIMEOUT_PER_TASK,
                        help="每题超时秒数")
    args = parser.parse_args()

    TIMEOUT_PER_TASK = args.timeout

    # 选择任务
    if args.task:
        selected = {args.task: TASKS[args.task]}
    elif args.type:
        selected = {k: v for k, v in TASKS.items() if v["type"] == args.type}
    else:
        selected = TASKS

    print("=" * 80)
    print("  推理类 & 长上下文类 Benchmark")
    print("=" * 80)
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  任务: {', '.join(selected.keys())}")
    print(f"  超时: {TIMEOUT_PER_TASK}s/题")
    print()

    # 依次运行
    results = []
    for task_key, task_cfg in selected.items():
        setup_work_env(task_key, task_cfg)
        result = run_single_benchmark(task_key, task_cfg)
        results.append(result)

    # 生成报告
    generate_report(results)


if __name__ == "__main__":
    main()
