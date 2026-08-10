#!/usr/bin/env python3
"""check.py — 文件系统验证脚本。"""

import os
import stat


# ── 断言验证函数 ──────────────────────────────────────────

def check_dir(target, expected_perm):
    if not os.path.isdir(target):
        return {"status": "fail", "expected": f"exists,{expected_perm}", "actual": "不存在"}
    actual_perm = oct(os.stat(target).st_mode)[-3:]
    if actual_perm != expected_perm:
        return {"status": "fail", "expected": expected_perm, "actual": actual_perm}
    return {"status": "ok"}


def check_exist(target):
    if os.path.isfile(target):
        return {"status": "ok"}
    return {"status": "fail", "expected": "exists", "actual": "不存在"}


def check_line(target, line_num, expected):
    if not os.path.isfile(target):
        return {"status": "fail", "expected": f"line {line_num}: {expected}", "actual": "文件不存在"}
    with open(target, "r") as f:
        lines = f.readlines()
    if line_num > len(lines):
        return {"status": "fail", "expected": f"line {line_num}: {expected}", "actual": f"文件只有 {len(lines)} 行"}
    actual = lines[line_num - 1].rstrip("\n").rstrip("\r")
    if actual != expected:
        return {"status": "fail", "expected": expected, "actual": actual}
    return {"status": "ok"}


def check_perm(target, expected_perm):
    if not os.path.isfile(target):
        return {"status": "fail", "expected": expected_perm, "actual": "文件不存在"}
    actual_perm = oct(os.stat(target).st_mode)[-3:]
    if actual_perm != expected_perm:
        return {"status": "fail", "expected": expected_perm, "actual": actual_perm}
    return {"status": "ok"}


# ── 规则分发 ──────────────────────────────────────────────

def run_checks(rules):
    results = []
    for rule in rules:
        t = rule[0]
        target = rule[1]
        if t == "DIR":
            r = check_dir(target, rule[2])
            results.append({"type": "DIR", "target": target, **r})
        elif t == "EXIST":
            r = check_exist(target)
            results.append({"type": "EXIST", "target": target, **r})
        elif t == "LINE":
            r = check_line(target, rule[2], rule[3])
            results.append({"type": "LINE", "target": f"{target}:{rule[2]}", **r})
        elif t == "PERM":
            r = check_perm(target, rule[2])
            results.append({"type": "PERM", "target": target, **r})
    return results


# ── 主逻辑 ────────────────────────────────────────────────

def main():
    # 切换到脚本所在目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # 占位符 — 由 generate_workspace.py 注入
    RULES = __RULES_PLACEHOLDER__
    TOKEN = "__TOKEN__"

    results = run_checks(RULES)
    passed = sum(1 for r in results if r["status"] == "ok")
    failed = len(results) - passed

    if failed == 0:
        print(f"[ OK ] 全部通过 (6/6)")
        print(f"TOKEN: {TOKEN}")
    else:
        print(f"[FAIL] {passed}/{passed + failed} 通过，{failed} 失败")
        for r in results:
            if r["status"] == "fail":
                print(f"[FAIL] {r['type']:5s} {r['target']:30s} — 期望 {r.get('expected','?')}，实际 {r.get('actual','?')}")


if __name__ == "__main__":
    main()
