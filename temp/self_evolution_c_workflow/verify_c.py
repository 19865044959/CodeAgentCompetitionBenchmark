#!/usr/bin/env python3
"""应急通信流程记录判题器。"""

from __future__ import annotations

import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
STEPS = ["power", "seed", "tune", "auth", "transmit", "log"]
MODEL_SPECS = {
    "R-700": {"voltage": Decimal("12.0"), "factor": Decimal("0.5"), "offset": Decimal("121")},
    "T-50": {"voltage": Decimal("9.0"), "factor": Decimal("0.25"), "offset": Decimal("118")},
}


def exact_keys(value: Any, keys: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == keys


def load_runtime(number: int) -> dict[str, Any]:
    return json.loads((ROOT / f"runtime_c{number}.json").read_text(encoding="utf-8"))


def freq_literal(raw: str) -> str | None:
    """只接受形如 168.0 的 JSON 数值原文，不接受 168、168.00 或字符串。"""
    matches = re.findall(r'"freq"\s*:\s*(-?\d+\.\d)(?=\s*[,}])', raw)
    return matches[0] if len(matches) == 1 else None


def verify(number: int, submission_dir: Path) -> tuple[bool, str]:
    answer_path = submission_dir / f"answer_c{number}.json"
    if not answer_path.is_file():
        return False, f"C-{number}: E_MISSING"

    try:
        raw = answer_path.read_text(encoding="utf-8")
        answer = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, f"C-{number}: E_JSON"

    runtime = load_runtime(number)
    if not exact_keys(answer, {"task", "execution"}):
        return False, f"C-{number}: E_SCHEMA"
    if answer["task"] != runtime["task"] or not isinstance(answer["execution"], list):
        return False, f"C-{number}: E_SCHEMA"

    execution = answer["execution"]
    if len(execution) != len(STEPS):
        return False, f"C-{number}: E_SEQUENCE position={min(len(execution), len(STEPS)) + 1}"
    for position, (entry, expected_step) in enumerate(zip(execution, STEPS), 1):
        if not isinstance(entry, dict) or entry.get("step") != expected_step:
            return False, f"C-{number}: E_SEQUENCE position={position}"

    model = runtime["model"]
    spec = MODEL_SPECS[model]

    power = execution[0]
    if not exact_keys(power, {"step", "request"}) or not exact_keys(power["request"], {"model", "voltage"}):
        return False, f"C-{number}: E_POWER"
    voltage = power["request"]["voltage"]
    if isinstance(voltage, bool) or not isinstance(voltage, (int, float)):
        return False, f"C-{number}: E_POWER"
    if power["request"]["model"] != model or Decimal(str(voltage)) != spec["voltage"]:
        return False, f"C-{number}: E_POWER"

    seed = execution[1]
    if not exact_keys(seed, {"step", "response"}) or not exact_keys(seed["response"], {"freq_seed"}):
        return False, f"C-{number}: E_SEED"
    seed_value = seed["response"]["freq_seed"]
    if isinstance(seed_value, bool) or not isinstance(seed_value, int) or seed_value != runtime["freq_seed"]:
        return False, f"C-{number}: E_SEED"

    tune = execution[2]
    if not exact_keys(tune, {"step", "request"}) or not exact_keys(tune["request"], {"freq"}):
        return False, f"C-{number}: E_FREQUENCY"
    freq_value = tune["request"]["freq"]
    if isinstance(freq_value, bool) or not isinstance(freq_value, (int, float)):
        return False, f"C-{number}: E_FREQUENCY"
    literal = freq_literal(raw)
    if literal is None:
        return False, f"C-{number}: E_PRECISION"
    try:
        submitted_freq = Decimal(literal)
    except InvalidOperation:
        return False, f"C-{number}: E_FREQUENCY"
    expected_freq = Decimal(runtime["freq_seed"]) * spec["factor"] + spec["offset"]
    if submitted_freq != expected_freq or Decimal(str(freq_value)) != expected_freq:
        return False, f"C-{number}: E_FREQUENCY"

    auth = execution[3]
    if not exact_keys(auth, {"step", "response"}) or not exact_keys(auth["response"], {"code"}):
        return False, f"C-{number}: E_AUTH"
    if auth["response"]["code"] != runtime["auth_code"]:
        return False, f"C-{number}: E_AUTH"

    transmit = execution[4]
    if not exact_keys(transmit, {"step", "request", "response"}):
        return False, f"C-{number}: E_TRANSMIT"
    if not exact_keys(transmit["request"], {"code", "coord"}) or not exact_keys(transmit["response"], {"ack"}):
        return False, f"C-{number}: E_TRANSMIT"
    if transmit["request"] != {"code": runtime["auth_code"], "coord": runtime["coordinate"]}:
        return False, f"C-{number}: E_TRANSMIT"
    if transmit["response"]["ack"] != runtime["ack"]:
        return False, f"C-{number}: E_TRANSMIT"

    log = execution[5]
    if not exact_keys(log, {"step", "request", "response"}):
        return False, f"C-{number}: E_LOG"
    if not exact_keys(log["request"], {"ack"}) or not exact_keys(log["response"], {"done_code"}):
        return False, f"C-{number}: E_LOG"
    if log["request"]["ack"] != runtime["ack"] or log["response"]["done_code"] != runtime["done_code"]:
        return False, f"C-{number}: E_LOG"

    return True, f"C-{number}: OK"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=int, choices=range(1, 4))
    parser.add_argument("--submission-dir", type=Path, default=Path("."))
    args = parser.parse_args()

    numbers = [args.task] if args.task else [1, 2, 3]
    results = [verify(number, args.submission_dir) for number in numbers]
    for _, message in results:
        print(message)
    raise SystemExit(0 if all(ok for ok, _ in results) else 1)


if __name__ == "__main__":
    main()
