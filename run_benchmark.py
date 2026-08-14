#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_benchmark.py — 自进化类任务统一评测脚本 (v3)

对旧版脚本 (run_all_benchmarks.py / run_one_benchmark.py / 自进化类任务/run_qwen36_35b_benchmark.py)
三类问题的修复:

  1. 回合泄漏 —— 旧版靠检测输出最后一行是否为 '>' 判定任务结束, 上一任务未读完的
     尾回合会混入下一任务的输出缓冲, 导致回合数虚高 (git 证据: 0019554 中未知API
     T3 报 9 轮, turns_detail 第 1 个是 "Turn 5 数据已验证，南京结果正确" 的泄漏段,
     实际只有 Turns 1-8 共 8 轮)。
     → 完成判定改为「答案证据 + 静默期」: 答案文件已生成 (或 TOKEN 已输出) 且 GA
       连续 QUIET_SECS 无新输出才结束; 回合解析按 Turn 1 起的连续递增序列过滤,
       丢弃前置泄漏段。
  2. 静默放行 —— 旧版 (run_one_benchmark.py:206-208) 在期望答案文件不存在时直接
     return os.path.exists(ans_file), 使错误答案 (如国贸桥、6区县) 被记为 ✅。
     → 期望文件缺失一律判失败 (fail-loud), 所有验证路径不再有任何 fallback 放行。
  3. 环境分叉 —— 旧版把任务文件拷到 /mnt/d/work/temp 再启动 GA, 与手动测试
     (在项目目录内用相对路径) 环境不同。
     → GA 的 cwd 直接是 /tmp/自进化类任务 下的项目目录, 与手动测试完全一致。

用法:
  python3 run_benchmark.py [--model-name Qwen3.6-35B-A3B] [--model-id qwen3.6-35b-a3b]
                           [--projects unknown_api,db_query]
                           [--timeout 300] [--quiet-secs 10] [--skip-cleanup]
  python3 run_benchmark.py --selftest   # 回归测试: 回合解析 + 验证器 (不启动 GA)

报告输出 (与评测集文件分开):
  自进化类任务/res/<model-id>/<YYYY-MM-DD-HHMM>/
    6 个 <工程>评测报告.json + self_evolution_benchmark_report.md

安全约定 (不可违反):
  - 期望答案只从仓库 ans/ 目录读取, 仅验证时使用, 绝不拷贝到 /tmp/自进化类任务
  - 每轮测试开始前执行 /tmp/自进化类任务/cleanup.sh 统一清理
"""

import argparse
import json
import os
import re
import select
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime

# ── 基础配置 ──────────────────────────────────────────────
GA_DIR = "/mnt/d/work/Hackthon/GenericAgent"
GA_SCRIPT = "agentmain.py"
LIB_DIR = "/tmp/自进化类任务"                                    # 测试库 (GA 只能看到这里)
REPO_TASKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "自进化类任务")
# 结果目录: res/<model-id>/<YYYY-MM-DD-HHMM>/ 下放 6 个 <工程>评测报告.json + 1 个汇总 md,
# 与评测集文件严格分开, 互不污染
RES_DIR = os.path.join(REPO_TASKS, "res")

# ── 6 个工程定义 ──────────────────────────────────────────
# lib_dir   = LIB_DIR/<category>/<subdir>            (GA 的 cwd, 任务现场)
# ans_dir   = REPO_TASKS/<category>/<subdir>/ans     (仅验证时读取, 绝不暴露给 GA)
PROJECTS = [
    {
        "key": "unknown_api", "name": "未知API",
        "category": "1固定步骤类", "subdir": "1未知API",
        "tasks": ["task_1_beijing.md", "task_2_nanjing.md", "task_3_chengdu.md"],
        "answers": ["answer_1.json", "answer_2.json", "answer_3.json"],
        "expected": ["expected_1.json", "expected_2.json", "expected_3.json"],
        "verify": "json_compare", "needs_server": True,
    },
    {
        "key": "engineering_fix", "name": "工程修复",
        "category": "1固定步骤类", "subdir": "2工程修复",
        "tasks": ["task_1_alpha.md", "task_2_beta.md", "task_3_gamma.md"],
        "answers": [],                                       # 靠 ./check 输出 TOKEN
        "expected": ["expected_1.json", "expected_2.json", "expected_3.json"],
        "verify": "token_check", "needs_server": False,
    },
    {
        "key": "cli_tool", "name": "CLI工具",
        "category": "1固定步骤类", "subdir": "3CLI工具",
        "tasks": ["task_e1.md", "task_e2.md", "task_e3.md"],
        "answers": ["answer_e1.json", "answer_e2.json", "answer_e3.json"],
        "expected": ["answer_e1.json", "answer_e2.json", "answer_e3.json"],
        "verify": "json_compare", "needs_server": False,
    },
    {
        "key": "follow_template", "name": "照样板办事",
        "category": "2模仿类", "subdir": "照样板办事",
        "tasks": ["task_1.md", "task_2.md", "task_3.md"],
        "answers": [],                                       # 靠 ./check1..3 输出 TOKEN
        "expected": ["expected_token_1.json", "expected_token_2.json", "expected_token_3.json"],
        "verify": "token_check", "needs_server": False,
    },
    {
        "key": "db_query", "name": "数据库查询",
        "category": "3数据处理类", "subdir": "1数据库查询",
        "tasks": ["task_c1.md", "task_c2.md", "task_c3.md"],
        "answers": ["answer_c1.json", "answer_c2.json", "answer_c3.json"],
        "expected": ["answer_c1.json", "answer_c2.json", "answer_c3.json"],
        "verify": "json_compare", "needs_server": False,
    },
    {
        "key": "camp_supply", "name": "营地物资统计",
        "category": "3数据处理类", "subdir": "2营地物资统计",
        "tasks": ["task_b1.md", "task_b2.md", "task_b3.md"],
        "answers": ["answer_b1.json", "answer_b2.json", "answer_b3.json"],
        "expected": ["expected_b1.json", "expected_b2.json", "expected_b3.json"],
        "verify": "json_fields", "needs_server": False,
    },
]

# ── 输出解析 ──────────────────────────────────────────────
# GA 的回合标记在 agent_loop.py 中始终会打印, 但 --verbose 才包 ** :
#   REPL 无 task_dir: "LLM Running (Turn N) ..."  (verbose 时 "**LLM Running (Turn N) ...**")
#   task_dir 模式:    "Turn N ..."                (verbose 时 "**Turn N ...**")
# 2026-08-13 教训: 旧版正则要求 ** 前缀, 未加 --verbose 时全部回合被漏掉 (turns=0)
TURN_RE = re.compile(r"^\**LLM Running \(Turn (\d+)\)")
TURN_RE2 = re.compile(r"^\**Turn (\d+) \.\.\.\**$")
SUMMARY_RE = re.compile(r"<summary>(.*?)</summary>")
TOKEN_RE = re.compile(r"TOKEN[:：]\s*([a-zA-Z0-9]+)")


def _tool_from_line(line):
    """从工具输出行提取工具名, 兼容两种格式: '🛠️ code_run(...)' / '🛠️ Tool: `code_run`'"""
    m = re.search(r"🛠️ Tool: `(\w+)`", line)
    if m:
        return m.group(1)
    m = re.search(r"🛠️ (\w+)\(", line)
    if m:
        return m.group(1)
    return None


def _tool_positions(buf):
    """返回 [(start, end, tool_name), ...], 按位置排序"""
    out = []
    for m in re.finditer(r"🛠️ (?:Tool: `\w+`|\w+\()", buf):
        out.append((m.start(), m.end(), _tool_from_line(m.group(0))))
    return out


def token_evidence(buf):
    """TOKEN 证据: TOKEN 必须出现在某次执行类工具 (非 file_read) 的输出之后,
    且该次执行之后没有出现过 file_read (避免把"读 check 脚本内容"误判为执行结果)。"""
    m = TOKEN_RE.search(buf)
    if not m:
        return False
    last_exec_end = None
    for start, end, tool in _tool_positions(buf):
        if tool != "file_read":
            last_exec_end = end
    if last_exec_end is None or m.start() <= last_exec_end:
        return False
    # 执行之后如果又读了文件, TOKEN 可能来自文件内容而非执行输出
    for start, end, tool in _tool_positions(buf):
        if start > last_exec_end and tool == "file_read":
            return False
    return True


def extract_token(text):
    m = TOKEN_RE.search(text)
    return m.group(1) if m else None


def analyze_turn(num, text):
    """单回合摘要: summary / tools / phase"""
    summary = ""
    sm = SUMMARY_RE.search(text)
    if sm:
        summary = sm.group(1).strip()
    if not summary:
        for line in text.split("\n"):
            line = line.strip()
            # [Xxx] 行是 GA 自己的 stdout 打印 (见 _GA_NOISE_PREFIX), 不是模型内容
            if line and not line.startswith(("🛠️", "<", "```", "LLM Running", "**Turn", "**LLM")
                               + _GA_NOISE_PREFIX):
                summary = line[:200]
                break
    tools = []
    for line in text.split("\n"):
        t = _tool_from_line(line)
        if t and t not in tools:
            tools.append(t)

    s_low = summary.lower()
    phase = "探索"
    if TOKEN_RE.search(text):
        phase = "通过"
    elif any(kw in s_low for kw in ["complete", "done", "完成", "通过"]):
        phase = "通过"
    elif any(kw in text for kw in ["复用", "reuse", "沿用", "直接改", "可复用的脚本", "same procedure"]):
        phase = "复用"
    elif any(kw in text for kw in ["验证", "校验", "verify", "MD5", "md5"]):
        phase = "验证"
    elif any(kw in text for kw in ["读题", "读取任务", "了解任务", "阅读题目", "read the task"]):
        phase = "读题"
    elif any(kw in text for kw in ["调试", "修正", "重试", "修复", "fix", "编码"]):
        phase = "调试"
    return {"num": num, "summary": summary, "tools": tools, "phase": phase}


def parse_turns(text):
    """解析 GA 输出中的回合序列。

    修复回合泄漏: GA 每个任务回合都从 Turn 1 重新计数, 上一任务泄漏进来的尾回合
    (Turn N, N>=2) 会排在 buffer 最前面。因此: 找到第一个 num==1 的段, 从它开始
    只保留连续递增 (1,2,3...) 的段, 其余丢弃。
    """
    segments = []  # {"num": int, "text": str}
    cur = None
    for line in text.split("\n"):
        line = line.strip()
        m = TURN_RE.match(line) or TURN_RE2.match(line)
        if m:
            if cur is not None:
                segments.append(cur)
            cur = {"num": int(m.group(1)), "text": ""}
        elif cur is not None:
            cur["text"] += line + "\n"
    if cur is not None:
        segments.append(cur)

    start = next((i for i, s in enumerate(segments) if s["num"] == 1), None)
    if start is None:
        return []
    turns, expect = [], 1
    for s in segments[start:]:
        if s["num"] != expect:
            break                       # 丢弃乱序/泄漏段, 不凑数
        turns.append(analyze_turn(s["num"], s["text"]))
        expect += 1
    return turns


# GA 自身打印到 stdout 的行前缀 (llmcore/ga/agentmain 的全部 [Xxx] 行):
#   [Debug] 上下文裁剪调试 (llmcore.py trim_messages_history)
#   [Cut] 历史裁剪报告 (llmcore.py:68)
#   [MixinSession] 会话选择 (llmcore.py:965)
#   [Reflect]/[INFO]/[WARN]/[ERROR] 插件钩子 (llmcore.py 251-279)
#   [Action] 工具执行回显 (ga.py:22)
#   [FILE] 文件读取回显 (ga.py)
#   [Cache]/[Output] usage 统计 (llmcore.py:306-312 _record_usage)
# 它们不是模型输出, 不能进入回合文本/摘要 (2026-08-13 17:22 轮实际出现 MixinSession/Cut 噪音;
# 20:41 轮无 --verbose 时 [Cache] 先于模型正文打到 stdout, 被兜底摘要误取)。
_GA_NOISE_PREFIX = ("[Debug]", "[Cut]", "[MixinSession]", "[Reflect]", "[ERROR]", "[WARN]",
                    "[Info]", "[Action]", "[FILE]", "[Cache]", "[Output]")
_GA_NOISE_RE = re.compile(
    r"^\[(?:Debug|Cut|MixinSession|Reflect|ERROR|WARN|Info|Action|FILE|Cache|Output)\][^\n]*\n?",
    re.M)


def clean_ga_debug(text):
    """去掉 GA 自身的 stdout 打印行, 保留模型输出。"""
    return _GA_NOISE_RE.sub("", text)


def drop_feed_turn(turns):
    """扣除每个任务的喂入应答回合。

    GA 的 agent_runner_loop 首轮 LLM 调用直接应答原始任务路径
    (agent_loop.py:44-46, prompt 无 WORKING MEMORY/Current turn),
    GA 自己的每任务计数器 (工作记忆 "Current turn: N") 不含这一轮。
    2026-08-13 实测 18 个任务全部: stdout 标记数 = GA 计数 + 1。
    """
    if turns and turns[0]["num"] == 1:
        turns = turns[1:]
        for n, t in enumerate(turns, 1):
            t["num"] = n
    return turns


# ── 验证 (fail-loud, 无任何静默放行) ──────────────────────

def deep_compare(ans, exp):
    """递归比较 JSON, 字符串做空白归一化。返回 (ok, 首个不匹配路径)。"""
    def cmp(a, e, path):
        if isinstance(e, dict):
            if not isinstance(a, dict):
                return False, (path or "<root>") + f" 期望 object 实际 {type(a).__name__}"
            for k in e:
                if k not in a:
                    return False, f"{path}.{k} 缺失"
                ok, p = cmp(a[k], e[k], f"{path}.{k}" if path else k)
                if not ok:
                    return ok, p
            return True, ""
        if isinstance(e, list):
            if not isinstance(a, list) or len(a) != len(e):
                return False, (path or "<root>") + \
                    f" 列表长度 {len(a) if isinstance(a, list) else type(a).__name__} != {len(e)}"
            for idx, (x, y) in enumerate(zip(a, e)):
                ok, p = cmp(x, y, f"{path}[{idx}]" if path else f"[{idx}]")
                if not ok:
                    return ok, p
            return True, ""
        if isinstance(e, str) and isinstance(a, str):
            if re.sub(r"\s+", "", a) == re.sub(r"\s+", "", e):
                return True, ""
            return False, f"{path or '<root>'}: 期望 '{e}' 实际 '{a}'"
        if a == e:
            return True, ""
        return False, f"{path or '<root>'}: 期望 {e!r} 实际 {a!r}"
    return cmp(ans, exp, "")


def verify_task(proj, i, task_buf, lib_dir):
    """验证第 i 个任务 (0-indexed)。返回 (success, error)。

    fail-loud: 期望答案文件缺失时直接判失败, 不再像旧版那样 fallback 放行。
    """
    exp_file = os.path.join(REPO_TASKS, proj["category"], proj["subdir"],
                            "ans", proj["expected"][i])
    if not os.path.exists(exp_file):
        return False, f"期望答案文件缺失 (fail-loud): {exp_file}"

    try:
        with open(exp_file, encoding="utf-8") as f:
            exp = json.load(f)
    except Exception as e:
        return False, f"期望答案损坏: {exp_file}: {e}"

    method = proj["verify"]

    if method == "token_check":
        token = extract_token(task_buf)
        if token is None:
            return False, "GA 输出中未发现 TOKEN"
        if token != exp.get("token"):
            return False, f"TOKEN 不匹配: 实际 {token} != 期望 {exp.get('token')}"
        return True, ""

    answer_file = os.path.join(lib_dir, proj["answers"][i])
    if not os.path.exists(answer_file):
        return False, f"未生成答案文件: {proj['answers'][i]}"
    try:
        with open(answer_file, encoding="utf-8") as f:
            ans = json.load(f)
    except Exception as e:
        return False, f"答案 JSON 无法解析: {proj['answers'][i]}: {e}"

    if method == "json_fields":
        for key in ["count", "total", "top_item"]:
            if ans.get(key) != exp.get(key):
                return False, f"{key}: 实际 {ans.get(key)!r} != 期望 {exp.get(key)!r}"
        return True, ""

    # json_compare
    ok, err = deep_compare(ans, exp)
    if not ok:
        return False, err
    return True, ""


# ── GA 交互 ───────────────────────────────────────────────

def wait_server_ready(timeout=30):
    """等待未知API服务就绪 (带正确 Authorization 的探测请求)。

    注意: 查询参数里的中文必须显式 quote, 否则 urllib 在编码请求行时抛
    UnicodeEncodeError (ASCII codec), 请求根本发不出去 —— 2026-08-13 实际踩坑。
    """
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            url = ("http://localhost:8899/api/v1/heritage/search?location="
                   + urllib.parse.quote("北京"))
            req = urllib.request.Request(url)
            req.add_header("Authorization", "Bearer heritage-api-key-2024")
            urllib.request.urlopen(req, timeout=3)
            return True
        except Exception as e:
            last_err = e
            time.sleep(1)
    if last_err is not None:
        print(f"    [server] 探测失败原因: {type(last_err).__name__}: {last_err}")
    return False


def run_project(proj, args):
    """在一个项目目录内启动 GA (cwd=项目目录, 与手动测试一致), 依次执行 3 个任务。"""
    lib_dir = os.path.join(LIB_DIR, proj["category"], proj["subdir"])
    print(f"\n{'=' * 62}")
    print(f"  [{proj['category']}/{proj['subdir']}] {proj['name']} ({proj['key']})")
    print(f"{'=' * 62}")

    # ── 启动 API 服务 (仅 unknown_api) ──
    server_proc = None
    if proj["needs_server"]:
        subprocess.run("fuser -k 8899/tcp 2>/dev/null", shell=True)
        time.sleep(0.5)
        server_bin = os.path.join(lib_dir, "nchda_server")
        logf = open("/tmp/nchda_server.log", "w")
        if os.path.exists(server_bin) and os.access(server_bin, os.X_OK):
            server_proc = subprocess.Popen([server_bin], cwd=lib_dir,
                                           stdout=logf, stderr=subprocess.STDOUT)
        else:
            server_proc = subprocess.Popen(
                [sys.executable, os.path.join(lib_dir, "api_server.py")],
                cwd=lib_dir, stdout=logf, stderr=subprocess.STDOUT)
        ok = wait_server_ready()
        print(f"  [server] {'就绪' if ok else '⚠ 未就绪(30s)'}")

    # ── 启动 GA (cwd = 项目目录, 环境与手动测试一致) ──
    print(f"  [GA] 启动 (cwd={lib_dir}) ...", flush=True)
    proc = subprocess.Popen(
        [sys.executable, os.path.join(args.ga_dir, args.ga_script)],
        cwd=lib_dir,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        bufsize=0,
    )
    fd = proc.stdout.fileno()
    chunks = []  # [(time, text)]

    def reader():
        while True:
            try:
                c = os.read(fd, 4096)
            except OSError:
                break
            if not c:
                break
            chunks.append((time.time(), c.decode("utf-8", errors="replace")))

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    def buf_since(idx):
        return "".join(c for _, c in chunks[idx:])

    # 等待 GA 就绪: 输出末尾出现 '>' 提示符
    ready = False
    for _ in range(60):
        if buf_since(0).rstrip().endswith(">"):
            ready = True
            break
        time.sleep(1)
    if not ready:
        print("  [GA] ⚠ 60s 内未见提示符, 继续尝试执行 (可能无 banner)")
    else:
        print("  [GA] 就绪")

    results = []
    try:
        for i in range(3):
            task_file = proj["tasks"][i]
            task_path = os.path.join(lib_dir, task_file)
            ans_path = os.path.join(lib_dir, proj["answers"][i]) if proj["answers"] else None
            t_start = time.time()
            start_idx = len(chunks)

            proc.stdin.write((task_path + "\n").encode("utf-8"))
            proc.stdin.flush()
            print(f"\n  [{datetime.now():%H:%M:%S}] Task {i + 1}/3: {task_file}", end="", flush=True)

            deadline = t_start + args.timeout
            last_chunk_t = t_start
            evidence_seen = False
            task_buf = ""
            while True:
                time.sleep(0.5)
                task_buf = clean_ga_debug(buf_since(start_idx))
                last_chunk_t = chunks[-1][0] if len(chunks) > start_idx else last_chunk_t

                if ans_path is not None:
                    evidence_seen = (os.path.exists(ans_path)
                                     and os.path.getmtime(ans_path) >= t_start)
                else:
                    evidence_seen = token_evidence(task_buf)

                if evidence_seen:
                    # 证据出现后, 静默期从证据时刻起算, 并保证至少有静默期+余量时间
                    deadline = max(deadline, last_chunk_t + args.quiet_secs + 30)
                    if time.time() - last_chunk_t >= args.quiet_secs:
                        break
                if time.time() >= deadline:
                    break

            time.sleep(2.0)  # 残余排空: 收下最后可能的输出
            task_buf = clean_ga_debug(buf_since(start_idx))
            turns = drop_feed_turn(parse_turns(task_buf))

            success, err = verify_task(proj, i, task_buf, lib_dir)
            reason = "超时" if time.time() - t_start >= args.timeout else ("证据+静默" if evidence_seen else "静默")
            status = "✓" if success else "✗"
            print(f" → {status} {len(turns)}轮 ({reason})")
            if err:
                print(f"      验证: {err}")
            for turn in turns:
                s = turn["summary"][:80] if turn["summary"] else ""
                print(f"    Turn {turn['num']:2d} [{turn['phase']}]: {s}")

            results.append({
                "task": i + 1,
                "task_file": task_file,
                "name": "",
                "success": success,
                "turns": len(turns),
                "turns_detail": turns,
            })
            if err:
                results[-1]["error"] = err

    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"\n  [ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    if server_proc is not None:
        try:
            server_proc.terminate()
            server_proc.wait(timeout=3)
        except Exception:
            server_proc.kill()
        subprocess.run("fuser -k 8899/tcp 2>/dev/null", shell=True)

    # 补任务名 (从任务文件标题提取)
    for r, tf in zip(results, proj["tasks"]):
        try:
            with open(os.path.join(lib_dir, tf), encoding="utf-8") as f:
                title = f.readline().strip().lstrip("#").strip()
                title = re.sub(r"^自进化任务\s*[A-Za-z]*-?\d+\s*[:：]\s*", "", title)
                r["name"] = title
        except Exception:
            pass
    return results


# ── 报告生成 ──────────────────────────────────────────────

def self_evolution_analysis(results):
    """与历史报告格式一致的自进化分析。"""
    if len(results) != 3:
        return None
    r1, r2, r3 = results
    t1, t2, t3 = r1["turns"], r2["turns"], r3["turns"]
    all_ok = all(r["success"] for r in results)

    red_t2 = round((1 - t2 / max(t1, 1)) * 100) if all_ok else None
    red_t3 = round((1 - t3 / max(t1, 1)) * 100) if all_ok else None

    analysis = {
        "all_success": all_ok,
        "t1_turns": t1, "t2_turns": t2, "t3_turns": t3,
        "reduction_t2_vs_t1_pct": red_t2,
        "reduction_t3_vs_t1_pct": red_t3,
        "shows_evolution": all_ok and (t2 < t1 or t3 < t1),
        "scores": {},
    }
    for idx, (r, exp) in enumerate(zip(results, [20, 1, 1])):
        actual = max(r["turns"], 1)
        # 封顶 20 分/题: 比基线快时不得突破总分 60 的名义上限 (2026-08-13 曾出现 80.1/60)
        score = round(min(exp / actual * 20, 20.0), 1)
        analysis["scores"][f"task{idx + 1}"] = {"exp": exp, "actual": actual, "score": score}
    analysis["total"] = f"{sum(analysis['scores'][k]['score'] for k in analysis['scores']):.1f}/60"
    return analysis


def write_reports(proj, results, args, analysis, run_dir):
    """项目 JSON 报告, 写入本次评测的日期目录 res/<model-id>/<日期>/。"""
    report = {
        "project": proj["key"],
        "name": proj["name"],
        "model": args.model_name,
        "model_id": args.model_id,
        "timestamp": datetime.now().isoformat(),
        "note": f"评测模式: REPL (GA cwd={LIB_DIR}/{proj['category']}/{proj['subdir']})",
        "results": results,
    }
    if analysis:
        report["self_evolution_analysis"] = analysis

    json_path = os.path.join(run_dir, f"{proj['name']}评测报告.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  [报告] {json_path}")
    return report


def write_summary_md(all_reports, args, run_dir):
    lines = [
        f"# 自进化 Benchmark 评测报告 — {args.model_name}",
        "",
        f"- **模型**: {args.model_name} (`{args.model_id}`)",
        f"- **评测模式**: Linux REPL, GA cwd = 测试库项目目录 (与手动测试一致)",
        f"- **测试库**: `{LIB_DIR}` (每轮开始自动执行 cleanup.sh 清理)",
        f"- **结果目录**: `{run_dir}`",
        f"- **时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 总览",
        "",
        "| 分类 | 工程 | 题1 | 题2 | 题3 | 回合缩减 | 自进化判定 |",
        "|---|---|---|---|---|---|---|",
    ]
    for report in all_reports:
        results = report["results"]
        analysis = report.get("self_evolution_analysis", {})
        cells = []
        for r in results:
            cells.append(f"{'✓' if r['success'] else '✗'} {r['turns']}轮")
        red = "—"
        if analysis.get("all_success"):
            r2, r3 = analysis.get("reduction_t2_vs_t1_pct"), analysis.get("reduction_t3_vs_t1_pct")
            red = f"T2:{r2}% / T3:{r3}%"
        evolve = "是" if analysis.get("shows_evolution") else ("否" if analysis.get("all_success") else "未全通过")
        lines.append(
            f"| {proj_category(report)} | {report['name']} | "
            + " | ".join(cells) + f" | {red} | {evolve} |")
    lines += [
        "",
        "## 说明",
        "",
        "- 回合数按「Turn 1 起连续递增序列」解析, 上一任务泄漏的尾回合不计入",
        "- 验证 fail-loud: 期望答案缺失、答案文件缺失、内容不匹配一律判 ✗",
        "",
    ]
    path = os.path.join(run_dir, "self_evolution_benchmark_report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  [汇总] {path}")


def proj_category(report):
    for p in PROJECTS:
        if p["key"] == report["project"]:
            return p["category"]
    return ""


# ── 回归测试 (--selftest) ─────────────────────────────────

def selftest():
    """针对 3 个根因的回归测试, 不启动 GA。"""
    failures = []

    def check(name, cond, detail=""):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
        if not cond:
            failures.append(name)

    print("== 回归测试 1: 回合泄漏过滤 ==")
    # 1a. 真实失败格式 (2026-08-13 15:27 实际输出: 未加 --verbose, 标记无 **)
    #     构造: 上一任务泄漏的 Turn 5 + 本任务真实的 Turn 1..8
    leaked = ["**LLM Running (Turn 5) ...**", "<summary>数据已验证，南京结果正确</summary>"]
    real = []
    for n in range(1, 9):
        real += [f"LLM Running (Turn {n}) ...", f"<summary>成都任务第{n}步处理中</summary>", "🛠️ code_run(...)"]
    text = "\n".join(leaked + real)
    turns = parse_turns(text)
    check("无星号格式(verbose=off 实际格式)解析 8 轮", len(turns) == 8,
          f"实际 {len(turns)} 轮 (2026-08-13 曾全部解析为 0)")
    check("泄漏段被丢弃, 回合编号为 1..8", [t["num"] for t in turns] == list(range(1, 9)))
    check("工具提取正确", all(t["tools"] == ["code_run"] for t in turns))
    # 1b. --verbose 带星号格式
    star_text = "\n".join(line for n in range(1, 4)
                          for line in [f"**LLM Running (Turn {n}) ...**", f"<summary>第{n}步</summary>"])
    check("带星号格式(--verbose)仍能解析", len(parse_turns(star_text)) == 3)
    # 1c. task_dir 模式格式
    td_text = "\n".join(line for n in range(1, 4)
                        for line in [f"**Turn {n} ...**", f"<summary>第{n}步</summary>"])
    check("task_dir 格式仍能解析", len(parse_turns(td_text)) == 3)

    print("== 回归测试 2: 验证器 fail-loud ==")
    proj_db = next(p for p in PROJECTS if p["key"] == "db_query")
    # 历史自动测错误答案 (国贸桥) vs 仓库期望 (中关村大街)
    wrong_ans = "/mnt/d/work/temp/answer_c1.json"
    if os.path.exists(wrong_ans):
        import shutil
        tmp = "/tmp/selftest_answer_c1.json"
        shutil.copy2(wrong_ans, tmp)
        lib = "/tmp/selftest_db_query"
        os.makedirs(lib, exist_ok=True)
        shutil.copy2(tmp, os.path.join(lib, "answer_c1.json"))
        ok, err = verify_task(proj_db, 0, "", lib)
        check("错误答案(国贸桥)判失败", ok is False, f"err={err}")
    else:
        print(f"  [SKIP] 缺少历史错误答案 {wrong_ans}")

    # 期望文件缺失 → 必须失败 (旧版静默放行的场景, run_one_benchmark.py:206-208)
    proj_fake = dict(proj_db)
    proj_fake["expected"] = ["不存在的文件.json", "expected_2.json", "expected_3.json"]
    ok, err = verify_task(proj_fake, 0, "", "/tmp/nonexistent_lib")
    check("期望文件缺失判失败(不再静默放行)", ok is False and "缺失" in err, f"err={err}")
    # 答案文件缺失 → 必须失败
    ok, err = verify_task(proj_db, 0, "", "/tmp/nonexistent_lib")
    check("答案文件缺失判失败", ok is False and "未生成答案文件" in err, f"err={err}")

    print("== 回归测试 3: 解析与比较细节 ==")
    a = {"count": 13, "total": 555, "top_item": "绳索"}
    e = {"count": 13, "total": 555, "top_item": "绳索"}
    ok, err = deep_compare(a, e)
    check("deep_compare 相同内容通过", ok)
    a2 = {"count": 12, "total": 555, "top_item": "绳索"}
    ok, err = deep_compare(a2, e)
    check("deep_compare 不同内容给出路径", not ok and "count" in err, f"err={err}")
    ok, _ = deep_compare({"s": "a b\n c"}, {"s": "abc"})
    check("deep_compare 空白归一化", ok)
    check("无 Turn 1 时返回空", parse_turns("**Turn 3 ...**\n随便") == [])
    buf = "🛠️ file_read(...)\nTOKEN: deadbeef\n"
    check("file_read 中的 TOKEN 不算证据", token_evidence(buf) is False)
    buf2 = "🛠️ code_run(...)\nTOKEN: deadbeef\n"
    check("code_run 后的 TOKEN 算证据", token_evidence(buf2) is True)
    buf3 = "🛠️ code_run(...)\nTOKEN: deadbeef\n🛠️ file_read(...)\n"
    check("执行后又读文件, TOKEN 不算证据", token_evidence(buf3) is False)

    print("== 回归测试 4: 评分封顶 ==")
    # 2026-08-13 15:27 真实数据: 营地物资 6/3/3 轮, 未封顶时总分 80.1/60
    fast = [dict(turns=6, success=True), dict(turns=3, success=True), dict(turns=3, success=True)]
    a = self_evolution_analysis(fast)
    scores = [a["scores"][f"task{i}"]["score"] for i in (1, 2, 3)]
    check("快于基线时每题得分封顶 20", all(s <= 20.0 for s in scores), f"实际 {scores}")
    check("总分不超过 60", sum(scores) <= 60.0 + 1e-9, f"总分 {sum(scores)}")

    print("== 回归测试 5: 喂入应答扣除 + [Debug] 噪音过滤 ==")
    # 5a. 2026-08-13 16:15 真实结构: 每个任务首轮 LLM 调用应答原始任务路径
    #     (无 WORKING MEMORY), GA 自己的 Current turn 计数器不含它
    #     复现 828077 e1: stdout 8 个标记, GA 计数 7
    feed_task = "\n".join(line for n in range(1, 9)
                          for line in [f"LLM Running (Turn {n}) ...", f"<summary>第{n}步</summary>",
                                       "🛠️ code_run(...)"])
    t = drop_feed_turn(parse_turns(feed_task))
    check("扣除喂入应答: 8 标记解析为 7 轮", len(t) == 7, f"实际 {len(t)} 轮")
    check("扣除后重新编号为 1..7", [x["num"] for x in t] == list(range(1, 8)))
    # 5b. GA 的 [Debug] 打印不能成为回合摘要 (2026-08-13 未知API T1 实际出现)
    noisy = ("LLM Running (Turn 6) ...\n"
             "[Debug] Current context: 10551 chars, 11 messages.\n"
             "API requires `Authorization` header instead of `X-API-Key`.\n"
             "🛠️ code_run(...)\n")
    t6 = analyze_turn(6, clean_ga_debug(noisy))
    check("[Debug] 行被过滤, 摘要为真实正文", t6["summary"].startswith("API requires"),
          f"实际 {t6['summary']!r}")
    check("clean_ga_debug 幂等", clean_ga_debug(clean_ga_debug(noisy)) == clean_ga_debug(noisy))
    # 5c. 2026-08-13 17:22 轮实际出现: [MixinSession]/[Cut] 等 GA 打印成为回合摘要
    noisy2 = ("LLM Running (Turn 10) ...\n"
              "[MixinSession] Using session (qwen)\n"
              "[Cut] 43528 -> 39691\n"
              "[Action] Running bash in temp: python3 xxx\n"
              "<summary>Task complete. Answer written.</summary>\n")
    t10 = analyze_turn(10, clean_ga_debug(noisy2))
    check("[MixinSession]/[Cut]/[Action] 行被过滤", t10["summary"] == "Task complete. Answer written.",
          f"实际 {t10['summary']!r}")
    # 5d. 只有 GA 打印、无模型正文的回合: 摘要保持空, 不抓 GA 行
    t11 = analyze_turn(11, clean_ga_debug("LLM Running (Turn 11) ...\n[MixinSession] Using session (qwen)\n"))
    check("纯 GA 打印回合摘要为空", t11["summary"] == "", f"实际 {t11['summary']!r}")
    # 5e. 2026-08-13 20:41 轮实际出现: 无 --verbose 时 llmcore 的 [Cache]/[Output]
    #     usage 打印先于模型正文打到 stdout (正文在调用结束后才 yield), 兜底摘要误取 [Cache]
    noisy3 = ("LLM Running (Turn 2) ...\n"
              "[Cache] input=3210 cached=0\n"
              "[Output] tokens=55\n"
              "我来完成这个数据库查询任务。首先需要定位数据库文件并探索其结构。\n\n"
              "🛠️ file_read(...)\n")
    t12 = analyze_turn(12, clean_ga_debug(noisy3))
    check("[Cache]/[Output] 行被过滤, 摘要为后续模型正文",
          t12["summary"].startswith("我来完成这个数据库查询任务"),
          f"实际 {t12['summary']!r}")

    print()
    if failures:
        print(f"回归测试失败 {len(failures)} 项: {failures}")
        sys.exit(1)
    print("全部回归测试通过 ✓")


# ── 主流程 ────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="自进化类任务统一评测脚本 (v3)")
    ap.add_argument("--model-name", default="GA", help="报告中的模型显示名")
    ap.add_argument("--model-id", default="ga", help="模型 ID (同时是 res/ 下的模型文件夹名)")
    ap.add_argument("--projects", default=None, help="逗号分隔的工程 key, 默认全部")
    ap.add_argument("--timeout", type=int, default=300, help="单任务超时秒数")
    ap.add_argument("--quiet-secs", type=int, default=10, help="证据出现后的静默判定秒数")
    ap.add_argument("--ga-dir", default=GA_DIR, help="GenericAgent 目录 (测试用)")
    ap.add_argument("--ga-script", default=GA_SCRIPT, help="GA 入口脚本名 (测试用)")
    ap.add_argument("--skip-cleanup", action="store_true", help="跳过轮初清理")
    ap.add_argument("--selftest", action="store_true", help="仅运行回归测试, 不启动 GA")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    print("═" * 62)
    print(f"  自进化 Benchmark v3 | 模型: {args.model_name} ({args.model_id})")
    print(f"  测试库: {LIB_DIR}")
    print("═" * 62)

    # 本次评测的结果目录: res/<model-id>/<YYYY-MM-DD-HHMM>/
    run_dir = os.path.join(RES_DIR, args.model_id,
                           datetime.now().strftime("%Y-%m-%d-%H%M"))
    os.makedirs(run_dir, exist_ok=True)
    print(f"[结果目录] {run_dir}")

    # ── 轮初统一清理 (恢复初始状态) ──
    if not args.skip_cleanup:
        cleanup = os.path.join(LIB_DIR, "cleanup.sh")
        if os.path.exists(cleanup):
            print(f"\n[清理] {cleanup}")
            r = subprocess.run(["bash", cleanup], capture_output=True, text=True)
            print(r.stdout.rstrip())
        else:
            print(f"[清理] ⚠ 未找到 {cleanup}, 跳过")

    selected = PROJECTS
    if args.projects:
        keys = [k.strip() for k in args.projects.split(",")]
        selected = [p for p in PROJECTS if p["key"] in keys]
        if not selected:
            print(f"未知工程 key: {args.projects} (可选: {[p['key'] for p in PROJECTS]})")
            sys.exit(1)

    all_reports = []
    for proj in selected:
        results = run_project(proj, args)
        analysis = self_evolution_analysis(results)
        report = write_reports(proj, results, args, analysis, run_dir)
        all_reports.append(report)

    write_summary_md(all_reports, args, run_dir)

    # ── 控制台总览 ──
    print(f"\n{'=' * 62}")
    print("  总览")
    print(f"{'=' * 62}")
    for report in all_reports:
        cells = [f"{'✓' if r['success'] else '✗'}{r['turns']}轮" for r in report["results"]]
        print(f"  {report['name']:<6} " + "  ".join(cells))


if __name__ == "__main__":
    main()
