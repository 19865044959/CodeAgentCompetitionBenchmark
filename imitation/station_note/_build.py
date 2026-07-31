#!/usr/bin/env python3
"""
Build script — generates all sample CSVs and expected outputs.
Run this to regenerate the task data.

Rule set (hidden from agent, discovered by comparing samples):
  1. Drop columns: 备注, 录入人
  2. Rename: 单价 → 总价
  3. Date: 2026/7/3 → 2026-07-03 (YYYY-MM-DD, zero-padded)
  4. 总价 = 数量 × 单价, ROUND_HALF_UP to 2 decimal places
  5. Missing 数量 → 0, 总价 → 0.00
  6. Sort by 站点 ascending (string order), stable within same 站点
  7. Summary row: 编号="合计", sum 数量 and 总价, other columns empty
  8. Output encoding: UTF-8, LF line endings, trailing newline
"""

import csv
import io
import os
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ── sample data definitions ──────────────────────────────────

# (id, date_in, station, item, qty, unit_price, note, recorder)
SAMPLE_1_IN = [
    ["W-001", "2026/7/3",  "站点B", "绳索", 12,   3.5,   "",   "老陈"],
    ["W-002", "2026/7/3",  "站点A", "绷带", 8,     6.25,  "急件", "小李"],
    ["W-003", "2026/7/4",  "站点A", "口粮", None,  4.2,   "数量待补", "小李"],
    ["W-004", "2026/7/4",  "站点B", "绳索", 20,    3.5,   "",   "老陈"],
    ["W-005", "2026/7/5",  "站点B", "燃油", 6,     25.8,  "",   "老陈"],
]

# (id, date_in, station, item, qty, unit_price, note, recorder)
SAMPLE_2_IN = [
    ["W-010", "2026/7/6",  "站点C", "信标电池", 3,  1.375, "校准件", "宁叔"],
    ["W-011", "2026/7/7",  "站点A", "斧头",     2,  18.40, "",       "阿青"],
    ["W-012", "2026/7/7",  "站点C", "绳索",     40, 0.30,  "",       "宁叔"],
    ["W-013", "2026/7/8",  "站点A", "铁钉",     100,0.12,  "",       "阿青"],
    ["W-014", "2026/7/8",  "站点B", "饮用水",    None,2.50, "待盘点", "阿青"],
]

# (id, date_in, station, item, qty, unit_price, note, recorder)
WORK_IN = [
    ["W-101", "2026/7/12", "站点B", "防水布",  9,   7.35,   "",       "老陈"],
    ["W-102", "2026/7/12", "站点A", "急救包",  5,   18.60,  "",       "小李"],
    ["W-103", "2026/7/13", "站点C", "信号弹",  3,   22.225, "",       "宁叔"],
    ["W-104", "2026/7/13", "站点A", "饮用水",  30,  1.25,   "",       "小李"],
    ["W-105", "2026/7/14", "站点B", "备用灯",  None,11.80,  "未到货", "老陈"],
    ["W-106", "2026/7/14", "站点C", "绳索",    14,  3.45,   "",       "宁叔"],
]

IN_HEADER = ["编号", "日期", "站点", "物资", "数量", "单价", "备注", "录入人"]
OUT_HEADER = ["编号", "日期", "站点", "物资", "数量", "总价"]


def convert_date(d: str) -> str:
    """2026/7/3 → 2026-07-03"""
    parts = d.split("/")
    return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"


def calc_amount(qty, unit_price):
    """ROUND_HALF_UP to 2 decimal places."""
    if qty is None:
        return Decimal("0.00")
    result = Decimal(str(qty)) * Decimal(str(unit_price))
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def transform(rows):
    """Apply all transformation rules to input rows."""
    # Step 1-2: select columns and rename
    out_rows = []
    for r in rows:
        rid, date_in, station, item, qty, unit_price, note, recorder = r
        date_out = convert_date(date_in)
        amount = calc_amount(qty, unit_price)
        qty_out = 0 if qty is None else qty
        out_rows.append([rid, date_out, station, item, str(qty_out), str(amount)])

    # Step 6: stable sort by station
    out_rows.sort(key=lambda r: r[2])  # r[2] = station

    # Step 7: summary row
    total_qty = sum(
        int(r[4]) for r in out_rows
    )  # qty is now string, convert back for sum
    total_amount = sum(Decimal(r[5]) for r in out_rows)
    summary = ["合计", "", "", "", str(total_qty), str(total_amount)]

    return out_rows + [summary]


def format_csv(header, rows):
    """Write CSV to bytes with exact format: UTF-8, LF, trailing newline, no quoting unless needed."""
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def write_csv(path, header, rows):
    path.write_bytes(format_csv(header, rows))


def main():
    # Sample 1
    write_csv(ROOT / "samples/in_1.csv", IN_HEADER, SAMPLE_1_IN)
    write_csv(ROOT / "samples/out_1.csv", OUT_HEADER, transform(SAMPLE_1_IN))

    # Sample 2
    write_csv(ROOT / "samples/in_2.csv", IN_HEADER, SAMPLE_2_IN)
    write_csv(ROOT / "samples/out_2.csv", OUT_HEADER, transform(SAMPLE_2_IN))

    # Work input
    write_csv(ROOT / "work/in.csv", IN_HEADER, WORK_IN)

    # Expected output (hidden in _reference)
    write_csv(ROOT / "_reference/out.csv", OUT_HEADER, transform(WORK_IN))

    print("All CSV files generated.")
    for f in sorted(ROOT.rglob("*.csv")):
        print(f"  {f.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
