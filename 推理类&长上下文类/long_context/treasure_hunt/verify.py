#!/usr/bin/env python3
"""
长上下文类 Benchmark — 民间传闻拼图寻宝 验证器

验证 GA 是否具备以下长上下文能力：
  1. 从7天混杂传闻中识别有效线索 vs 噪声
  2. 跨天串联信息（代号→外貌→封印→凹槽 四重映射）
  3. 从隐晦表达推导坐标位置
  4. 知道购买物品后使用 detect 指令激活祭坛

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


def normalize_str(s):
    """标准化字符串"""
    if not isinstance(s, str):
        return str(s)
    return re.sub(r'\s+', '', s.lower())


def verify_q1_signal_detection(answer):
    """验证 Q1: 信号识别"""
    result = {"score": 0, "max_score": 15, "details": []}

    expected_valid = {1, 3, 5, 7}
    expected_noise = {2, 4, 6}

    # 检查 valid_days
    if "valid_days" in answer:
        actual_valid = set(answer["valid_days"]) if isinstance(answer["valid_days"], list) else set()
        if actual_valid == expected_valid:
            result["score"] += 7
            result["details"].append({"field": "valid_days", "status": "PASS", "expected": list(expected_valid), "actual": list(actual_valid)})
        elif actual_valid.issuperset(expected_valid):
            result["score"] += 4
            result["details"].append({"field": "valid_days", "status": "PARTIAL", "desc": "包含了正确天数但也多选了", "expected": list(expected_valid), "actual": list(actual_valid)})
        elif len(actual_valid & expected_valid) >= 3:
            result["score"] += 4
            result["details"].append({"field": "valid_days", "status": "PARTIAL", "desc": "大部分正确但有遗漏", "expected": list(expected_valid), "actual": list(actual_valid)})
        else:
            result["details"].append({"field": "valid_days", "status": "FAIL", "expected": list(expected_valid), "actual": list(actual_valid)})
    else:
        result["details"].append({"field": "valid_days", "status": "MISSING"})

    # 检查 noise_days
    if "noise_days" in answer:
        actual_noise = set(answer["noise_days"]) if isinstance(answer["noise_days"], list) else set()
        if actual_noise == expected_noise:
            result["score"] += 5
            result["details"].append({"field": "noise_days", "status": "PASS", "expected": list(expected_noise), "actual": list(actual_noise)})
        elif len(actual_noise & expected_noise) >= 2:
            result["score"] += 2
            result["details"].append({"field": "noise_days", "status": "PARTIAL", "desc": "大部分噪声识别正确", "expected": list(expected_noise), "actual": list(actual_noise)})
        else:
            result["details"].append({"field": "noise_days", "status": "FAIL", "expected": list(expected_noise), "actual": list(actual_noise)})
    else:
        result["details"].append({"field": "noise_days", "status": "MISSING"})

    # 检查推理质量
    if "reasoning" in answer:
        reasoning = normalize_str(str(answer["reasoning"]))
        quality_keywords = ["噪声", "有效", "线索", "无关", "识别", "筛选"]
        if any(kw in reasoning for kw in quality_keywords):
            result["score"] += 3
            result["details"].append({"field": "reasoning", "status": "PASS"})
        else:
            result["score"] += 1
            result["details"].append({"field": "reasoning", "status": "BASIC"})

    return result


def check_item_mapping(item, item_idx):
    """检查单个物品的映射"""
    expected_mappings = {
        1: {
            "day1_code_name": ["言者石"],
            "day3_appearance": ["灰白", "石板", "刻字"],
            "day5_seal_name": ["真言之印", "铭文石板"],
            "day7_slot_shape": ["方槽", "方形", "方正"],
            "weapon_shop_item": ["古符石板"],
            "price": 15
        },
        2: {
            "day1_code_name": ["光之尘"],
            "day3_appearance": ["银白", "粉末", "发光"],
            "day5_seal_name": ["明光之印", "不灭之光"],
            "day7_slot_shape": ["圆碟", "圆形", "碟状"],
            "weapon_shop_item": ["星辰之沙"],
            "price": 20
        },
        3: {
            "day1_code_name": ["焚之心"],
            "day3_appearance": ["水晶", "橙红", "雾", "瓶子"],
            "day5_seal_name": ["焚天之印", "纯净之火"],
            "day7_slot_shape": ["小孔", "焦痕", "烧焦"],
            "weapon_shop_item": ["烈焰之息"],
            "price": 25
        }
    }

    exp = expected_mappings[item_idx]
    score = 0
    details = []

    # 检查 weapon_shop_item（最重要）
    if "weapon_shop_item" in item:
        item_name = normalize_str(str(item["weapon_shop_item"]))
        if any(normalize_str(e) in item_name or item_name in normalize_str(e) for e in exp["weapon_shop_item"]):
            score += 4
            details.append({"field": f"item_{item_idx}.weapon_shop_item", "status": "PASS", "actual": item["weapon_shop_item"]})
        else:
            details.append({"field": f"item_{item_idx}.weapon_shop_item", "status": "FAIL", "expected": exp["weapon_shop_item"][0], "actual": item.get("weapon_shop_item")})

    # 检查价格
    if "price" in item:
        try:
            if int(item["price"]) == exp["price"]:
                score += 2
                details.append({"field": f"item_{item_idx}.price", "status": "PASS", "actual": item["price"]})
            else:
                details.append({"field": f"item_{item_idx}.price", "status": "FAIL", "expected": exp["price"], "actual": item["price"]})
        except (ValueError, TypeError):
            details.append({"field": f"item_{item_idx}.price", "status": "PARSE_ERROR"})

    # 检查各天映射（较宽松——检查关键词是否出现）
    mapping_fields = [
        ("day1_code_name", exp["day1_code_name"]),
        ("day3_appearance", exp["day3_appearance"]),
        ("day5_seal_name", exp["day5_seal_name"]),
        ("day7_slot_shape", exp["day7_slot_shape"]),
    ]

    for field, keywords in mapping_fields:
        if field in item:
            text = normalize_str(str(item[field]))
            matched = sum(1 for kw in keywords if normalize_str(kw) in text)
            if matched >= 1:
                score += 1
                details.append({"field": f"item_{item_idx}.{field}", "status": "PASS", "actual": item[field][:80]})
            else:
                details.append({"field": f"item_{item_idx}.{field}", "status": "FAIL", "expected": keywords, "actual": item.get(field, "")[:80]})

    return score, details


def verify_q2_item_identification(answer):
    """验证 Q2: 物品映射"""
    result = {"score": 0, "max_score": 35, "details": []}

    for i in range(1, 4):
        item_key = f"item_{i}"
        if item_key in answer:
            item_score, item_details = check_item_mapping(answer[item_key], i)
            result["score"] += item_score
            result["details"].extend(item_details)
        else:
            result["details"].append({"field": f"item_{i}", "status": "MISSING", "desc": f"缺少第{i}个物品的映射"})

    # 检查推理
    if "reasoning" in answer:
        reasoning = normalize_str(str(answer["reasoning"]))
        cross_day_keywords = ["交叉", "四重", "代号", "外貌", "封印", "凹槽", "验证", "映射", "串联"]
        if sum(1 for kw in cross_day_keywords if kw in reasoning) >= 3:
            result["score"] += 3
            result["details"].append({"field": "reasoning", "status": "PASS", "desc": "推理包含跨天串联逻辑"})
        elif sum(1 for kw in cross_day_keywords if kw in reasoning) >= 1:
            result["score"] += 1
            result["details"].append({"field": "reasoning", "status": "PARTIAL"})

    return result


def verify_q3_location(answer):
    """验证 Q3: 位置推理"""
    result = {"score": 0, "max_score": 20, "details": []}

    # 检查坐标
    if "target_x" in answer:
        try:
            if int(answer["target_x"]) == 3:
                result["score"] += 8
                result["details"].append({"field": "target_x", "status": "PASS", "expected": 3, "actual": answer["target_x"]})
            else:
                result["details"].append({"field": "target_x", "status": "FAIL", "expected": 3, "actual": answer["target_x"]})
        except (ValueError, TypeError):
            result["details"].append({"field": "target_x", "status": "PARSE_ERROR"})

    if "target_y" in answer:
        try:
            if int(answer["target_y"]) == 3:
                result["score"] += 8
                result["details"].append({"field": "target_y", "status": "PASS", "expected": 3, "actual": answer["target_y"]})
            else:
                result["details"].append({"field": "target_y", "status": "FAIL", "expected": 3, "actual": answer["target_y"]})
        except (ValueError, TypeError):
            result["details"].append({"field": "target_y", "status": "PARSE_ERROR"})

    # 检查推理中是否引用了两天线索
    if "reasoning" in answer:
        reasoning = normalize_str(str(answer["reasoning"]))
        day1_ref = any(kw in reasoning for kw in ["day1", "day 1", "采药人", "西部", "石门"])
        day7_ref = any(kw in reasoning for kw in ["day7", "day 7", "猎人", "北三", "东三", "原点"])
        if day1_ref and day7_ref:
            result["score"] += 4
            result["details"].append({"field": "reasoning", "status": "PASS", "desc": "使用 Day1 + Day7 双重确认位置"})
        elif day7_ref:
            result["score"] += 2
            result["details"].append({"field": "reasoning", "status": "PARTIAL", "desc": "仅引用了 Day7 的精确坐标"})

    return result


def verify_q4_action_plan(answer):
    """验证 Q4: 行动计划"""
    result = {"score": 0, "max_score": 30, "details": []}

    # 检查物品列表
    if "required_items" in answer:
        items = [normalize_str(i) for i in answer["required_items"]]
        expected_items = {"古符石板", "星辰之沙", "烈焰之息"}
        found = set()
        for item in items:
            for exp in expected_items:
                if normalize_str(exp) in item:
                    found.add(exp)
        if found == expected_items:
            result["score"] += 10
            result["details"].append({"field": "required_items", "status": "PASS", "actual": answer["required_items"]})
        elif len(found) >= 2:
            result["score"] += 5
            result["details"].append({"field": "required_items", "status": "PARTIAL", "missing": list(expected_items - found)})
        else:
            result["details"].append({"field": "required_items", "status": "FAIL", "expected": list(expected_items), "actual": answer["required_items"]})

    # 检查总金币
    if "total_gold_needed" in answer:
        try:
            if int(answer["total_gold_needed"]) == 60:
                result["score"] += 5
                result["details"].append({"field": "total_gold_needed", "status": "PASS", "actual": answer["total_gold_needed"]})
            else:
                result["details"].append({"field": "total_gold_needed", "status": "FAIL", "expected": 60, "actual": answer["total_gold_needed"]})
        except (ValueError, TypeError):
            result["details"].append({"field": "total_gold_needed", "status": "PARSE_ERROR"})

    # 检查最终动作
    if "final_action" in answer:
        action = normalize_str(str(answer["final_action"]))
        if action == "detect":
            result["score"] += 10
            result["details"].append({"field": "final_action", "status": "PASS", "actual": "detect"})
        elif "detect" in action:
            result["score"] += 5
            result["details"].append({"field": "final_action", "status": "PARTIAL", "actual": answer["final_action"]})
        else:
            result["details"].append({"field": "final_action", "status": "FAIL", "expected": "detect", "actual": answer["final_action"]})

    # 检查使用开拓者
    if "required_role" in answer:
        role = normalize_str(str(answer["required_role"]))
        if role == "pioneer" or "开拓者" in role:
            result["score"] += 5
            result["details"].append({"field": "required_role", "status": "PASS", "actual": answer["required_role"]})
        else:
            result["details"].append({"field": "required_role", "status": "FAIL", "expected": "pioneer", "actual": answer["required_role"]})

    # 检查 action_sequence
    if "action_sequence" in answer:
        seq = answer["action_sequence"]
        if isinstance(seq, list) and len(seq) > 0:
            seq_text = normalize_str(" ".join(str(s) for s in seq))
            # 检查关键步骤
            has_buy = any(kw in seq_text for kw in ["buy", "购买", "买"])
            has_move_to_store = any(kw in seq_text for kw in ["武器商店", "weaponstore", "(25,20)"])
            has_move_to_target = any(kw in seq_text for kw in ["(3,3)", "3,3"])
            has_detect = any(kw in seq_text for kw in ["detect", "探索", "探查"])

            checks = [has_buy, has_move_to_store, has_move_to_target, has_detect]
            result["score"] += sum(1 for c in checks if c)
            result["details"].append({
                "field": "action_sequence",
                "status": "PASS" if all(checks) else "PARTIAL",
                "checks": {"buy": has_buy, "move_to_store": has_move_to_store, "move_to_target": has_move_to_target, "detect": has_detect}
            })

    return result


def verify(answer_path, expected_path=None):
    """主验证函数"""
    if not os.path.exists(answer_path):
        return {"success": False, "error": f"Answer file not found: {answer_path}"}

    answer_data = load_json(answer_path)
    answers = answer_data.get("answers", answer_data)

    # 加载期望答案和通过阈值
    if expected_path and os.path.exists(expected_path):
        expected_data = load_json(expected_path)
        passing_threshold = expected_data.get("passing_threshold", 70)
    else:
        script_dir = Path(__file__).parent
        default_expected = script_dir / "ans" / "expected.json"
        if default_expected.exists():
            expected_data = load_json(str(default_expected))
            passing_threshold = expected_data.get("passing_threshold", 70)
        else:
            passing_threshold = 70

    # 逐题验证
    q1_result = verify_q1_signal_detection(answers.get("q1_signal_detection", {}))
    q2_result = verify_q2_item_identification(answers.get("q2_item_identification", {}))
    q3_result = verify_q3_location(answers.get("q3_location_deduction", {}))
    q4_result = verify_q4_action_plan(answers.get("q4_action_plan", {}))

    # 逐题封顶分数
    q1_result["score"] = min(q1_result["score"], q1_result["max_score"])
    q2_result["score"] = min(q2_result["score"], q2_result["max_score"])
    q3_result["score"] = min(q3_result["score"], q3_result["max_score"])
    q4_result["score"] = min(q4_result["score"], q4_result["max_score"])

    # 汇总
    total_score = q1_result["score"] + q2_result["score"] + q3_result["score"] + q4_result["score"]
    max_score = q1_result["max_score"] + q2_result["max_score"] + q3_result["max_score"] + q4_result["max_score"]
    percentage = round(total_score / max_score * 100, 1)
    passed = percentage >= passing_threshold

    # 诊断
    diagnostics = []
    if not passed:
        if q1_result["score"] < q1_result["max_score"] * 0.6:
            diagnostics.append("Q1 信号识别能力不足：GA 无法从混杂传闻中区分有效线索与噪声")
        if q2_result["score"] < q2_result["max_score"] * 0.6:
            diagnostics.append("Q2 物品映射能力不足：GA 无法完成代号→外貌→封印→凹槽→商品的四重映射")
        if q3_result["score"] < q3_result["max_score"] * 0.6:
            diagnostics.append("Q3 位置推理能力不足：GA 无法从 Day1 方向 + Day7 坐标推导出 (3,3)")
        if q4_result["score"] < q4_result["max_score"] * 0.6:
            diagnostics.append("Q4 行动计划能力不足：GA 不知道需要购买三样物品后使用 detect")

    report = {
        "task_id": "long_context_treasure_hunt",
        "success": passed,
        "total_score": total_score,
        "max_score": max_score,
        "percentage": percentage,
        "passing_threshold": passing_threshold,
        "questions": {
            "q1_signal_detection": q1_result,
            "q2_item_identification": q2_result,
            "q3_location_deduction": q3_result,
            "q4_action_plan": q4_result
        },
        "diagnostics": diagnostics
    }

    return report


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
