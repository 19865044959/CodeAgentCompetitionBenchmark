#!/usr/bin/env python3
"""
推理类 Benchmark — 铁矿价格套利 验证器（灵活解析版）

用法:
  python3 verify.py <answer.json> [expected.json]
"""

import json
import os
import sys
import re
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize(s):
    """标准化字符串：去空白、去下划线、去连字符、转小写"""
    if not isinstance(s, str):
        return str(s)
    return re.sub(r'[\s_\-]+', '', s.lower())


def deep_find(obj, keys, max_depth=10):
    """在嵌套 JSON 中递归搜索 key，返回第一个匹配的值"""
    if max_depth <= 0:
        return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            nk = normalize(k)
            for target in keys:
                if normalize(target) in nk:
                    return v
        for v in obj.values():
            result = deep_find(v, keys, max_depth - 1)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = deep_find(item, keys, max_depth - 1)
            if result is not None:
                return result
    return None


def find_price_in_answer(answer_data, day_num):
    """从任意格式的答案中提取某天的预测价格"""
    # 先在 Q1 相关数据中搜索
    q1_data = None
    for q_key in ["q1", "question_1", "question1", "price_prediction", "q1_price", "Q1"]:
        q1_data = deep_find(answer_data, [q_key])
        if q1_data is not None:
            break

    if q1_data is None:
        q1_data = answer_data

    # 格式1: 数组 [2, 4, 4, 2]（按天索引）
    if isinstance(q1_data, list) and len(q1_data) >= day_num:
        try:
            return int(q1_data[day_num - 1])
        except (ValueError, TypeError):
            pass

    # 格式2: {"prices": [2, 4, 4, 2]} 或 {"data": [{"day": 1, "price": 2}, ...]}
    if isinstance(q1_data, dict):
        for arr_key in ["prices", "data", "values", "price_list"]:
            arr = q1_data.get(arr_key)
            if isinstance(arr, list):
                if len(arr) >= day_num:
                    val = arr[day_num - 1]
                    if isinstance(val, (int, float)):
                        return int(val)
                    if isinstance(val, dict):
                        for pk in ["price", "价格", "value"]:
                            if pk in val:
                                return int(val[pk])
                        # 取第一个数值
                        for v in val.values():
                            try:
                                return int(v)
                            except (ValueError, TypeError):
                                continue

    # 格式3: dict with day-labeled keys
    day_keys = [f"day{day_num}", f"day {day_num}", f"day_{day_num}",
                f"day{day_num}price", f"day{day_num}_price", f"第{day_num}天"]
    if isinstance(q1_data, dict):
        for dk in day_keys:
            val = deep_find(q1_data, [dk])
            if val is not None:
                if isinstance(val, dict):
                    for pk in ["price", "价格", "value"]:
                        if pk in val:
                            return int(val[pk])
                    for v in val.values():
                        try:
                            return int(v)
                        except (ValueError, TypeError):
                            continue
                try:
                    return int(val)
                except (ValueError, TypeError):
                    pass

    return None


def find_action_text(answer_data, question_key_patterns):
    """从任意格式的答案中提取行动描述文本"""
    text_parts = []

    def extract_text(obj, depth=0):
        if depth > 8:
            return
        if isinstance(obj, str):
            text_parts.append(obj)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                nk = normalize(k)
                if any(p in nk for p in ["action", "行动", "动作", "策略", "strategy", "做什么"]):
                    if isinstance(v, str):
                        text_parts.append(v)
                    elif isinstance(v, dict):
                        for vk, vv in v.items():
                            if isinstance(vv, str):
                                text_parts.append(vv)
                            elif isinstance(vv, (int, float)):
                                pass
                extract_text(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                extract_text(item, depth + 1)

    # 先定位到相关 question
    q_data = answer_data
    for pattern in question_key_patterns:
        result = deep_find(answer_data, [pattern])
        if result is not None:
            q_data = result
            break

    extract_text(q_data)
    return " ".join(text_parts)


def find_numeric_value(answer_data, key_patterns):
    """从答案中提取数值"""
    val = deep_find(answer_data, key_patterns)
    if val is None:
        return None
    try:
        if isinstance(val, str):
            # 尝试提取数字
            m = re.search(r'(\d+)', val)
            if m:
                return int(m.group(1))
        return int(val)
    except (ValueError, TypeError):
        return None


def verify_q1(answer_data):
    """Q1: 价格预测"""
    expected = {1: 2, 2: 4, 3: 4, 4: 2}
    score, details = 0, []

    for day, exp_price in expected.items():
        actual = find_price_in_answer(answer_data, day)
        if actual is not None and actual == exp_price:
            weight = 7 if day in [2, 3] else 5
            score += weight
            details.append({"day": day, "status": "PASS", "expected": exp_price, "actual": actual})
        elif actual is not None:
            details.append({"day": day, "status": "FAIL", "expected": exp_price, "actual": actual})
        else:
            details.append({"day": day, "status": "NOT_FOUND", "expected": exp_price})

    # Partial credit for gradual model (day2=3, day3=4 is reasonable)
    if score < 14:  # If not already passing well
        alt_score = 0
        for day, exp_price in expected.items():
            actual = find_price_in_answer(answer_data, day)
            if actual is not None:
                if day == 1 and actual == 2:
                    alt_score += 5
                elif day in [2, 3] and actual >= 3:  # At least higher than base
                    alt_score += 5
                elif day == 4 and actual <= 3:  # At least coming back down
                    alt_score += 3
        if alt_score > score:
            score = alt_score
            details.append({"note": "PARTIAL_CREDIT", "desc": "价格趋势方向正确（涨→跌）但幅度不完全准确"})

    return {"score": min(score, 25), "max_score": 25, "details": details}


def verify_q2(answer_data):
    """Q2: 囤积策略"""
    score, details = 0, []

    # 找到 Q2 数据
    q2_data = deep_find(answer_data, ["q2", "question_2", "question2", "day1_strategy", "hoarding"])
    if q2_data is None:
        q2_data = answer_data

    action_text = ""
    if isinstance(q2_data, dict):
        # 先找显式的 action/strategy 字段
        for ak in ["action", "strategy", "行动", "动作", "策略"]:
            if ak in q2_data:
                action_text += str(q2_data[ak]) + " "
        # 也找 reasoning/why 字段
        for rk in ["reasoning", "reason", "why", "原因", "理由"]:
            if rk in q2_data:
                action_text += str(q2_data[rk]) + " "
    if not action_text:
        action_text = json.dumps(q2_data, ensure_ascii=False)

    norm = normalize(action_text)

    # 核心检查：动作应该是采集
    hoard_hits = sum(1 for kw in ["采集", "collect", "囤", "攒", "挖", "采", "mine", "hoard", "全力", "抢采", "抢", "扫荡"] if kw in norm)
    # "sell"应该只在推理上下文中出现（等待高价出售），不是动作本身
    sell_in_action = False
    if isinstance(q2_data, dict):
        for ak in ["action", "strategy", "行动", "动作"]:
            if ak in q2_data:
                av = normalize(str(q2_data[ak]))
                if any(kw in av for kw in ["卖", "sell", "出售"]):
                    sell_in_action = True

    if hoard_hits >= 2 and not sell_in_action:
        score += 20
        details.append({"status": "PASS", "desc": f"正确：Day1应采集/囤积铁矿 (匹配{hoard_hits}个关键词)"})
    elif hoard_hits >= 1:
        score += 12
        details.append({"status": "PARTIAL", "desc": "提到采集但关键词匹配不够强"})
    else:
        details.append({"status": "FAIL", "desc": "未明确提到采集/囤积铁矿"})

    # 检查优先级
    priority_keywords = ["最高", "最优先", "high", "优先", "立即", "马上", "urgent"]
    if any(kw in norm for kw in priority_keywords):
        score += 5
        details.append({"status": "PASS", "desc": "正确识别为高优先级"})

    return {"score": min(score, 25), "max_score": 25, "details": details}


def verify_q3(answer_data):
    """Q3: 卖出策略"""
    score, details = 0, []

    q3_data = deep_find(answer_data, ["q3", "question_3", "question3", "subsequent", "followup", "follow_up"])
    if q3_data is None:
        q3_data = answer_data

    sell_keywords = ["卖", "sell", "出售", "抛售", "出"]
    collect_keywords = ["采集", "collect", "采", "mine"]

    # 格式1: 按天索引的数组 [{"day": 2, "action": "..."}, ...]
    if isinstance(q3_data, list):
        for item in q3_data:
            if isinstance(item, dict):
                day_label = str(item.get("day", ""))
                action = normalize(str(item.get("action", "")))
                # Day 2 or Day 3: should sell
                if "2" in day_label or "3" in day_label:
                    if any(kw in action for kw in sell_keywords):
                        score += 12
                        details.append({"status": "PASS", "desc": f"Day{day_label}: 正确卖出"})
                    elif any(kw in action for kw in collect_keywords):
                        details.append({"status": "FAIL", "desc": f"Day{day_label}: 不应采集（矿区停工）"})
                    else:
                        details.append({"status": "FAIL", "desc": f"Day{day_label}: 未卖出（{item.get('action', '')}）"})
                # Day 4: should resume normal
                if "4" in day_label:
                    if not any(kw in action for kw in sell_keywords):
                        score += 6
                        details.append({"status": "PASS", "desc": "Day4正确未大量卖出"})

    # 格式2: dict with Day keys {"Day 2": {...}, "Day 3": {...}, ...}
    elif isinstance(q3_data, dict):
        for dk, dv in q3_data.items():
            ndk = normalize(dk)
            if not isinstance(dv, dict):
                continue
            action = normalize(str(dv.get("action", "")))
            # Day 2-3 should sell
            if "day2" in ndk or "day 2" in ndk or "第二天" in ndk:
                if any(kw in action for kw in sell_keywords):
                    score += 12
                    details.append({"status": "PASS", "desc": f"Day2: 正确卖出"})
                else:
                    details.append({"status": "FAIL", "desc": f"Day2: 未卖出（{dv.get('action', '')}）"})
            if "day3" in ndk or "day 3" in ndk or "第三天" in ndk:
                if any(kw in action for kw in sell_keywords):
                    score += 12
                    details.append({"status": "PASS", "desc": f"Day3: 正确卖出"})
                else:
                    details.append({"status": "FAIL", "desc": f"Day3: 未卖出（{dv.get('action', '')}）"})
            if "day4" in ndk or "day 4" in ndk or "第四天" in ndk:
                if not any(kw in action for kw in sell_keywords):
                    score += 6
                    details.append({"status": "PASS", "desc": "Day4正确恢复正常"})

    return {"score": min(score, 30), "max_score": 30, "details": details}


def verify_q4(answer_data):
    """Q4: 利润分析"""
    score, details = 0, []

    all_text = json.dumps(answer_data, ensure_ascii=False)
    norm_all = normalize(all_text)

    # 利润应该约为2/单位 或 40/20单位
    profit_val = find_numeric_value(answer_data, ["extra_profit", "profit", "额外利润", "extra", "利润"])
    if profit_val is not None:
        if profit_val == 40:
            score += 10
            details.append({"status": "PASS", "desc": f"额外利润正确：{profit_val}"})
        elif profit_val >= 20:
            score += 6
            details.append({"status": "PARTIAL", "desc": f"额外利润接近正确：{profit_val}（预期40）"})
        else:
            details.append({"status": "FAIL", "desc": f"额外利润不正确：{profit_val}（预期40）"})
    else:
        # 检查是否提到了4和2的差价
        if "2金币" in norm_all or "2个金币" in norm_all or "差价2" in norm_all:
            score += 5
            details.append({"status": "PARTIAL", "desc": "提到了价差2金币"})

    # 策略描述
    strategy_keywords = ["囤", "collect", "涨价", "高价", "卖", "sell", "差价", "arbitrage"]
    strategy_hits = sum(1 for kw in strategy_keywords if kw in norm_all)
    if strategy_hits >= 4:
        score += 10
        details.append({"status": "PASS", "desc": "策略描述完整"})
    elif strategy_hits >= 2:
        score += 5
        details.append({"status": "PARTIAL", "desc": "策略描述基本完整"})
    else:
        details.append({"status": "FAIL", "desc": "策略描述不完整"})

    return {"score": min(score, 20), "max_score": 20, "details": details}


def verify(answer_path, expected_path=None):
    """主验证函数"""
    if not os.path.exists(answer_path):
        return {"success": False, "error": f"Answer file not found: {answer_path}"}

    answer_data = load_json(answer_path)

    # 加载阈值
    passing_threshold = 70
    if expected_path and os.path.exists(expected_path):
        try:
            expected_data = load_json(expected_path)
            passing_threshold = expected_data.get("passing_threshold", 70)
        except:
            pass

    q1 = verify_q1(answer_data)
    q2 = verify_q2(answer_data)
    q3 = verify_q3(answer_data)
    q4 = verify_q4(answer_data)

    total = q1["score"] + q2["score"] + q3["score"] + q4["score"]
    max_score = 100
    pct = round(total / max_score * 100, 1)
    passed = pct >= passing_threshold

    diagnostics = []
    if not passed:
        if q1["score"] < 15:
            diagnostics.append("Q1 价格预测：GA未能正确识别停工导致的价格变化时间线")
        if q2["score"] < 15:
            diagnostics.append("Q2 囤积策略：GA未意识到应在涨价前囤积铁矿")
        if q3["score"] < 18:
            diagnostics.append("Q3 卖出策略：GA未能在正确的高价窗口卖出铁矿")
        if q4["score"] < 10:
            diagnostics.append("Q4 利润分析：GA未能正确计算套利利润")

    return {
        "task_id": "reasoning_iron_price",
        "success": passed,
        "total_score": total,
        "max_score": max_score,
        "percentage": pct,
        "passing_threshold": passing_threshold,
        "questions": {
            "q1_price_prediction": q1,
            "q2_hoarding_strategy": q2,
            "q3_selling_strategy": q3,
            "q4_profit_analysis": q4,
        },
        "diagnostics": diagnostics,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 verify.py <answer.json> [expected.json]")
        sys.exit(1)
    answer_path = sys.argv[1]
    expected_path = sys.argv[2] if len(sys.argv) > 2 else None
    report = verify(answer_path, expected_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("success"):
        print(f"\n✅ PASS ({report['percentage']}%)")
    else:
        print(f"\n❌ FAIL ({report['percentage']}% < {report['passing_threshold']}%)")
        for d in report.get("diagnostics", []):
            print(f"  ⚠ {d}")


if __name__ == "__main__":
    main()
