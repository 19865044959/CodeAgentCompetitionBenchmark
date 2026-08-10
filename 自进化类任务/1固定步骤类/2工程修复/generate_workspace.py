#!/usr/bin/env python3
"""生成三道自进化题目的工作区"""

import os
import sys
import json
import shutil
import hashlib
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
SKELETON_DIR = BASE_DIR / "skeleton"
OUTPUT_DIR = BASE_DIR / "cases"

TASKS = [
    {
        "id": 1,
        "name": "alpha",
        "port": "8080",
        "svc_name": "alpha-app",
        "wrong_port": "9999",
        "wrong_name": "wrong-app",
    },
    {
        "id": 2,
        "name": "beta",
        "port": "9090",
        "svc_name": "beta-svc",
        "wrong_port": "1111",
        "wrong_name": "bad-svc",
    },
    {
        "id": 3,
        "name": "gamma",
        "port": "3000",
        "svc_name": "gamma-daemon",
        "wrong_port": "7777",
        "wrong_name": "broken",
    },
]


def make_rules(task):
    """根据任务配置生成断言规则列表"""
    name = task["name"]
    return [
        ("DIR",  f"logs/{name}",        "755"),
        ("EXIST", f"config/{name}.conf", None),
        ("LINE", f"config/{name}.conf",   3, f"port {task['port']}"),
        ("LINE", f"config/{name}.conf",   6, f"name {task['svc_name']}"),
        ("EXIST", "bin/start.sh",       None),
        ("PERM",  "bin/start.sh",       "755"),
    ]


def compute_token(rules):
    """对规则列表计算确定性 token"""
    rules_json = json.dumps(rules, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(rules_json.encode()).hexdigest()[:12]


def generate_workspace(task, rules, token):
    """为单个任务生成工作区"""
    ws = OUTPUT_DIR / f"ws_{task['id']}"
    name = task["name"]

    if ws.exists():
        shutil.rmtree(ws)

    shutil.copytree(SKELETON_DIR, ws)

    # 1. spec.md
    spec = (ws / "spec.md").read_text()
    spec = spec.replace("{name}", name).replace("{port}", task["port"]).replace("{svc_name}", task["svc_name"])
    (ws / "spec.md").write_text(spec)

    # 2. config/{name}.conf（含错误）
    conf = (ws / "config" / "app.conf").read_text()
    conf = conf.replace("{name}", name).replace("{wrong_port}", task["wrong_port"]).replace("{wrong_name}", task["wrong_name"])
    (ws / "config" / "app.conf").unlink()
    (ws / "config" / f"{name}.conf").write_text(conf)

    # 3. bin/start.sh
    start_sh = ws / "bin" / "start.sh"
    content = start_sh.read_text().replace("{name}", name).replace("{port}", task["port"])
    start_sh.write_text(content)

    # 4. 不创建 logs/{name}/ —— 故意错误

    # 5. 生成 check 脚本
    check_src = (BASE_DIR / "check.py").read_text()
    rules_str = json.dumps(rules, ensure_ascii=False).replace("null", "None")
    check_src = check_src.replace("__RULES_PLACEHOLDER__", rules_str)
    check_src = check_src.replace('"__TOKEN__"', f'"{token}"')
    (ws / "check").write_text(check_src)
    os.chmod(ws / "check", 0o755)

    return ws


def main():
    print("生成自进化任务工作区...")
    for task in TASKS:
        rules = make_rules(task)
        token = compute_token(rules)
        ws = generate_workspace(task, rules, token)

        # expected_N.json 只存 token
        expected_path = BASE_DIR / f"expected_{task['id']}.json"
        expected_path.write_text(json.dumps({"token": token}, ensure_ascii=False) + "\n")

        print(f"  Task {task['id']} ({task['name']}): {ws}")
        print(f"    Token: {token}")
        print(f"    Expected: {expected_path}")
    print("完成。")


if __name__ == "__main__":
    main()
