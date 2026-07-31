#!/usr/bin/env python3
"""
自进化 Benchmark 运行器 — 单项目版
用法: python3 run_one_benchmark.py <project_key>
  project_key: A_HTTP, E_CLI, B_DATA, C_SQLITE, D_STATION, F_PROGRAM
"""

import subprocess
import re
import json
import time
import os
import sys
import signal
import shutil
import select
from datetime import datetime
from pathlib import Path

GA_DIR = "/mnt/d/work/Hackthon/GenericAgent"
TEMP = "/mnt/d/work/temp"

# ── 项目配置 ──────────────────────────────────────────────
PROJECT_CONFIGS = {
    "A_HTTP": {
        "name": "A-HTTP",
        "src": "/tmp/benchmark_a_http",
        "orig_src": "/mnt/d/work/CodeAgentCompetitionBenchmark/blackbox_api/self_evolution_a_http",
        "task_files": ["task_1_beijing.md", "task_2_nanjing.md", "task_3_chengdu.md"],
        "answer_files": ["answer_1.json", "answer_2.json", "answer_3.json"],
        "expected_files": ["expected_1.json", "expected_2.json", "expected_3.json"],
        "extra": ["API_DOCS.md"],
        "verify": "json_full",
        "needs_server": True,
    },
    "E_CLI": {
        "name": "E-CLI",
        "src": "/tmp/benchmark_e_cli",
        "orig_src": "/mnt/d/work/CodeAgentCompetitionBenchmark/blackbox_api/self_evolution_e_cli",
        "task_files": ["task_e1.md", "task_e2.md", "task_e3.md"],
        "answer_files": ["answer_e1.json", "answer_e2.json", "answer_e3.json"],
        "expected_files": ["answer_e1.json", "answer_e2.json", "answer_e3.json"],
        "extra": ["datatool.py"],
        "verify": "json_full",
        "needs_server": False,
    },
    "B_DATA": {
        "name": "B-Data",
        "src": "/tmp/benchmark_b_data",
        "orig_src": "/mnt/d/work/CodeAgentCompetitionBenchmark/data_process/self_evolution_b_data",
        "task_files": ["task_b1.md", "task_b2.md", "task_b3.md"],
        "answer_files": ["answer_b1.json", "answer_b2.json", "answer_b3.json"],
        "expected_files": ["expected_b1.json", "expected_b2.json", "expected_b3.json"],
        "extra": ["data.csv"],
        "verify": "json_fields",
        "needs_server": False,
    },
    "C_SQLITE": {
        "name": "C-SQLite",
        "src": "/tmp/benchmark_c_sqlite",
        "orig_src": "/mnt/d/work/CodeAgentCompetitionBenchmark/data_process/self_evolution_c_sqlite",
        "task_files": ["task_c1.md", "task_c2.md", "task_c3.md"],
        "answer_files": ["answer_c1.json", "answer_c2.json", "answer_c3.json"],
        "expected_files": ["answer_c1.json", "answer_c2.json", "answer_c3.json"],
        "extra": ["traffic.db"],
        "verify": "json_full",
        "needs_server": False,
    },
    "D_STATION": {
        "name": "D-Station",
        "src": "/tmp/benchmark_d_station",
        "orig_src": "/mnt/d/work/CodeAgentCompetitionBenchmark/imitation/station_note",
        "task_files": [],  # uses spec.md in cases/
        "answer_files": [],
        "expected_files": ["expected_token_1.json", "expected_token_2.json", "expected_token_3.json"],
        "extra": [],
        "verify": "token",
        "needs_server": False,
    },
    "F_PROGRAM": {
        "name": "F-Program",
        "src": "/tmp/benchmark_f_program",
        "orig_src": "/mnt/d/work/CodeAgentCompetitionBenchmark/program_fix/program_alpha_beta_gamma",
        "task_files": ["task_1_alpha.md", "task_2_beta.md", "task_3_gamma.md"],
        "answer_files": [],
        "expected_files": ["expected_1.json", "expected_2.json", "expected_3.json"],
        "extra": [],
        "verify": "token_ws",
        "needs_server": False,
    },
}


def setup(proj):
    """设置工作环境 — 拷贝文件到 /mnt/d/work/temp/"""
    cfg = PROJECT_CONFIGS[proj]
    os.makedirs(f"{TEMP}/ans", exist_ok=True)

    # 拷贝任务文件
    for tf in cfg["task_files"]:
        src = f"{cfg['src']}/{tf}"
        if not os.path.exists(src):
            src = f"{cfg['orig_src']}/{tf}"
        if os.path.exists(src):
            shutil.copy2(src, f"{TEMP}/{tf}")

    # 拷贝答案文件到 ans/
    for ef in cfg["expected_files"]:
        # 先查 orig_src/ans (未被删除)
        src = f"{cfg['orig_src']}/ans/{ef}"
        if not os.path.exists(src):
            src = f"{cfg['src']}/ans/{ef}"
        if os.path.exists(src):
            shutil.copy2(src, f"{TEMP}/ans/{ef}")

    # 拷贝额外文件
    for ef in cfg["extra"]:
        src = f"{cfg['src']}/{ef}"
        if not os.path.exists(src):
            src = f"{cfg['orig_src']}/{ef}"
        if os.path.exists(src) and not os.path.exists(f"{TEMP}/{ef}"):
            if os.path.isdir(src):
                if not os.path.exists(f"{TEMP}/{ef}"):
                    shutil.copytree(src, f"{TEMP}/{ef}")
            else:
                shutil.copy2(src, f"{TEMP}/{ef}")

    # D_STATION: 拷贝 cases/
    if proj == "D_STATION":
        cases_dest = f"{TEMP}/cases"
        if os.path.exists(cases_dest):
            shutil.rmtree(cases_dest)
        for src_dir in [f"{cfg['src']}/cases", f"{cfg['orig_src']}/cases"]:
            if os.path.exists(src_dir):
                shutil.copytree(src_dir, cases_dest)
                break

    # F_PROGRAM: 拷贝 workspaces 到 /tmp/ws_N/
    if proj == "F_PROGRAM":
        for i in range(1, 4):
            ws_dest = f"/tmp/ws_{i}"
            if os.path.exists(ws_dest):
                shutil.rmtree(ws_dest)
            for src_dir in [f"{cfg['src']}/cases/ws_{i}", f"{cfg['orig_src']}/cases/ws_{i}"]:
                if os.path.exists(src_dir):
                    shutil.copytree(src_dir, ws_dest)
                    break

    # 清理旧答案
    for af in cfg["answer_files"]:
        p = f"{TEMP}/{af}"
        if os.path.exists(p):
            os.remove(p)

    print(f"  Setup complete for {cfg['name']}")


def parse_turns(text):
    turns = []; cur = None
    for line in text.split("\n"):
        m = re.match(r".*LLM Running \(Turn (\d+)\)", line)
        if m:
            if cur: turns.append(cur)
            cur = {"num": int(m.group(1)), "summary": "", "tools": []}
            continue
        if cur is None: continue
        sm = re.match(r"<summary>(.*?)</summary>", line.strip())
        if sm: cur["summary"] = sm.group(1).strip()
        tm = re.match(r"🛠️ (\w+)\(.*", line.strip())
        if tm: cur["tools"].append(tm.group(1))
    if cur: turns.append(cur)
    return turns


def verify_answer(proj, i, output_text):
    """验证第 i 个任务 (0-indexed) 的答案"""
    cfg = PROJECT_CONFIGS[proj]
    method = cfg["verify"]

    if method == "token":
        # 从输出中提取 TOKEN
        m = re.search(r"TOKEN:\s*([a-f0-9]+)", output_text)
        if not m: return False, None
        token = m.group(1)
        exp_file = f"{TEMP}/ans/{cfg['expected_files'][i]}"
        if os.path.exists(exp_file):
            exp = json.load(open(exp_file))
            return token == exp.get("token"), token
        return bool(token), token

    if method == "token_ws":
        # 从输出中提取 TOKEN
        m = re.search(r"TOKEN:\s*([a-f0-9]+)", output_text)
        if not m: return False, None
        token = m.group(1)
        exp_file = f"{TEMP}/ans/{cfg['expected_files'][i]}"
        if os.path.exists(exp_file):
            exp = json.load(open(exp_file))
            return token == exp.get("token"), token
        return bool(token), token

    if method == "json_full":
        ans_file = f"{TEMP}/{cfg['answer_files'][i]}"
        if not os.path.exists(ans_file):
            return False, None
        exp_file = f"{TEMP}/ans/{cfg['expected_files'][i]}"
        if not os.path.exists(exp_file):
            return os.path.exists(ans_file), None
        try:
            ans = json.load(open(ans_file))
            exp = json.load(open(exp_file))
            # 递归比较（字符串做 normalize：去空格 + CJK 前空格）
            import re as _re
            def _norm(s):
                if isinstance(s, str):
                    return _re.sub(r'\s+', '', s)  # 去掉所有空白字符后比较
                return s
            def deep_eq(a, e):
                if isinstance(e, dict):
                    return isinstance(a, dict) and all(k in a and deep_eq(a[k], e[k]) for k in e)
                if isinstance(e, list):
                    return isinstance(a, list) and len(a) == len(e) and all(deep_eq(ai, ei) for ai, ei in zip(a, e))
                if isinstance(e, str) and isinstance(a, str):
                    return _norm(a) == _norm(e)
                return a == e
            return deep_eq(ans, exp), None
        except:
            return False, None

    if method == "json_fields":
        ans_file = f"{TEMP}/{cfg['answer_files'][i]}"
        if not os.path.exists(ans_file):
            return False, None
        exp_file = f"{TEMP}/ans/{cfg['expected_files'][i]}"
        if not os.path.exists(exp_file):
            return False, None
        try:
            ans = json.load(open(ans_file))
            exp = json.load(open(exp_file))
            for k in ["count", "total", "top_item"]:
                if ans.get(k) != exp.get(k):
                    return False, None
            return True, None
        except:
            return False, None

    return False, None


def run_benchmark(proj):
    """运行单个项目的 benchmark"""
    cfg = PROJECT_CONFIGS[proj]
    print(f"\n{'='*70}")
    print(f"  {cfg['name']} Benchmark")
    print(f"{'='*70}")

    # ── 启动服务 (如果需要) ──
    server_proc = None
    if cfg["needs_server"]:
        print(f"[{datetime.now():%H:%M:%S}] Starting API server...")
        subprocess.run("fuser -k 8899/tcp 2>/dev/null", shell=True)
        time.sleep(0.3)

        # Try nchda_server binary first
        server_bin = f"{cfg['src']}/nchda_server"
        if not os.path.exists(server_bin):
            server_bin = f"{cfg['orig_src']}/nchda_server"
        if os.path.exists(server_bin) and os.access(server_bin, os.X_OK):
            server_proc = subprocess.Popen(
                [server_bin], stdout=open("/tmp/api_server.log", "w"), stderr=subprocess.STDOUT)
        else:
            server_py = f"{cfg['src']}/api_server.py"
            if not os.path.exists(server_py):
                server_py = f"{cfg['orig_src']}/api_server.py"
            server_proc = subprocess.Popen(
                [sys.executable, server_py], stdout=open("/tmp/api_server.log", "w"), stderr=subprocess.STDOUT)
        time.sleep(1.5)
        print(f"[{datetime.now():%H:%M:%S}] API server started (PID {server_proc.pid})")

    # ── 启动 GA ──
    print(f"[{datetime.now():%H:%M:%S}] Starting GenericAgent...")
    proc = subprocess.Popen(
        [sys.executable, "agentmain.py"], cwd=GA_DIR,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=0
    )
    fd = proc.stdout.fileno()
    all_output = []

    def read_until_prompt(timeout_sec, expected_answer_file=None):
        """Wait for GA to complete task.

        Strategy: primarily wait for answer file to appear, then wait a bit more
        for final output. Fall back to prompt detection if no answer file expected.
        """
        buf, deadline = "", time.time() + timeout_sec
        answer_seen = False
        min_work_time = time.time() + 15  # Don't check prompt before 15s of work

        while time.time() < deadline:
            r, _, _ = select.select([fd], [], [], 0.5)
            if r:
                chunk = os.read(fd, 4096).decode("utf-8", errors="replace")
                if not chunk: break
                buf += chunk; all_output.append(chunk)

                # Primary: answer file appeared
                if expected_answer_file and os.path.exists(expected_answer_file):
                    if not answer_seen:
                        answer_seen = True
                        deadline = min(deadline, time.time() + 20)  # 20s grace period

                # Secondary: prompt detection (only after min work time)
                if time.time() > min_work_time and buf.rstrip().endswith(">"):
                    if expected_answer_file and not answer_seen:
                        continue  # Ignore prompt if answer not yet created
                    time.sleep(0.5); return buf
            else:
                # select timeout: check answer file
                if expected_answer_file and os.path.exists(expected_answer_file) and not answer_seen:
                    answer_seen = True
                    deadline = min(deadline, time.time() + 20)

        return buf

    # Wait for GA ready
    print(f"[{datetime.now():%H:%M:%S}] Waiting for GA to be ready...")
    while True:
        r, _, _ = select.select([fd], [], [], 1.0)
        if r:
            c = os.read(fd, 4096).decode("utf-8", errors="replace")
            if not c: break
            all_output.append(c)
            if c.rstrip().endswith(">"): break
    print(f"[{datetime.now():%H:%M:%S}] GA ready")

    # ── 依次执行 3 个任务 ──
    results = []
    try:
        for i in range(3):
            # 确定任务文件
            if proj == "D_STATION":
                task_path = f"{TEMP}/cases/ws_{i+1}/spec.md"
            elif cfg["task_files"]:
                task_path = f"{TEMP}/{cfg['task_files'][i]}"
            else:
                task_path = f"{cfg['src']}/task_{i+1}_*.md"

            # 确定期望的答案文件
            ans_file = None
            if cfg["answer_files"]:
                ans_file = f"{TEMP}/{cfg['answer_files'][i]}"

            print(f"\n[{datetime.now():%H:%M:%S}] Task {i+1}/3: {os.path.basename(task_path)}", end="", flush=True)
            proc.stdin.write(f"'{task_path}'\n"); proc.stdin.flush()
            output = read_until_prompt(300, expected_answer_file=ans_file)
            turns = parse_turns(output)
            ok, detail = verify_answer(proj, i, output)

            status = "✓" if ok else "✗"
            extra = f" ({detail})" if detail else ""
            print(f" {status}{extra} turns={len(turns)}")

            results.append({
                "task": i+1, "task_file": task_path, "success": ok,
                "turns": len(turns), "turns_detail": turns
            })

            for t in turns:
                s = t["summary"][:100] if t["summary"] else ""
                print(f"    Turn {t['num']:2d}: {s}")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback; traceback.print_exc()
    finally:
        try: proc.send_signal(signal.SIGINT); proc.wait(timeout=5)
        except: proc.kill()

    if server_proc:
        try: server_proc.terminate(); server_proc.wait(timeout=3)
        except: server_proc.kill()
        subprocess.run("fuser -k 8899/tcp 2>/dev/null", shell=True)

    # ── 报告 ──
    print(f"\n{'='*70}")
    print(f"  {cfg['name']} Results")
    print(f"{'='*70}")
    for r in results:
        s = "✅" if r["success"] else "❌"
        print(f"  Task {r['task']}: {s}  turns={r['turns']}")

    if len(results) == 3:
        exps = [20, 1, 1]; scores = []
        for idx, (r, exp) in enumerate(zip(results, exps)):
            actual = max(r["turns"], 1)
            scores.append(round(exp / actual * 20, 1))
        print(f"  Self-evolution score: {sum(scores):.1f}/60")

    # 保存报告
    report = {
        "project": proj, "name": cfg["name"],
        "timestamp": datetime.now().isoformat(),
        "results": results, "full_output": "".join(all_output)
    }
    report_path = f"{TEMP}/benchmark_{proj.lower()}_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  Report: {report_path}")

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 run_one_benchmark.py <PROJECT_KEY>")
        print(f"  PROJECT_KEY: {', '.join(PROJECT_CONFIGS.keys())}")
        sys.exit(1)

    proj = sys.argv[1].upper()
    if proj not in PROJECT_CONFIGS:
        print(f"Unknown project: {proj}")
        sys.exit(1)

    setup(proj)
    run_benchmark(proj)
