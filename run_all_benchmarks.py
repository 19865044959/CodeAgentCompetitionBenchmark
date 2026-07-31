#!/usr/bin/env python3
"""
自进化 Benchmark 总控脚本
========================
1. 将所有 6 个工程拷贝到 /tmp，删除答案文件
2. 依次运行所有 benchmark
3. 汇总结果，生成评测报告
"""

import subprocess
import re
import json
import time
import os
import sys
import signal
import shutil
import hashlib
from datetime import datetime
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────
GA_DIR = "/mnt/d/work/Hackthon/GenericAgent"
GA_SCRIPT = "agentmain.py"
BENCHMARK_BASE = "/mnt/d/work/CodeAgentCompetitionBenchmark"
TEMP_BASE = "/mnt/d/work/temp"
TIMEOUT_PER_TASK = 300  # 每题 5 分钟
REPORT_DIR = "/mnt/d/work/CodeAgentCompetitionBenchmark"

# ── 6 个工程的定义 ────────────────────────────────────────
PROJECTS = {
    "A_HTTP": {
        "name": "A — 未知API",
        "src_dir": f"{BENCHMARK_BASE}/blackbox_api/self_evolution_a_http",
        "task_files": ["task_1_beijing.md", "task_2_nanjing.md", "task_3_chengdu.md"],
        "answer_files": ["answer_1.json", "answer_2.json", "answer_3.json"],
        "expected_dir": "ans",
        "expected_map": {0: "expected_1.json", 1: "expected_2.json", 2: "expected_3.json"},
        "extra_files": ["API_DOCS.md"],
        "needs_server": True,
        "server_cmd": None,  # filled at runtime
        "verify": "json_compare",
    },
    "E_CLI": {
        "name": "E — CLI工具",
        "src_dir": f"{BENCHMARK_BASE}/blackbox_api/self_evolution_e_cli",
        "task_files": ["task_e1.md", "task_e2.md", "task_e3.md"],
        "answer_files": ["answer_e1.json", "answer_e2.json", "answer_e3.json"],
        "expected_dir": "ans",
        "expected_map": {0: "answer_e1.json", 1: "answer_e2.json", 2: "answer_e3.json"},
        "extra_files": ["datatool.py"],
        "needs_server": False,
        "verify": "json_compare",
    },
    "B_DATA": {
        "name": "B — 数据处理",
        "src_dir": f"{BENCHMARK_BASE}/data_process/self_evolution_b_data",
        "task_files": ["task_b1.md", "task_b2.md", "task_b3.md"],
        "answer_files": ["answer_b1.json", "answer_b2.json", "answer_b3.json"],
        "expected_dir": "ans",
        "expected_map": {0: "expected_b1.json", 1: "expected_b2.json", 2: "expected_b3.json"},
        "extra_files": ["data.csv"],
        "needs_server": False,
        "verify": "json_fields",
    },
    "C_SQLITE": {
        "name": "C — 数据库查询",
        "src_dir": f"{BENCHMARK_BASE}/data_process/self_evolution_c_sqlite",
        "task_files": ["task_c1.md", "task_c2.md", "task_c3.md"],
        "answer_files": ["answer_c1.json", "answer_c2.json", "answer_c3.json"],
        "expected_dir": "ans",
        "expected_map": {0: "answer_c1.json", 1: "answer_c2.json", 2: "answer_c3.json"},
        "extra_files": ["traffic.db"],
        "needs_server": False,
        "verify": "deep_compare",
    },
    "D_STATION": {
        "name": "D — 照样板办事",
        "src_dir": f"{BENCHMARK_BASE}/imitation/station_note",
        "task_files": [],  # uses spec.md in cases/
        "answer_files": [],
        "expected_dir": "ans",
        "expected_map": {},
        "extra_files": [],
        "needs_server": False,
        "verify": "token_check",
        "setup_type": "cases",  # copy cases/ws_N to temp
    },
    "F_PROGRAM": {
        "name": "F — 程序修复",
        "src_dir": f"{BENCHMARK_BASE}/program_fix/program_alpha_beta_gamma",
        "task_files": ["task_1_alpha.md", "task_2_beta.md", "task_3_gamma.md"],
        "answer_files": [],
        "expected_dir": "ans",
        "expected_map": {0: "expected_1.json", 1: "expected_2.json", 2: "expected_3.json"},
        "extra_files": [],
        "needs_server": False,
        "verify": "token_check",
        "setup_type": "workspaces",  # copy cases/ws_N to /tmp/ws_N
    },
}


# ── 工具函数 ──────────────────────────────────────────────

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


def deep_compare(ans, exp):
    """递归比较 JSON"""
    if isinstance(exp, dict):
        if not isinstance(ans, dict):
            return False
        for k in exp:
            if k not in ans or not deep_compare(ans[k], exp[k]):
                return False
        return True
    elif isinstance(exp, list):
        if not isinstance(ans, list) or len(ans) != len(exp):
            return False
        return all(deep_compare(a, e) for a, e in zip(ans, exp))
    else:
        return ans == exp


def verify_json_fields(answer_file, expected_file):
    """比较 JSON 的关键字段"""
    try:
        ans = json.load(open(answer_file))
        exp = json.load(open(expected_file))
        for key in ["count", "total", "top_item"]:
            if ans.get(key) != exp.get(key):
                return False
        return True
    except Exception:
        return False


def verify_json_compare(answer_file, expected_file):
    """完整比较 JSON"""
    try:
        ans = json.load(open(answer_file))
        exp = json.load(open(expected_file))
        return deep_compare(ans, exp)
    except Exception:
        return False


def extract_token(output_text: str):
    """从输出中提取 TOKEN"""
    m = re.search(r"TOKEN:\s*([a-f0-9]+)", output_text)
    return m.group(1) if m else None


# ── 步骤1: 拷贝工程到 /tmp，删除答案 ──────────────────────

def copy_and_sanitize():
    """将所有工程拷贝到 /tmp/benchmark_*，删除 ans/ 目录"""
    print("=" * 70)
    print("  步骤1: 拷贝工程到 /tmp，清除答案文件")
    print("=" * 70)

    for key, proj in PROJECTS.items():
        dest = f"/tmp/benchmark_{key.lower()}"
        src = proj["src_dir"]

        if os.path.exists(dest):
            shutil.rmtree(dest)

        # 拷贝整个工程
        shutil.copytree(src, dest,
                        ignore=shutil.ignore_patterns('ans', '__pycache__', '.git', '*.pyc'))

        # 确保 ans 不存在（双重保险）
        ans_dir = f"{dest}/ans"
        if os.path.exists(ans_dir):
            shutil.rmtree(ans_dir)

        print(f"  ✓ {key}: {src} → {dest}")
        print(f"    (ans/ 已删除)")

    print()


# ── 步骤2: 设置工作环境并运行单个 benchmark ───────────────

def setup_work_env(proj_key, proj):
    """将任务文件、数据文件拷贝到 /mnt/d/work/temp/"""
    temp_dir = TEMP_BASE
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(f"{temp_dir}/ans", exist_ok=True)

    src = proj["src_dir"]

    # 拷贝任务文件
    for tf in proj["task_files"]:
        shutil.copy2(f"{src}/{tf}", f"{temp_dir}/{tf}")

    # 拷贝额外文件
    for ef in proj["extra_files"]:
        if os.path.isfile(f"{src}/{ef}"):
            shutil.copy2(f"{src}/{ef}", f"{temp_dir}/{ef}")

    # 拷贝答案文件到 ans/
    exp_dir = f"{src}/{proj['expected_dir']}"
    if os.path.isdir(exp_dir):
        for f in os.listdir(exp_dir):
            shutil.copy2(f"{exp_dir}/{f}", f"{temp_dir}/ans/{f}")

    # 特殊处理: cases/ 类型
    if proj.get("setup_type") == "cases":
        cases_src = f"{src}/cases"
        cases_dest = f"{temp_dir}/cases"
        if os.path.exists(cases_dest):
            shutil.rmtree(cases_dest)
        if os.path.exists(cases_src):
            shutil.copytree(cases_src, cases_dest)

    # 特殊处理: workspaces 类型 (program_alpha_beta_gamma)
    if proj.get("setup_type") == "workspaces":
        for i in range(1, 4):
            ws_src = f"{src}/cases/ws_{i}"
            ws_dest = f"/tmp/ws_{i}"
            if os.path.exists(ws_dest):
                shutil.rmtree(ws_dest)
            if os.path.exists(ws_src):
                shutil.copytree(ws_src, ws_dest)


def run_single_benchmark(proj_key, proj):
    """运行单个项目的 benchmark"""
    print(f"\n{'='*70}")
    print(f"  运行: {proj['name']} ({proj_key})")
    print(f"{'='*70}")

    temp_dir = TEMP_BASE
    results = []

    # ── 启动可选服务 ──
    server_proc = None
    if proj["needs_server"]:
        print(f"[{datetime.now():%H:%M:%S}] 启动 API 服务...")
        # 杀掉旧进程
        subprocess.run("fuser -k 8899/tcp 2>/dev/null", shell=True)
        time.sleep(0.5)

        # 使用 Python server 或编译好的 binary
        src = proj["src_dir"]
        server_bin = f"{src}/nchda_server"
        if os.path.exists(server_bin) and os.access(server_bin, os.X_OK):
            server_proc = subprocess.Popen(
                [server_bin],
                stdout=open("/tmp/nchda_server.log", "w"),
                stderr=subprocess.STDOUT,
            )
        else:
            server_proc = subprocess.Popen(
                [sys.executable, f"{src}/api_server.py"],
                stdout=open("/tmp/nchda_server.log", "w"),
                stderr=subprocess.STDOUT,
            )
        time.sleep(1.5)

        # 验证服务就绪
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:8899/api/v1/heritage/search?location=北京")
            req.add_header("Authorization", "Bearer heritage-api-key-2024")
            urllib.request.urlopen(req, timeout=5)
            print(f"[{datetime.now():%H:%M:%S}] API 服务就绪")
        except Exception as e:
            print(f"[{datetime.now():%H:%M:%S}] ⚠ API 服务可能未就绪: {e}")

    # ── 清理旧答案 ──
    for af in proj.get("answer_files", []):
        p = f"{temp_dir}/{af}"
        if os.path.exists(p):
            os.remove(p)
    # 清理通用答案
    for i in range(1, 4):
        for pat in ["answer_{i}.json", "answer_e{i}.json", "answer_b{i}.json",
                     "answer_c{i}.json"]:
            p = f"{temp_dir}/{pat.format(i=i)}"
            if os.path.exists(p):
                os.remove(p)

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

    import select
    all_output = []

    def read_until_prompt(timeout_sec, expected_answer_file=None):
        buf = ""
        deadline = time.time() + timeout_sec
        fd = proc.stdout.fileno()
        answer_seen = False
        while time.time() < deadline:
            r, _, _ = select.select([fd], [], [], 0.3)
            if r:
                chunk = os.read(fd, 4096).decode("utf-8", errors="replace")
                if not chunk:
                    break
                buf += chunk
                all_output.append(chunk)
                if buf.rstrip().endswith(">"):
                    time.sleep(0.3)
                    return buf
            else:
                if expected_answer_file and os.path.exists(expected_answer_file) and not answer_seen:
                    answer_seen = True
                    deadline = min(deadline, time.time() + 10)
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
            if init_buf.rstrip().endswith(">"):
                break

    # ── 依次执行 3 个任务 ──
    try:
        for i in range(3):
            task_idx = i + 1
            print(f"\n[{datetime.now():%H:%M:%S}] Task {task_idx}/3 ", end="", flush=True)

            # 确定任务文件路径
            if proj.get("setup_type") == "cases":
                task_file = f"{temp_dir}/cases/ws_{task_idx}/spec.md"
            elif proj["task_files"]:
                task_file = f"{temp_dir}/{proj['task_files'][i]}"
            else:
                print("ERROR: no task file")
                continue

            print(f"{os.path.basename(task_file)} ", end="", flush=True)

            # 发送任务
            proc.stdin.write(f"'{task_file}'\n")
            proc.stdin.flush()

            # 确定期望的答案文件
            answer_file = None
            if proj.get("setup_type") == "cases":
                # station_note: answer is TOKEN in output
                answer_file = None
            elif proj.get("setup_type") == "workspaces":
                # program fix: answer is TOKEN in output
                answer_file = None
            elif proj["answer_files"]:
                answer_file = f"{temp_dir}/{proj['answer_files'][i]}"

            # 等待完成
            output = read_until_prompt(TIMEOUT_PER_TASK, answer_file)
            turns = parse_output(output)

            # ── 验证 ──
            success = False
            verify_method = proj["verify"]

            if verify_method == "token_check":
                token = extract_token(output)
                if token and proj["expected_map"]:
                    exp_token = json.load(
                        open(f"{temp_dir}/ans/{proj['expected_map'][i]}")
                    )["token"]
                    success = (token == exp_token)
                elif token:
                    success = True
                status = f"✓ TOKEN={token}" if success else "✗"
            elif answer_file and os.path.exists(answer_file):
                exp_file = f"{temp_dir}/ans/{proj['expected_map'][i]}"
                if os.path.exists(exp_file):
                    if verify_method == "json_fields":
                        success = verify_json_fields(answer_file, exp_file)
                    else:
                        success = verify_json_compare(answer_file, exp_file)
                status = "✓" if success else "✗"
            else:
                token = extract_token(output)
                success = token is not None
                status = f"✓ TOKEN={token}" if success else "✗"

            print(f"{status}  turns={len(turns)}")

            results.append({
                "task": task_idx,
                "task_file": task_file,
                "success": success,
                "turns": len(turns),
                "turns_detail": turns,
            })

            # 打印回合详情
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

    # ── 停止服务 ──
    if server_proc:
        try:
            server_proc.terminate()
            server_proc.wait(timeout=3)
        except Exception:
            server_proc.kill()
        subprocess.run("fuser -k 8899/tcp 2>/dev/null", shell=True)
        print(f"[{datetime.now():%H:%M:%S}] API 服务已停止")

    # ── 输出项目摘要 ──
    print(f"\n  {proj['name']} — 结果摘要:")
    for r in results:
        s = "✅" if r["success"] else "❌"
        print(f"    Task {r['task']}: {s}  turns={r['turns']}")

    if all(r["success"] for r in results) and len(results) == 3:
        t1, t2, t3 = [r["turns"] for r in results]
        exps = [20, 1, 1]
        scores = []
        for idx, (r, exp) in enumerate(zip(results, exps)):
            actual = max(r["turns"], 1)
            score = round(exp / actual * 20, 1)
            scores.append(score)
        print(f"    自进化得分: {sum(scores):.1f}/60  (T1={t1}, T2={t2}, T3={t3})")

    return {
        "project_key": proj_key,
        "project_name": proj["name"],
        "results": results,
        "full_output": "".join(all_output),
    }


# ── 步骤3: 生成评测报告 ──────────────────────────────────

def generate_report(all_results):
    """生成综合评测报告"""
    print("\n\n")
    print("=" * 80)
    print("  自进化 Benchmark — 综合评测报告")
    print("=" * 80)
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    total_projects = len(all_results)
    all_pass = []
    partial_pass = []
    all_fail = []

    for pr in all_results:
        proj_name = pr["project_name"]
        results = pr["results"]
        n_pass = sum(1 for r in results if r["success"])
        n_total = len(results)

        if n_total == 0:
            continue

        if n_pass == n_total:
            all_pass.append(pr)
        elif n_pass > 0:
            partial_pass.append(pr)
        else:
            all_fail.append(pr)

    # ── 总体概览 ──
    print("─" * 80)
    print("  一、总体概览")
    print("─" * 80)
    print(f"  评测工程数: {total_projects}")
    print(f"  全部通过:   {len(all_pass)} 个")
    print(f"  部分通过:   {len(partial_pass)} 个")
    print(f"  全部失败:   {len(all_fail)} 个")
    print()

    # 汇总表
    print(f"  {'工程':<20s} {'题1':>6s} {'题2':>6s} {'题3':>6s} {'T1轮':>5s} {'T2轮':>5s} {'T3轮':>5s} {'自进化分':>8s}")
    print(f"  {'-'*20} {'-'*6} {'-'*6} {'-'*6} {'-'*5} {'-'*5} {'-'*5} {'-'*8}")

    for pr in all_results:
        name = pr["project_name"]
        results = pr["results"]
        statuses = []
        turns = []
        for r in results:
            statuses.append("✅" if r["success"] else "❌")
            turns.append(str(r["turns"]) if r["turns"] > 0 else "-")

        # 补齐
        while len(statuses) < 3:
            statuses.append("N/A")
        while len(turns) < 3:
            turns.append("-")

        # 计算自进化分
        if len(results) == 3 and all(r["success"] for r in results):
            exps = [20, 1, 1]
            scores = []
            for idx, (r, exp) in enumerate(zip(results, exps)):
                actual = max(r["turns"], 1)
                scores.append(round(exp / actual * 20, 1))
            evo_score = f"{sum(scores):.1f}/60"
        else:
            evo_score = "N/A"

        print(f"  {name:<20s} {statuses[0]:>6s} {statuses[1]:>6s} {statuses[2]:>6s} "
              f"{turns[0]:>5s} {turns[1]:>5s} {turns[2]:>5s} {evo_score:>8s}")

    print()

    # ── 自进化分析 ──
    print("─" * 80)
    print("  二、自进化能力分析")
    print("─" * 80)

    for pr in all_results:
        name = pr["project_name"]
        results = pr["results"]

        if len(results) < 3:
            print(f"\n  【{name}】数据不足，跳过")
            continue

        r1, r2, r3 = results[0], results[1], results[2]
        t1, t2, t3 = r1["turns"], r2["turns"], r3["turns"]

        print(f"\n  【{name}】")
        print(f"    题1 (探索): {t1} turns {'✅' if r1['success'] else '❌'}")
        print(f"    题2 (复用): {t2} turns {'✅' if r2['success'] else '❌'}")
        print(f"    题3 (复用): {t3} turns {'✅' if r3['success'] else '❌'}")

        if r1["success"] and r2["success"] and r3["success"]:
            if t2 < t1 and t3 < t1:
                reduction_2 = round((1 - t2/t1) * 100)
                reduction_3 = round((1 - t3/t1) * 100)
                print(f"    ✅ 体现自进化: 题2节省 {reduction_2}% turns, 题3节省 {reduction_3}% turns")
            elif t2 <= t1 and t3 <= t1:
                print(f"    ⚠ 部分自进化: turns 减少不明显")
            else:
                print(f"    ❌ 未体现自进化: 后续任务反而用了更多 turns")

            # 分析复用模式
            for t in r2["turns_detail"]:
                if "复用" in t.get("summary", "") or "模板" in t.get("summary", "") or "SOP" in t.get("summary", "").upper():
                    print(f"    📝 题2中观察到复用行为: Turn {t['num']}: {t['summary'][:80]}")
                    break
            else:
                if t2 <= 3:
                    print(f"    📝 题2仅用 {t2} turns，疑似直接复用脚本")

        elif r1["success"] and not (r2["success"] and r3["success"]):
            print(f"    ❌ 题1成功但后续失败 — 未能正确复用经验")
        elif not r1["success"]:
            print(f"    ❌ 题1未通过 — 无法评估自进化")
        print()

    # ── 各工程详细结果 ──
    print("─" * 80)
    print("  三、各工程详细结果")
    print("─" * 80)

    for pr in all_results:
        name = pr["project_name"]
        results = pr["results"]
        print(f"\n  【{name}】")
        for r in results:
            s = "✅ PASS" if r["success"] else "❌ FAIL"
            print(f"    Task {r['task']}: {s}  |  {r['turns']} turns")
            print(f"      文件: {os.path.basename(r['task_file'])}")
            if r["turns_detail"]:
                for t in r["turns_detail"]:
                    summary = t["summary"][:120] if t["summary"] else "(无summary)"
                    tools = " → ".join(t["tools"]) if t["tools"] else "(无工具)"
                    print(f"      Turn {t['num']:2d}: {summary}")
                    if t["tools"]:
                        print(f"             🛠️  {tools}")

    print("\n" + "=" * 80)
    print("  报告生成完毕")
    print("=" * 80)

    # ── 保存 JSON 报告 ──
    report_data = {
        "title": "Agent 自进化能力综合评测报告",
        "timestamp": datetime.now().isoformat(),
        "total_projects": total_projects,
        "summary": {
            "all_pass": len(all_pass),
            "partial_pass": len(partial_pass),
            "all_fail": len(all_fail),
        },
        "projects": [],
    }

    for pr in all_results:
        proj_data = {
            "key": pr["project_key"],
            "name": pr["project_name"],
            "results": [],
            "self_evolution_analysis": {},
        }

        results = pr["results"]
        if len(results) == 3:
            r1, r2, r3 = results
            t1, t2, t3 = r1["turns"], r2["turns"], r3["turns"]
            all_ok = r1["success"] and r2["success"] and r3["success"]
            proj_data["self_evolution_analysis"] = {
                "all_success": all_ok,
                "t1_turns": t1, "t2_turns": t2, "t3_turns": t3,
                "reduction_t2_vs_t1_pct": round((1 - t2/max(t1,1)) * 100) if all_ok else None,
                "reduction_t3_vs_t1_pct": round((1 - t3/max(t1,1)) * 100) if all_ok else None,
                "shows_evolution": all_ok and (t2 < t1 or t3 < t1),
            }

        for r in results:
            proj_data["results"].append({
                "task": r["task"],
                "task_file": os.path.basename(r["task_file"]),
                "success": r["success"],
                "turns": r["turns"],
                "turns_detail": r["turns_detail"],
            })

        report_data["projects"].append(proj_data)

    report_path = f"{REPORT_DIR}/self_evolution_benchmark_report_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    # 同时保存 Markdown 版本
    md_path = f"{REPORT_DIR}/self_evolution_benchmark_report_{datetime.now():%Y%m%d_%H%M%S}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Agent 自进化能力综合评测报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## 一、总体概览\n\n")
        f.write(f"| 指标 | 数量 |\n|---|---|\n")
        f.write(f"| 评测工程数 | {total_projects} |\n")
        f.write(f"| 全部通过 | {len(all_pass)} |\n")
        f.write(f"| 部分通过 | {len(partial_pass)} |\n")
        f.write(f"| 全部失败 | {len(all_fail)} |\n\n")

        f.write(f"## 二、详细结果\n\n")
        f.write(f"| 工程 | 题1 | 题2 | 题3 | T1轮 | T2轮 | T3轮 | 自进化分 |\n")
        f.write(f"|---|---|---|---|---|---|---|---|\n")
        for pr in all_results:
            name = pr["project_name"]
            results = pr["results"]
            s = ["-" for _ in range(3)]
            t = ["-" for _ in range(3)]
            for idx, r in enumerate(results):
                s[idx] = "✅" if r["success"] else "❌"
                t[idx] = str(r["turns"])
            evo = "N/A"
            if len(results) == 3 and all(r["success"] for r in results):
                exps = [20, 1, 1]
                scores = [round(exps[i]/max(results[i]["turns"],1)*20, 1) for i in range(3)]
                evo = f"{sum(scores):.1f}/60"
            f.write(f"| {name} | {s[0]} | {s[1]} | {s[2]} | {t[0]} | {t[1]} | {t[2]} | {evo} |\n")

        f.write(f"\n## 三、自进化分析\n\n")
        for pr in all_results:
            name = pr["project_name"]
            results = pr["results"]
            if len(results) < 3:
                continue
            r1, r2, r3 = results[0], results[1], results[2]
            f.write(f"### {name}\n\n")
            f.write(f"- 题1 (探索): {r1['turns']} turns {'✅' if r1['success'] else '❌'}\n")
            f.write(f"- 题2 (复用): {r2['turns']} turns {'✅' if r2['success'] else '❌'}\n")
            f.write(f"- 题3 (复用): {r3['turns']} turns {'✅' if r3['success'] else '❌'}\n")

            if r1["success"] and r2["success"] and r3["success"]:
                if r2["turns"] < r1["turns"]:
                    f.write(f"- **体现自进化**: 题2节省 {round((1-r2['turns']/r1['turns'])*100)}% turns\n")
                if r3["turns"] < r1["turns"]:
                    f.write(f"- **体现自进化**: 题3节省 {round((1-r3['turns']/r1['turns'])*100)}% turns\n")
            f.write("\n")

    print(f"\n  JSON 报告: {report_path}")
    print(f"  MD 报告:   {md_path}")
    return report_path, md_path


# ── 主流程 ──

def main():
    parser = __import__('argparse').ArgumentParser(description="自进化 Benchmark 总控")
    parser.add_argument("--skip-copy", action="store_true", help="跳过拷贝步骤")
    parser.add_argument("--projects", type=str, default="all",
                        help="指定项目 (逗号分隔, 如 A_HTTP,E_CLI)")
    parser.add_argument("--timeout", type=int, default=300, help="每题超时秒数")
    args = parser.parse_args()

    global TIMEOUT_PER_TASK
    TIMEOUT_PER_TASK = args.timeout

    # 选择项目
    if args.projects == "all":
        selected = list(PROJECTS.keys())
    else:
        selected = [p.strip() for p in args.projects.split(",")]

    print("=" * 80)
    print("  Agent 自进化 Benchmark 总控")
    print("=" * 80)
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  项目: {', '.join(selected)}")
    print(f"  超时: {TIMEOUT_PER_TASK}s/题")
    print()

    # 步骤1: 拷贝
    if not args.skip_copy:
        copy_and_sanitize()

    # 步骤2: 依次运行
    all_results = []
    for key in selected:
        proj = PROJECTS[key]
        setup_work_env(key, proj)
        result = run_single_benchmark(key, proj)
        all_results.append(result)

        # 保存中间结果
        mid_path = f"{TEMP_BASE}/benchmark_intermediate_{key}.json"
        with open(mid_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    # 步骤3: 生成报告
    report_path, md_path = generate_report(all_results)

    print(f"\n  全部完成！")
    print(f"  报告: {report_path}")
    print(f"        {md_path}")


if __name__ == "__main__":
    main()
