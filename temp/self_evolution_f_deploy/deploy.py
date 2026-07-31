#!/usr/bin/env python3
"""
部署配置验证器 (deploy.py)
==========================
自进化任务 Type F: 配置验证类

与 DEPLOY_GUIDE.md 之间的陷阱:
  1. 字段层级: 文档说 app_name 是顶层字段，实际在 app.name 嵌套下
  2. 字段名: 文档说 memory，实际用 mem
  3. 字段名: 文档说 database.type，实际是 db.kind
  4. 端口范围: 文档说 80-65535，实际 3000-9000
  5. 名字长度: 文档说 "任意字符串"，实际 3-20 字符
  6. mem 格式: 文档说 "数字+单位如512MB"，实际要用 "512M"（无B）
  7. db: 当 kind=sqlite 时，host 是可选的（互斥约束）
  8. 文档说 workers 默认 1，实际必填（Range(min=1)）
"""

import sys
import json
import argparse
import re


# ============================================================
# 验证逻辑
# ============================================================
MEM_RE = re.compile(r'^\d+[KMG]$')

def validate(yaml_like: dict):
    """验证配置，返回错误列表。每个错误为 (path, message)"""
    errors = []

    # --- app 段 ---
    # 陷阱1: 文档说是 app_name (顶层), 实际是 app.name (嵌套)
    # 这些检查必须在 app 存在性检查之前，否则 Agent 看不到具体提示
    if "app_name" in yaml_like:
        errors.append(("app_name",
            "Unknown top-level field 'app_name'. "
            "This field should be inside the 'app' section as 'name'. "
            "Example: app:\n  name: myapp"))

    # 陷阱1补充: 文档说 app_version 顶层, 实际 app.version
    if "app_version" in yaml_like:
        errors.append(("app_version",
            "Unknown top-level field 'app_version'. "
            "This field should be inside the 'app' section as 'version'."))

    app = yaml_like.get("app")
    if app is None:
        errors.append(("app", "required section 'app' is missing."))
        # 不 return，继续检查其他顶级错误
    elif not isinstance(app, dict):
        errors.append(("app", "must be a mapping/dictionary."))

    if app is None or not isinstance(app, dict):
        return errors  # 无法继续检查 app 内部字段

    name = app.get("name")
    if name is None:
        errors.append(("app.name", "required field is missing."))
    elif not isinstance(name, str):
        errors.append(("app.name", f"must be a string. Got: {type(name).__name__}"))
    elif len(name) < 3 or len(name) > 20:
        # 陷阱5: 文档说任意字符串，实际限制 3-20
        errors.append(("app.name",
            f"must be 3-20 characters. Got '{name}' ({len(name)} chars)."))

    version = app.get("version")
    if version is None:
        errors.append(("app.version", "required field is missing."))
    elif not isinstance(version, str):
        errors.append(("app.version", f"must be a string. Got: {type(version).__name__}"))

    env = app.get("env")
    valid_envs = {"dev", "staging", "production"}
    if env is None:
        errors.append(("app.env", "required field is missing."))
    elif env not in valid_envs:
        errors.append(("app.env",
            f"invalid value '{env}'. Must be one of: {', '.join(sorted(valid_envs))}"))

    # --- server 段 ---
    server = yaml_like.get("server")
    if server is None:
        errors.append(("server", "required section 'server' is missing."))
    elif not isinstance(server, dict):
        errors.append(("server", "must be a mapping/dictionary."))
    else:
        port = server.get("port")
        if port is None:
            errors.append(("server.port", "required field is missing."))
        elif not isinstance(port, int):
            errors.append(("server.port", f"must be an integer. Got: {type(port).__name__}"))
        elif port < 3000 or port > 9000:
            # 陷阱4: 文档说 80-65535, 实际 3000-9000
            errors.append(("server.port",
                f"must be between 3000 and 9000. Got: {port}. "
                f"(Note: port range is 3000-9000, not 80-65535 as some docs may suggest)"))

        workers = server.get("workers")
        if workers is None:
            # 文档说默认1，实际必填
            errors.append(("server.workers", "required field is missing."))
        elif not isinstance(workers, int):
            errors.append(("server.workers", f"must be an integer. Got: {type(workers).__name__}"))
        elif workers < 1 or workers > 16:
            errors.append(("server.workers", f"must be between 1 and 16. Got: {workers}"))

        mem = server.get("mem")
        # 陷阱2: 文档说 memory
        if "memory" in server:
            errors.append(("server.memory",
                "Unknown field 'memory'. Did you mean 'mem'? "
                "(Note: the correct field name is 'mem', format: '<number><unit>' "
                "e.g., '512M' or '2G', not '512MB')"))
        if mem is None:
            errors.append(("server.mem", "required field is missing."))
        elif not isinstance(mem, str):
            errors.append(("server.mem", f"must be a string. Got: {type(mem).__name__}"))
        elif not MEM_RE.match(mem):
            # 陷阱6: 格式 512M 不是 512MB
            errors.append(("server.mem",
                f"invalid format '{mem}'. Expected: '<number><unit>' "
                f"where unit is K, M, or G. Examples: '512M', '2G', '256K'. "
                f"(Note: unit should be a single letter, e.g., 'M' not 'MB')"))

    # --- db 段 (陷阱3: 文档说 database, 实际是 db) ---
    if "database" in yaml_like:
        errors.append(("database",
            "Unknown section 'database'. Did you mean 'db'? "
            "(Note: the correct section name is 'db', not 'database')"))

    db = yaml_like.get("db")
    if db is None:
        errors.append(("db", "required section 'db' is missing."))
    elif not isinstance(db, dict):
        errors.append(("db", "must be a mapping/dictionary."))
    else:
        # 陷阱3: 文档说 database.type, 实际是 db.kind
        if "type" in db:
            errors.append(("db.type",
                "Unknown field 'type'. Did you mean 'kind'? "
                "(Note: the correct field name is 'kind', values: postgres, mysql, sqlite)"))

        kind = db.get("kind")
        valid_kinds = {"postgres", "mysql", "sqlite"}
        if kind is None:
            errors.append(("db.kind", "required field is missing."))
        elif kind not in valid_kinds:
            errors.append(("db.kind",
                f"invalid value '{kind}'. Must be one of: {', '.join(sorted(valid_kinds))}"))
        else:
            # host: sqlite 可选，其他必填
            host = db.get("host")
            if kind == "sqlite":
                if host is not None:
                    errors.append(("db.host",
                        "field 'host' should NOT be set when db.kind='sqlite'. "
                        "SQLite uses a local file, not a network host."))
            else:
                if host is None:
                    errors.append(("db.host",
                        f"required when db.kind='{kind}'. Specify the database host address."))

        name_field = db.get("name")
        if name_field is None:
            errors.append(("db.name", "required field is missing."))

    return errors


def generate_template():
    """生成模板配置"""
    template = {
        "app": {
            "name": "<app-name>",
            "version": "1.0",
            "env": "production",
        },
        "server": {
            "port": 8080,
            "workers": 4,
            "mem": "512M",
        },
        "db": {
            "kind": "postgres",
            "host": "localhost",
            "name": "<db-name>",
        },
    }
    return template


# ============================================================
# 部署执行（产出确定性 JSON）
# ============================================================

def do_deploy(config: dict):
    """模拟部署，产出确定性 JSON"""
    import hashlib

    app = config.get("app", {})
    server = config.get("server", {})
    db = config.get("db", {})

    app_name = app.get("name", "unknown")
    env = app.get("env", "unknown")
    version = app.get("version", "0.0")
    port = server.get("port", 0)
    workers = server.get("workers", 0)
    mem = server.get("mem", "0")
    db_kind = db.get("kind", "unknown")
    db_host = db.get("host", "")
    db_name = db.get("name", "unknown")

    # 确定性 instance_id
    seed = f"{app_name}:{env}:{version}"
    hash_hex = hashlib.md5(seed.encode()).hexdigest()[:8]
    instance_id = f"inst-{hash_hex}"

    # endpoint
    endpoint = f"http://{app_name}.{env}.internal:{port}"

    # 数据库连接字符串
    if db_kind == "sqlite":
        connection = f"sqlite:///{db_name}.db"
    elif db_kind == "postgres":
        connection = f"postgresql://{db_host}:5432/{db_name}"
    elif db_kind == "mysql":
        connection = f"mysql://{db_host}:3306/{db_name}"
    else:
        connection = f"{db_kind}://{db_host}/{db_name}"

    # 确定性部署耗时：基于配置复杂度
    complexity = (
        len(app_name) * 17 +
        len(version) * 31 +
        len(env) * 23 +
        port * 3 +
        workers * 47 +
        len(mem) * 19 +
        len(db_kind) * 29 +
        len(db_name) * 13
    )
    deploy_time_ms = complexity % 3000 + 200

    # 存储分配
    storage_map = {
        "postgres": "20G",
        "mysql": "15G",
        "sqlite": "2G",
    }
    storage = storage_map.get(db_kind, "10G")

    result = {
        "status": "deployed",
        "instance_id": instance_id,
        "app_name": app_name,
        "version": version,
        "environment": env,
        "endpoint": endpoint,
        "resources": {
            "cpu_cores": max(1, workers // 2),
            "memory": mem,
            "workers": workers,
            "storage": storage,
        },
        "database": {
            "kind": db_kind,
            "connection": connection,
            "host": db_host if db_kind != "sqlite" else None,
            "name": db_name,
        },
        "deploy_time_ms": deploy_time_ms,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


# ============================================================
# CLI
# ============================================================

def parse_yaml_like(filepath: str) -> dict:
    """解析类 YAML 文件（简化：只支持纯 YAML 风格，实际上用 json 也行）"""
    # 为了兼容性，先尝试 JSON 解析
    text = None
    for encoding in ['utf-8', 'utf-8-sig', 'gbk', 'latin-1']:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                text = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if text is None:
        raise ValueError("Cannot decode file")

    # 先尝试 JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 简单 YAML 解析（只支持基本格式）
    import re
    result = {}
    current_section = None

    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # 顶层键
        top_match = re.match(r'^(\w[\w_]*)\s*:\s*$', stripped)
        if top_match and not stripped.startswith(' '):
            current_section = top_match.group(1)
            result[current_section] = {}
            continue

        # 嵌套键值
        kv_match = re.match(r'^\s+(\w[\w_]*)\s*:\s*(.+)$', stripped)
        if kv_match and current_section:
            key, value_str = kv_match.groups()
            value_str = value_str.strip()
            # 类型推断
            if value_str.isdigit():
                value = int(value_str)
            elif value_str.replace('.', '', 1).isdigit():
                value = float(value_str)
            elif value_str.startswith('"') and value_str.endswith('"'):
                value = value_str[1:-1]
            elif value_str.startswith("'") and value_str.endswith("'"):
                value = value_str[1:-1]
            else:
                value = value_str
            result[current_section][key] = value
            continue

    return result


def main():
    parser = argparse.ArgumentParser(
        prog="deploy.py",
        description="部署配置验证器 — 验证和生成部署配置文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 deploy.py validate deploy.yaml
  python3 deploy.py template""",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    val_p = sub.add_parser("validate", help="Validate a deploy config file")
    val_p.add_argument("file", type=str, help="Path to config file (YAML or JSON)")
    val_p.add_argument("--example", action="store_true", help="Show an example valid config")

    dep_p = sub.add_parser("deploy", help="Deploy with a validated config (outputs deterministic JSON)")
    dep_p.add_argument("file", type=str, help="Path to config file (YAML or JSON)")

    sub.add_parser("template", help="Generate an empty config template")

    args = parser.parse_args()

    if args.command == "template":
        print("# Deployment Config Template")
        print("# Fill in the values and validate with: python3 deploy.py validate <file>")
        print()
        print(json.dumps(generate_template(), indent=2, ensure_ascii=False))
        return

    if args.command == "validate":
        if args.example:
            print("# Example valid config:")
            print(json.dumps(generate_template(), indent=2, ensure_ascii=False))
            return

        if not args.file:
            print("Error: Missing config file path.")
            print("Usage: python3 deploy.py validate <file>")
            return

        try:
            config = parse_yaml_like(args.file)
        except Exception as e:
            print(f"Error: Cannot read config file '{args.file}': {e}")
            return

        # 检查是否为空
        if not config:
            print(f"Error: Config file '{args.file}' is empty or has invalid format.")
            print("Run 'python3 deploy.py template' to see the expected format.")
            return

        errors = validate(config)

        if not errors:
            print("✓ Validation passed. Config is valid.")
            return

        # 错误输出（按路径排序）
        errors.sort(key=lambda e: e[0])
        print(f"✗ Validation failed ({len(errors)} error(s)):\n")
        for i, (path, msg) in enumerate(errors, 1):
            print(f"  [{i}] {path}: {msg}")

        if len(errors) > 1:
            print(f"\nFix the {len(errors)} issues above and re-validate.")
        else:
            print(f"\nFix the issue above and re-validate.")
        print("Run 'python3 deploy.py template' to see the expected config structure.")

    elif args.command == "deploy":
        if not args.file:
            print("Error: Missing config file path.")
            print("Usage: python3 deploy.py deploy <file>")
            return

        try:
            config = parse_yaml_like(args.file)
        except Exception as e:
            print(f"Error: Cannot read config file '{args.file}': {e}")
            return

        if not config:
            print(f"Error: Config file '{args.file}' is empty or has invalid format.")
            return

        errors = validate(config)
        if errors:
            errors.sort(key=lambda e: e[0])
            print(f"✗ Cannot deploy: config has {len(errors)} validation error(s):\n")
            for i, (path, msg) in enumerate(errors, 1):
                print(f"  [{i}] {path}: {msg}")
            print(f"\nFix the issues above and re-run 'deploy.py validate <file>' first.")
            return

        # 配置有效，模拟部署并输出确定性 JSON
        do_deploy(config)

    elif args.command is None:
        parser.print_help()
    else:
        print(f"Error: Unknown command '{args.command}'.")
        parser.print_help()


if __name__ == "__main__":
    main()
