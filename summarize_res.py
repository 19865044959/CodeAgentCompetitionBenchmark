#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汇总 res/ 下各模型的多轮评测结果:
  1. 每道题的平均正确率 (题1/2/3, 跨 6 个工程)
  2. 每道题的平均消耗回合
  3. 题2/题3 相对题1 的平均回合缩减 (绝对轮数 + 百分比)

用法:
  python3 summarize_res.py [res目录]
  默认 res目录 = <脚本所在目录>/自进化类任务/res

说明:
  - 每个模型目录下的每个时间戳子目录 = 一次完整评测 (6 个工程报告, 18 道题)
  - 空的时间戳目录 (评测进行中) 自动跳过
  - 回合均值 = 该题位所有尝试的平均 (含失败任务; 括号内为仅成功任务的均值)
"""
import json
import os
import sys
from collections import defaultdict

# 不参与统计的工程 (按报告 "name" 字段匹配); 数据库查询的旧数据受 prompt 路径表述问题影响
EXCLUDE = {"数据库查询"}


def disp_width(s):
    """终端显示宽度: CJK 字符按 2 计。"""
    return sum(2 if ord(c) > 127 else 1 for c in s)


def pad(s, w):
    return s + " " * max(0, w - disp_width(s))


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    res_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, "自进化类任务", "res")
    res_dir = os.path.abspath(res_dir)
    if not os.path.isdir(res_dir):
        sys.exit(f"res 目录不存在: {res_dir}")

    # data[model][工程名][q] -> {"ok": [...], "turns": [...], "turns_ok": [...]}
    data = defaultdict(lambda: defaultdict(
        lambda: {q: {"ok": [], "turns": [], "turns_ok": []} for q in (1, 2, 3)}))
    n_runs = {}
    skipped = []

    for model in sorted(os.listdir(res_dir)):
        mdir = os.path.join(res_dir, model)
        if not os.path.isdir(mdir):
            continue
        n_runs[model] = 0
        for rdir in sorted(os.listdir(mdir)):
            rpath = os.path.join(mdir, rdir)
            if not os.path.isdir(rpath):
                continue
            jsons = sorted(f for f in os.listdir(rpath) if f.endswith(".json"))
            if not jsons:                      # 评测进行中的轮次目录
                skipped.append(f"{model}/{rdir}")
                continue
            n_runs[model] += 1
            for fn in jsons:
                with open(os.path.join(rpath, fn), encoding="utf-8") as fh:
                    rep = json.load(fh)
                pname = rep.get("name", "")
                if pname in EXCLUDE:
                    continue
                for r in rep.get("results", []):
                    q = r.get("task")
                    if q not in (1, 2, 3):
                        continue
                    t = r.get("turns")
                    if not isinstance(t, (int, float)):
                        continue
                    ok = bool(r.get("success"))
                    data[model][pname][q]["ok"].append(ok)
                    data[model][pname][q]["turns"].append(t)
                    if ok:
                        data[model][pname][q]["turns_ok"].append(t)

    if not data:
        sys.exit("res 目录下没有找到任何评测报告")

    def stats(agg):
        """返回 [(n, 正确率%, 全部均值, 成功均值|None) × 3题]"""
        out = []
        for q in (1, 2, 3):
            a = agg[q]
            n = len(a["ok"])
            rate = 100.0 * sum(a["ok"]) / n if n else 0.0
            t_all = sum(a["turns"]) / n if n else 0.0
            t_ok = sum(a["turns_ok"]) / len(a["turns_ok"]) if a["turns_ok"] else None
            out.append((n, rate, t_all, t_ok))
        return out

    # 各模型 + 合计(全部尝试合并)
    EMPTY = {q: {"ok": [], "turns": [], "turns_ok": []} for q in (1, 2, 3)}

    def agg_model(m):
        agg = defaultdict(lambda: {"ok": [], "turns": [], "turns_ok": []})
        for qs in data[m].values():
            for q in (1, 2, 3):
                for k in agg[q]:
                    agg[q][k] += qs[q][k]
        return agg

    model_agg = {m: agg_model(m) for m in data}
    rows = [(m, n_runs.get(m, 0), stats(model_agg[m])) for m in sorted(data)]
    pooled = defaultdict(lambda: {"ok": [], "turns": [], "turns_ok": []})
    for m in data:
        for q in (1, 2, 3):
            for k in pooled[q]:
                pooled[q][k] += model_agg[m][q][k]
    rows.append(("合计", sum(n_runs.values()), stats(pooled)))

    def fmt_rate(n, rate):
        return f"{rate:5.1f}% {int(round(rate / 100 * n))}/{n}"

    def fmt_turns(t_all, t_ok):
        ok = f"{t_ok:4.1f}" if t_ok is not None else "  — "
        return f"{t_all:5.1f} ({ok})"

    def fmt_red(t1, tq):
        """缩减 = 题1均值 - 题q均值; 正值表示回合减少。"""
        if not t1:
            return "—"
        d, pct = t1 - tq, (t1 - tq) / t1 * 100
        return f"{d:.1f}turns ({pct:.1f}%)"

    WN, WR = 16, 9   # 模型列宽 / 执行次数列宽

    def name_runs_cells(name, runs, cells):
        return pad(name, WN) + pad(str(runs), WR) + "".join(pad(c, 15) for c in cells)

    print(f"评测数据目录: {res_dir}")
    print()

    print("=== 1. 每道题平均正确率 ===")
    print(pad("模型", WN) + pad("执行次数", WR) + "".join(pad(h, 15) for h in ["题1", "题2", "题3"]))
    for name, runs, st in rows:
        cells = [fmt_rate(n, rate) for (n, rate, _, _) in st]
        print(name_runs_cells(name, runs, cells))
    print()

    print("=== 2. 每道题平均消耗回合 (括号内为仅成功任务) ===")
    print(pad("模型", WN) + pad("执行次数", WR) + "".join(pad(h, 15) for h in ["题1", "题2", "题3"]))
    for name, runs, st in rows:
        cells = [fmt_turns(t_all, t_ok) for (_, _, t_all, t_ok) in st]
        print(name_runs_cells(name, runs, cells))
    print()

    print("=== 3. 题2/题3 相对题1 的平均回合缩减 ===")
    print(pad("模型", WN) + "".join(pad(h, 17) for h in ["题1均值", "题2均值", "题2缩减", "题3均值", "题3缩减"]))
    for name, runs, st in rows:
        (_, _, t1, _), (_, _, t2, _), (_, _, t3, _) = st
        cells = [f"{t1:5.1f}", f"{t2:5.1f}", fmt_red(t1, t2), f"{t3:5.1f}", fmt_red(t1, t3)]
        print(pad(name, WN) + "".join(pad(c, 17) for c in cells))
    print()

    print("=== 4. 每道题明细: 各工程 × 题位 (平均正确率/平均回合) ===")
    order = ["未知API", "工程修复", "CLI工具", "照样板办事", "营地物资统计"]
    known = {p for m in data for p in data[m]}
    projs = [p for p in order if p in known] + sorted(known - set(order))
    CW = 25
    for pname in projs:
        print(f"── {pname} ──")
        print(pad("模型", WN) + "".join(pad(h, CW) for h in ["题1", "题2", "题3"]))
        p_agg = defaultdict(lambda: {"ok": [], "turns": [], "turns_ok": []})
        for m in sorted(data):
            st = stats(data[m].get(pname, EMPTY))
            cells = [f"{rate:5.1f}% {int(round(rate * n / 100))}/{n} ({t_all:4.1f}turns)" if n else "—"
                     for (n, rate, t_all, _) in st]
            print(pad(m, WN) + "".join(pad(c, CW) for c in cells))
            qs = data[m].get(pname)
            if qs:
                for q in (1, 2, 3):
                    for k in p_agg[q]:
                        p_agg[q][k] += qs[q][k]
        st = stats(p_agg)
        cells = [f"{rate:5.1f}% {int(round(rate * n / 100))}/{n} ({t_all:4.1f}turns)" if n else "—"
                 for (n, rate, t_all, _) in st]
        print(pad("合计", WN) + "".join(pad(c, CW) for c in cells))
        print()

    if skipped:
        print(f"已跳过评测进行中的执行目录: {', '.join(sorted(skipped))}")
    print(f"注: 每个题位 = 5 个工程 × 执行次数次尝试 (已排除: {'、'.join(sorted(EXCLUDE))}); turns 均值含失败任务(失败往往 turns 更少, 会拉低均值);")
    print("    缩减为负值表示题2/题3 反而用了更多回合。")


if __name__ == "__main__":
    main()
