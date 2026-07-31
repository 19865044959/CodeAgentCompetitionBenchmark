#!/usr/bin/env python3
"""
Generate task workspaces for the simplified D-track benchmark.

Usage:
    python3 generate_workspace.py [--task 1]

Creates cases/ws_N/ with:
    - samples/  (input/output pairs)
    - work/in.csv  (the actual data to process)
    - check  (validation script, prints TOKEN on success)
    - spec.md  (task description for the agent)
"""

import os
import sys
import json
import shutil
import hashlib
import csv
import io
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = BASE_DIR / "cases"

# ── Rule engine (same as _build.py) ──────────────────────────

IN_HEADER = ["编号", "日期", "站点", "物资", "数量", "单价", "备注", "录入人"]
OUT_HEADER = ["编号", "日期", "站点", "物资", "数量", "总价"]


def convert_date(d: str) -> str:
    parts = d.split("/")
    return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"


def calc_amount(qty, unit_price):
    if qty is None:
        return Decimal("0.00")
    result = Decimal(str(qty)) * Decimal(str(unit_price))
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def transform(rows):
    out_rows = []
    for r in rows:
        rid, date_in, station, item, qty, unit_price, note, recorder = r
        date_out = convert_date(date_in)
        amount = calc_amount(qty, unit_price)
        qty_out = 0 if qty is None else qty
        out_rows.append([rid, date_out, station, item, str(qty_out), str(amount)])
    out_rows.sort(key=lambda r: r[2])
    total_qty = sum(int(r[4]) for r in out_rows)
    total_amount = sum(Decimal(r[5]) for r in out_rows)
    summary = ["合计", "", "", "", str(total_qty), str(total_amount)]
    return out_rows + [summary]


def format_csv(header, rows) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


# ── Task definitions ─────────────────────────────────────────

TASKS = [
    {
        "id": 1,
        "name": "灰雀",
        "samples": [
            {  # Sample 1: shows basic rules + missing qty → 0
                "in": [
                    ["W-001", "2026/7/3",  "站点B", "绳索", 12,   3.5,   "",   "老陈"],
                    ["W-002", "2026/7/3",  "站点A", "绷带", 8,     6.25,  "急件", "小李"],
                    ["W-003", "2026/7/4",  "站点A", "口粮", None,  4.2,   "数量待补", "小李"],
                    ["W-004", "2026/7/4",  "站点B", "绳索", 20,    3.5,   "",   "老陈"],
                    ["W-005", "2026/7/5",  "站点B", "燃油", 6,     25.8,  "",   "老陈"],
                ]
            },
            {  # Sample 2: shows rounding + different station order
                "in": [
                    ["W-010", "2026/7/6",  "站点C", "信标电池", 3,  1.375, "校准件", "宁叔"],
                    ["W-011", "2026/7/7",  "站点A", "斧头",     2,  18.40, "",       "阿青"],
                    ["W-012", "2026/7/7",  "站点C", "绳索",     40, 0.30,  "",       "宁叔"],
                    ["W-013", "2026/7/8",  "站点A", "铁钉",     100,0.12,  "",       "阿青"],
                    ["W-014", "2026/7/8",  "站点B", "饮用水",    None,2.50, "待盘点", "阿青"],
                ]
            },
        ],
        "work": [
            ["W-101", "2026/7/12", "站点B", "防水布",  9,   7.35,   "",       "老陈"],
            ["W-102", "2026/7/12", "站点A", "急救包",  5,   18.60,  "",       "小李"],
            ["W-103", "2026/7/13", "站点C", "信号弹",  3,   22.225, "",       "宁叔"],
            ["W-104", "2026/7/13", "站点A", "饮用水",  30,  1.25,   "",       "小李"],
            ["W-105", "2026/7/14", "站点B", "备用灯",  None,11.80,  "未到货", "老陈"],
            ["W-106", "2026/7/14", "站点C", "绳索",    14,  3.45,   "",       "宁叔"],
        ],
    },
    {
        "id": 2,
        "name": "柳莺",
        "samples": [
            {  # Sample 1: shows basic rules + missing qty → 0, different items/stations
                "in": [
                    ["T-001", "2026/8/10", "东站", "帐篷",     5,   120.00, "",       "老王"],
                    ["T-002", "2026/8/10", "西站", "净水片",   50,  0.85,   "急用",   "小赵"],
                    ["T-003", "2026/8/11", "东站", "睡袋",     3,   45.50,  "",       "老王"],
                    ["T-004", "2026/8/11", "西站", "压缩饼干", None,12.80,  "待确认", "小赵"],
                    ["T-005", "2026/8/12", "东站", "帐篷",     2,   120.00, "",       "老王"],
                ]
            },
            {  # Sample 2: shows rounding + more station variety, edge cases
                "in": [
                    ["T-010", "2026/8/13", "南站", "电池",     8,  3.675,  "精密",   "老孙"],
                    ["T-011", "2026/8/14", "东站", "手套",     20, 5.55,   "",       "老王"],
                    ["T-012", "2026/8/14", "南站", "净水片",   30, 0.85,   "",       "老孙"],
                    ["T-013", "2026/8/15", "西站", "燃料块",   4,  22.225, "",       "小赵"],
                    ["T-014", "2026/8/15", "东站", "急救箱",   None,35.00, "盘点中", "老王"],
                ]
            },
        ],
        "work": [
            ["T-101", "2026/8/20", "东站", "睡袋",     7,   45.50,  "",       "老王"],
            ["T-102", "2026/8/20", "南站", "信号枪",   2,   88.125, "",       "老孙"],
            ["T-103", "2026/8/21", "西站", "压缩饼干", 15,  12.80,  "",       "小赵"],
            ["T-104", "2026/8/21", "东站", "手套",     12,  5.55,   "",       "老王"],
            ["T-105", "2026/8/22", "南站", "电池",     None,3.675,  "缺货",   "老孙"],
            ["T-106", "2026/8/22", "西站", "燃料块",   6,   22.225, "",       "小赵"],
        ],
    },
    {
        "id": 3,
        "name": "松鸦",
        "samples": [
            {  # Sample 1: shows basic rules + missing qty → 0, mechanical parts theme
                "in": [
                    ["S-001", "2026/9/5",  "北站", "零件A",  25,  2.40,   "",       "大刘"],
                    ["S-002", "2026/9/5",  "中站", "润滑油", 10,  15.75,  "急件",   "阿明"],
                    ["S-003", "2026/9/6",  "北站", "螺丝",   200, 0.08,   "",       "大刘"],
                    ["S-004", "2026/9/6",  "中站", "零件A",  None,2.40,   "数量未定", "阿明"],
                    ["S-005", "2026/9/7",  "北站", "油漆",   3,   45.125, "",       "大刘"],
                ]
            },
            {  # Sample 2: shows rounding + different station distributions
                "in": [
                    ["S-010", "2026/9/8",  "中站", "焊条",   50,  1.375,  "",       "阿明"],
                    ["S-011", "2026/9/9",  "北站", "润滑油", 6,   15.75,  "",       "大刘"],
                    ["S-012", "2026/9/9",  "中站", "螺丝",   500, 0.08,   "",       "阿明"],
                    ["S-013", "2026/9/10", "北站", "轴承",   8,   33.33,  "",       "大刘"],
                    ["S-014", "2026/9/10", "中站", "焊条",   None,1.375,  "待盘点", "阿明"],
                ]
            },
        ],
        "work": [
            ["S-101", "2026/9/15", "中站", "零件A",  18,  2.40,   "",       "阿明"],
            ["S-102", "2026/9/15", "北站", "焊条",   35,  1.375,  "",       "大刘"],
            ["S-103", "2026/9/16", "中站", "油漆",   5,   45.125, "",       "阿明"],
            ["S-104", "2026/9/16", "北站", "螺丝",   150, 0.08,   "",       "大刘"],
            ["S-105", "2026/9/17", "中站", "轴承",   None,33.33,  "未到",   "阿明"],
            ["S-106", "2026/9/17", "北站", "润滑油", 4,   15.75,  "",       "大刘"],
        ],
    },
]


# ── Check script template ────────────────────────────────────

CHECK_TEMPLATE = '''#!/usr/bin/env python3
"""check — 验证 work/out.csv 是否与标准成品一致。"""

import os
import sys
import hashlib

os.chdir(os.path.dirname(os.path.abspath(__file__)))

EXPECTED_MD5 = "{expected_md5}"
TOKEN = "{token}"

def main():
    out_path = "work/out.csv"
    if not os.path.isfile(out_path):
        print("[FAIL] 未找到 work/out.csv，请先生成输出文件。")
        sys.exit(1)

    actual = open(out_path, "rb").read()
    actual_md5 = hashlib.md5(actual).hexdigest()

    if actual_md5 != EXPECTED_MD5:
        print("[FAIL] CSV 内容与标准成品不一致。")
        print(f"  期望 MD5: {{EXPECTED_MD5}}")
        print(f"  实际 MD5: {{actual_md5}}")
        print()
        print("  提示：请检查样板的转换规则是否全部正确应用：")
        print("  - 列的增删和重命名")
        print("  - 日期格式转换")
        print("  - 金额计算公式和精度")
        print("  - 缺失数量处理")
        print("  - 排序依据和稳定性")
        print("  - 合计行的标签和求和")
        print("  - 文件编码(UTF-8)和换行(LF)")
        sys.exit(1)

    print("[ OK ] work/out.csv 与标准成品一致，全部通过！")
    print(f"TOKEN: {{TOKEN}}")

if __name__ == "__main__":
    main()
'''


# ── Task spec template ───────────────────────────────────────

SPEC_TEMPLATE_EXPLORE = '''# 账册整理任务 — {name}驿站

## 任务背景

你是荒野后勤署的账册整理员。{name}驿站在沙暴中遗失了账册处理规程，只留下了若干组已经通过总署验收的原始清单和成品清单。

请根据这些样板，处理本次收到的物资账册。

## 任务要求

1. 查看 `samples/` 中的输入/输出样板（`in_*.csv` → `out_*.csv`）
2. 比较每组输入和输出，归纳完整处理规则
3. 读取待处理文件 `work/in.csv`
4. 按样板中的同一套规则生成 `work/out.csv`
5. 运行 `./check` 验证结果
6. 当 `./check` 输出 `TOKEN: ...` 时，任务完成

## 数据文件说明

| 文件 | 说明 |
|---|---|
| `samples/in_1.csv` | 第 1 组原始样板 |
| `samples/out_1.csv` | 第 1 组已验收成品 |
| `samples/in_2.csv` | 第 2 组原始样板 |
| `samples/out_2.csv` | 第 2 组已验收成品 |
| `work/in.csv` | 本题待处理文件 |

## 提交规则

- 最终答案文件为 `work/out.csv`
- 运行 `./check` 验证，通过即完成
- CSV 使用 UTF-8 编码，LF 换行

## 提示

- 规则不会在题面中直接给出，样板是唯一依据
- 不要只观察一组样板，应使用全部样板进行交叉验证
- 注意数值精度、日期格式、排序方式等细节
- 可以反复运行 `./check` 查看是否通过
'''

SPEC_TEMPLATE_REUSE = '''# 账册整理任务 — {name}驿站

## 任务背景

你是荒野后勤署的账册整理员。{name}驿站也需要整理物资账册。

**重要：处理规则与题1（灰雀驿站）完全相同！** 你无需重新分析样板，直接将已经归纳好的规则应用到新数据即可。

## 任务要求

1. 样板文件 `samples/` 与题1 共享同一份（通过软链接），规则完全一致
2. 读取待处理文件 `work/in.csv`（本题新数据，编号前缀为 {id_prefix}）
3. 按**题1 同一套规则**生成 `work/out.csv`
4. 运行 `./check` 验证结果
5. 当 `./check` 输出 `TOKEN: ...` 时，任务完成

## 数据文件说明

| 文件 | 说明 |
|---|---|
| `samples/` | 与题1 共享的样板（软链接，规则一致） |
| `work/in.csv` | 本题待处理文件（{name}驿站物资，编号 {id_prefix}-xxx） |

## 提交规则

- 最终答案文件为 `work/out.csv`
- 运行 `./check` 验证，通过即完成
- CSV 使用 UTF-8 编码，LF 换行

## 提示

- **规则与题1（灰雀驿站）完全一致，不要再花时间分析样板！**
- 如果你在题1 中编写了处理脚本/函数，直接修改输入输出路径复用即可
- 可以反复运行 `./check` 查看是否通过
'''


def compute_token(expected_bytes: bytes) -> str:
    """Derive deterministic token from expected output."""
    return hashlib.md5(expected_bytes).hexdigest()[:12]


def generate_workspace(task: dict):
    """Generate a complete workspace for one task."""
    ws = OUTPUT_DIR / f"ws_{task['id']}"
    if ws.exists():
        shutil.rmtree(ws)

    # Create directories
    (ws / "work").mkdir(parents=True)

    # Symlink to shared samples instead of copying
    samples_link = ws / "samples"
    if not samples_link.exists():
        os.symlink("../../samples", str(samples_link))

    # Generate work input
    (ws / "work" / "in.csv").write_bytes(format_csv(IN_HEADER, task["work"]))

    # Generate expected output
    expected_bytes = format_csv(OUT_HEADER, transform(task["work"]))
    expected_md5 = hashlib.md5(expected_bytes).hexdigest()
    token = hashlib.md5(expected_bytes).hexdigest()[:12]

    # Generate check script
    check_content = CHECK_TEMPLATE.format(
        expected_md5=expected_md5,
        token=token,
    )
    check_path = ws / "check"
    check_path.write_text(check_content)
    os.chmod(check_path, 0o755)

    # Generate task spec — use reuse template for tasks 2 and 3
    tid = task["id"]
    if tid == 1:
        spec_content = SPEC_TEMPLATE_EXPLORE.format(name=task["name"])
    else:
        # Determine id prefix: task 1 data uses W-, task 2 uses T-, task 3 uses S-
        prefix = {2: "T", 3: "S"}.get(tid, "?")
        spec_content = SPEC_TEMPLATE_REUSE.format(name=task["name"], id_prefix=prefix)
    (ws / "spec.md").write_text(spec_content)

    # Save expected token for benchmark runner
    expected_path = BASE_DIR / "ans" / f"expected_token_{task['id']}.json"
    expected_path.write_text(
        json.dumps({"token": token, "task_id": task["id"]}, ensure_ascii=False) + "\n"
    )

    return ws, token


def main():
    print("生成自进化任务 station_note 工作区...")

    # Generate shared samples from task 1 data (at top level)
    task0 = TASKS[0]
    for i, sample in enumerate(task0["samples"], 1):
        (BASE_DIR / "samples" / f"in_{i}.csv").write_bytes(
            format_csv(IN_HEADER, sample["in"])
        )
        (BASE_DIR / "samples" / f"out_{i}.csv").write_bytes(
            format_csv(OUT_HEADER, transform(sample["in"]))
        )
    print(f"  Shared samples generated in samples/")

    # Generate each case workspace
    for task in TASKS:
        ws, token = generate_workspace(task)
        print(f"  Task {task['id']} ({task['name']}): {ws}")
        print(f"    Token: {token}")
        print(f"    samples -> ../../samples (symlink)")

    print("完成。")


if __name__ == "__main__":
    main()
