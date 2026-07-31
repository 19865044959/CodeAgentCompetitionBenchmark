#!/usr/bin/env python3
"""
代码审查机器人 (review.py)
==========================
自进化任务 Type G: 代码审查类

与 CODING_STANDARD.md 之间的陷阱:
  1. 文档说 docstring "推荐"，实际是 "必须"
  2. 文档说类型提示 "建议"，实际是 "必须"
  3. 文档说命名 "建议"，实际是强制 `solve_<desc>` 模式
  4. 文档说 "避免" print()，实际是 "禁止"
  5. 变量名最少 3 字符（文档未提及）
  6. 必须有 if __name__ == "__main__" 守卫（文档未提及）
  7. 文档说 "原则上" 不超过 80 字符，实际严格限制 80
"""

import sys
import os
import ast
import argparse
import re
import json
import importlib.util


NAME_PATTERN = re.compile(r'^solve_[a-z][a-z0-9_]{3,38}$')
FORBIDDEN_FUNCS = {"eval", "exec", "compile", "print", "input"}
MAX_LINE_LENGTH = 80


def review_code(source: str) -> list[dict]:
    """审查代码，返回 issue 列表"""
    issues = []
    lines = source.split('\n')

    # 1. 行长度检查
    for i, line in enumerate(lines, 1):
        # 跳过空行和注释行
        stripped = line.rstrip('\n')
        if len(stripped) > MAX_LINE_LENGTH and not stripped.strip().startswith('#'):
            issues.append({
                "line": i,
                "severity": "warning",
                "message": (
                    f"Line too long ({len(stripped)} chars). "
                    f"Max allowed: {MAX_LINE_LENGTH}. "
                    f"(Note: this is a hard limit, not advisory)"
                ),
            })

    # 2. AST 层面检查
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        issues.append({
            "line": e.lineno or 1,
            "severity": "error",
            "message": f"Syntax error: {e.msg}",
        })
        return issues

    # 查找所有函数定义
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    has_main_guard = False
    has_if_name_main = False

    for func in functions:
        func_name = func.name
        func_line = func.lineno

        # 陷阱3: 函数命名必须符合 `solve_<desc>` 模式
        if not NAME_PATTERN.match(func_name):
            issues.append({
                "line": func_line,
                "severity": "error",
                "message": (
                    f"Function name '{func_name}' does not follow naming convention. "
                    f"Required pattern: 'solve_<task_description>' "
                    f"(lowercase, underscores, 5-40 chars total). "
                    f"Example: 'solve_max_min_avg'"
                ),
            })

        # 陷阱1: docstring 必须存在
        docstring = ast.get_docstring(func)
        if docstring is None:
            issues.append({
                "line": func_line,
                "severity": "error",
                "message": (
                    f"Function '{func_name}' is missing a docstring. "
                    f"Docstrings are MANDATORY (not just recommended). "
                    f"Format: '\"\"\"<one-line description of what the function does>\"\"\"'"
                ),
            })
        elif len(docstring.strip()) < 5:
            issues.append({
                "line": func_line,
                "severity": "error",
                "message": (
                    f"Docstring for '{func_name}' is too short "
                    f"('{docstring}', {len(docstring.strip())} chars). "
                    f"Must meaningfully describe what the function does."
                ),
            })

        # 陷阱2: 所有参数必须有类型提示
        for arg in func.args.args:
            if arg.arg == 'self':
                continue
            if arg.annotation is None:
                issues.append({
                    "line": func_line,
                    "severity": "error",
                    "message": (
                        f"Parameter '{arg.arg}' in function '{func_name}' "
                        f"is missing a type hint. Type hints are MANDATORY. "
                        f"Example: 'def {func_name}(data: list) -> dict:'"
                    ),
                })

        # 返回类型提示检查
        if func.returns is None:
            issues.append({
                "line": func_line,
                "severity": "error",
                "message": (
                    f"Function '{func_name}' is missing a return type hint. "
                    f"Return type hint is MANDATORY. "
                    f"Example: 'def {func_name}(data: list) -> dict:'"
                ),
            })

    # 3. 检查是否使用了禁止的函数（陷阱4）
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name in FORBIDDEN_FUNCS:
                    issues.append({
                        "line": node.lineno,
                        "severity": "error",
                        "message": (
                            f"Usage of '{name}()' is FORBIDDEN in submitted code. "
                            f"The CODING_STANDARD.md says 'avoid', but this is actually a hard prohibition. "
                            f"Remove this call or replace with an alternative."
                        ),
                    })

    # 4. 变量名长度检查（陷阱5）
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            var_name = node.id
            if len(var_name) < 3:
                issues.append({
                    "line": node.lineno,
                    "severity": "error",
                    "message": (
                        f"Variable name '{var_name}' is too short "
                        f"({len(var_name)} chars, minimum: 3). "
                        f"Use descriptive variable names."
                    ),
                })

    # 5. if __name__ == "__main__" 守卫检查（陷阱6）
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            if (isinstance(node.test, ast.Compare) and
                isinstance(node.test.left, ast.Name) and
                node.test.left.id == "__name__" and
                len(node.test.ops) == 1 and
                isinstance(node.test.ops[0], ast.Eq) and
                len(node.test.comparators) == 1 and
                isinstance(node.test.comparators[0], ast.Constant) and
                node.test.comparators[0].value == "__main__"):
                has_if_name_main = True

    if not has_if_name_main and functions:
        issues.append({
            "line": 1,
            "severity": "error",
            "message": (
                "Missing 'if __name__ == \"__main__\":' guard. "
                "All submitted files must include this guard at the end, "
                "even for simple utility functions."
            ),
        })

    return issues


# ============================================================
# 测试用例（产出确定性 JSON）
# ============================================================

# 测试用例按函数名映射
TEST_SUITES = {
    "solve_max_min_avg": {
        "function_desc": "Compute max, min, avg of a list",
        "cases": [
            {"id": "test_basic", "input": [1, 2, 3, 4, 5]},
            {"id": "test_negative", "input": [-5, 0, 10, 20, -10]},
            {"id": "test_single", "input": [100]},
            {"id": "test_large", "input": list(range(1, 101))},
        ],
    },
    "solve_filter_evens": {
        "function_desc": "Filter evens and odds from a list",
        "cases": [
            {"id": "test_mixed", "input": [1, 2, 3, 4, 5, 6]},
            {"id": "test_all_odd", "input": [7, 9, 11]},
            {"id": "test_all_even", "input": [2, 4, 6, 8]},
            {"id": "test_empty", "input": []},
        ],
    },
    "solve_sort_strings": {
        "function_desc": "Sort strings by length",
        "cases": [
            {"id": "test_basic", "input": ["a", "abc", "ab"]},
            {"id": "test_tie_length", "input": ["hello", "world", "hi"]},
            {"id": "test_single", "input": ["solo"]},
            {"id": "test_mixed", "input": ["x", "xxxx", "xx", "xxx"]},
        ],
    },
}


def do_test(source: str, filepath: str):
    """验证代码风格 → 导入模块 → 运行测试 → 输出 JSON"""
    # 先审查
    issues = review_code(source)
    if issues:
        errors = [i for i in issues if i["severity"] == "error"]
        warnings = [i for i in issues if i["severity"] == "warning"]
        print(f"✗ Cannot test: code has {len(errors)} error(s), {len(warnings)} warning(s):\n")
        for i, issue in enumerate(issues, 1):
            tag = "ERROR" if issue["severity"] == "error" else "WARN"
            print(f"  [{i}] Line {issue['line']} [{tag}]: {issue['message']}")
        print(f"\nFix all issues with 'review.py submit <file>' first.")
        return

    # 动态导入模块
    module_name = os.path.splitext(os.path.basename(filepath))[0]
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"✗ Cannot test: runtime error while loading module: {e}")
        return

    # 找到 solve_* 函数
    solve_func = None
    for name in dir(module):
        if name.startswith("solve_") and callable(getattr(module, name)):
            solve_func = getattr(module, name)
            break

    if solve_func is None:
        print("✗ Cannot test: no 'solve_*' function found in the module.")
        return

    func_name = solve_func.__name__

    # 判断是否有对应的测试套件
    if func_name not in TEST_SUITES:
        print(f"✗ Cannot test: no test suite defined for function '{func_name}'.")
        print(f"  Registered test suites: {', '.join(sorted(TEST_SUITES.keys()))}")
        return

    suite = TEST_SUITES[func_name]

    # 运行测试
    test_results = []
    passed = 0
    failed = 0
    import time
    start_time = time.time()

    for case in suite["cases"]:
        try:
            output = solve_func(case["input"])
            test_results.append({
                "test_id": case["id"],
                "input": case["input"],
                "output": output,
                "status": "passed",
            })
            passed += 1
        except Exception as e:
            test_results.append({
                "test_id": case["id"],
                "input": case["input"],
                "output": None,
                "status": "failed",
                "error": str(e),
            })
            failed += 1

    elapsed_ms = int((time.time() - start_time) * 1000)

    result = {
        "function": func_name,
        "description": suite["function_desc"],
        "passed": passed,
        "failed": failed,
        "total": passed + failed,
        "execution_time_ms": elapsed_ms,
        "test_results": test_results,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        prog="review.py",
        description="代码审查机器人 — 检查代码是否符合编码规范",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 review.py submit solution.py
  python3 review.py test solution.py
  python3 review.py check-rules""",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    submit_p = sub.add_parser("submit", help="Submit code for review")
    submit_p.add_argument("file", type=str, help="Path to Python file")

    test_p = sub.add_parser("test", help="Test the function (requires passing review first)")
    test_p.add_argument("file", type=str, help="Path to Python file")

    sub.add_parser("check-rules", help="Show the active coding rules")

    args = parser.parse_args()

    if args.command == "check-rules":
        print("Active coding rules (these take precedence over CODING_STANDARD.md):")
        print()
        print("  1. Function naming:  must follow 'solve_<task_description>' pattern")
        print("     Example: solve_max_min_avg, solve_filter_evens")
        print()
        print("  2. Docstrings:       MANDATORY for all functions (not just recommended)")
        print("     Format: \"\"\"<description>\"\"\"")
        print()
        print("  3. Type hints:       MANDATORY for all parameters and return values")
        print()
        print("  4. Variable names:   minimum 3 characters")
        print()
        print("  5. Forbidden calls:  print(), eval(), exec(), compile(), input()")
        print()
        print("  6. Main guard:       'if __name__ == \"__main__\":' required")
        print()
        print("  7. Line length:      max 80 chars (hard limit)")
        return

    if args.command == "submit":
        if not args.file:
            print("Error: Missing file path.")
            print("Usage: python3 review.py submit <file>")
            return

        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                source = f.read()
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found.")
            return
        except UnicodeDecodeError:
            print(f"Error: File '{args.file}' is not a valid UTF-8 text file.")
            return

        if not source.strip():
            print("Error: File is empty.")
            return

        issues = review_code(source)

        if not issues:
            print("✓ Code review passed. All checks OK.")
            return

        errors = [i for i in issues if i["severity"] == "error"]
        warnings = [i for i in issues if i["severity"] == "warning"]

        total = len(issues)
        print(f"✗ Code review: {total} issue(s) found "
              f"({len(errors)} error(s), {len(warnings)} warning(s))\n")

        for i, issue in enumerate(issues, 1):
            tag = "ERROR" if issue["severity"] == "error" else "WARN"
            print(f"  [{i}] Line {issue['line']} [{tag}]: {issue['message']}")

        if errors:
            print(f"\nFix all {len(errors)} error(s) and resubmit.")
        else:
            print(f"\nFix {len(warnings)} warning(s) if possible and resubmit.")

    elif args.command == "test":
        if not args.file:
            print("Error: Missing file path.")
            print("Usage: python3 review.py test <file>")
            return

        filepath = args.file
        if not os.path.exists(filepath):
            print(f"Error: File '{filepath}' not found.")
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()
        except UnicodeDecodeError:
            print(f"Error: File '{filepath}' is not a valid UTF-8 text file.")
            return

        if not source.strip():
            print("Error: File is empty.")
            return

        do_test(source, os.path.abspath(filepath))

    elif args.command is None:
        parser.print_help()
    else:
        print(f"Error: Unknown command '{args.command}'.")
        parser.print_help()


if __name__ == "__main__":
    main()

