#!/usr/bin/env python3
"""D 类判题器：只比较最终 work/out_dN.csv。"""

from __future__ import annotations

import argparse
from pathlib import Path


EXPECTED_DIR = Path(__file__).resolve().parent / "expected"


def first_different_line(actual: bytes, expected: bytes) -> int:
    actual_lines = actual.splitlines(keepends=True)
    expected_lines = expected.splitlines(keepends=True)
    for index, (left, right) in enumerate(zip(actual_lines, expected_lines), 1):
        if left != right:
            return index
    if len(actual_lines) != len(expected_lines):
        return min(len(actual_lines), len(expected_lines)) + 1
    return max(1, len(expected_lines))


def verify(number: int, submission_dir: Path) -> tuple[bool, str]:
    actual_path = submission_dir / "work" / f"out_d{number}.csv"
    expected_path = EXPECTED_DIR / f"out_d{number}.csv"
    if not actual_path.is_file():
        return False, f"D-{number}: E_MISSING_OUTPUT"
    actual = actual_path.read_bytes()
    expected = expected_path.read_bytes()
    if actual != expected:
        return False, f"D-{number}: E_DIFF line={first_different_line(actual, expected)}"
    return True, f"D-{number}: OK"


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
