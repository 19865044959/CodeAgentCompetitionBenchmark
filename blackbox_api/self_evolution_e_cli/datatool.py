#!/usr/bin/env python3
"""
城市环境监测数据查询工具 (datatool.py)
======================================
自进化任务 Type E: CLI工具类

与 API_DOCS.md 之间的陷阱:
  1. 子命令: 文档说 search，实际用 fetch
  2. 参数名: 不同数据集用不同的位置参数名
     - weather: --station (文档说 --city)
     - traffic: --district (文档说 --city)
     - population: --area (文档说 --city)
  3. 年份格式: 必须是中文年份 "2024年" (文档说 "2024")
  4. 输出格式: 文档说 flat array，实际是嵌套 JSON
  5. --help 只给出通用帮助，具体参数通过错误提示发现
"""

import sys
import json
import argparse

# ============================================================
# 数据集
# ============================================================
WEATHER_DATA = {
    "北京": {
        "2024年": {
            "station": "北京气象站",
            "total_days": 365,
            "avg_temp": 13.5,
            "avg_humidity": 52.3,
            "avg_aqi": 78,
            "records": [
                {"month": "1月", "avg_temp": -3.2, "avg_aqi": 95, "rain_days": 3},
                {"month": "2月", "avg_temp": 0.1, "avg_aqi": 82, "rain_days": 2},
                {"month": "3月", "avg_temp": 8.5, "avg_aqi": 75, "rain_days": 4},
                {"month": "4月", "avg_temp": 16.2, "avg_aqi": 68, "rain_days": 6},
                {"month": "5月", "avg_temp": 22.8, "avg_aqi": 55, "rain_days": 7},
                {"month": "6月", "avg_temp": 27.1, "avg_aqi": 48, "rain_days": 10},
                {"month": "7月", "avg_temp": 29.3, "avg_aqi": 42, "rain_days": 14},
                {"month": "8月", "avg_temp": 28.0, "avg_aqi": 45, "rain_days": 12},
                {"month": "9月", "avg_temp": 23.5, "avg_aqi": 52, "rain_days": 8},
                {"month": "10月", "avg_temp": 15.0, "avg_aqi": 65, "rain_days": 5},
                {"month": "11月", "avg_temp": 5.5, "avg_aqi": 80, "rain_days": 3},
                {"month": "12月", "avg_temp": -1.0, "avg_aqi": 92, "rain_days": 2},
            ]
        },
        "2023年": {
            "station": "北京气象站",
            "total_days": 365,
            "avg_temp": 12.9,
            "avg_humidity": 54.1,
            "avg_aqi": 82,
            "records": [
                {"month": "1月", "avg_temp": -2.8, "avg_aqi": 102, "rain_days": 2},
                {"month": "2月", "avg_temp": 0.5, "avg_aqi": 88, "rain_days": 3},
                {"month": "3月", "avg_temp": 9.0, "avg_aqi": 72, "rain_days": 5},
                {"month": "4月", "avg_temp": 15.8, "avg_aqi": 65, "rain_days": 6},
                {"month": "5月", "avg_temp": 23.0, "avg_aqi": 58, "rain_days": 8},
                {"month": "6月", "avg_temp": 26.5, "avg_aqi": 50, "rain_days": 11},
                {"month": "7月", "avg_temp": 29.0, "avg_aqi": 44, "rain_days": 13},
                {"month": "8月", "avg_temp": 27.5, "avg_aqi": 48, "rain_days": 11},
                {"month": "9月", "avg_temp": 22.8, "avg_aqi": 55, "rain_days": 7},
                {"month": "10月", "avg_temp": 14.5, "avg_aqi": 68, "rain_days": 6},
                {"month": "11月", "avg_temp": 5.0, "avg_aqi": 85, "rain_days": 3},
                {"month": "12月", "avg_temp": -0.5, "avg_aqi": 98, "rain_days": 2},
            ]
        }
    },
    "上海": {
        "2024年": {
            "station": "上海气象站",
            "total_days": 365,
            "avg_temp": 18.2,
            "avg_humidity": 72.5,
            "avg_aqi": 55,
            "records": [
                {"month": "1月", "avg_temp": 5.2, "avg_aqi": 62, "rain_days": 8},
                {"month": "2月", "avg_temp": 7.0, "avg_aqi": 58, "rain_days": 9},
                {"month": "3月", "avg_temp": 11.5, "avg_aqi": 52, "rain_days": 12},
                {"month": "4月", "avg_temp": 17.0, "avg_aqi": 48, "rain_days": 11},
                {"month": "5月", "avg_temp": 22.5, "avg_aqi": 42, "rain_days": 13},
                {"month": "6月", "avg_temp": 26.8, "avg_aqi": 35, "rain_days": 15},
                {"month": "7月", "avg_temp": 30.2, "avg_aqi": 30, "rain_days": 14},
                {"month": "8月", "avg_temp": 29.8, "avg_aqi": 32, "rain_days": 13},
                {"month": "9月", "avg_temp": 25.5, "avg_aqi": 38, "rain_days": 11},
                {"month": "10月", "avg_temp": 20.0, "avg_aqi": 45, "rain_days": 8},
                {"month": "11月", "avg_temp": 13.5, "avg_aqi": 55, "rain_days": 7},
                {"month": "12月", "avg_temp": 7.5, "avg_aqi": 60, "rain_days": 6},
            ]
        }
    }
}

TRAFFIC_DATA = {
    "朝阳区": {
        "2024年": {
            "district": "朝阳区",
            "total_roads": 156,
            "avg_congestion_index": 7.2,
            "data": [
                {"road": "三环路朝阳段", "congestion_index": 8.5, "peak_speed": 25, "offpeak_speed": 55},
                {"road": "四环路朝阳段", "congestion_index": 7.8, "peak_speed": 30, "offpeak_speed": 60},
                {"road": "京通快速", "congestion_index": 6.5, "peak_speed": 40, "offpeak_speed": 75},
                {"road": "机场高速", "congestion_index": 5.2, "peak_speed": 55, "offpeak_speed": 90},
                {"road": "望京区域", "congestion_index": 8.0, "peak_speed": 20, "offpeak_speed": 45},
            ]
        }
    },
    "海淀区": {
        "2024年": {
            "district": "海淀区",
            "total_roads": 132,
            "avg_congestion_index": 6.8,
            "data": [
                {"road": "中关村大街", "congestion_index": 7.5, "peak_speed": 28, "offpeak_speed": 50},
                {"road": "学院路", "congestion_index": 6.2, "peak_speed": 35, "offpeak_speed": 58},
                {"road": "西三环海淀段", "congestion_index": 7.0, "peak_speed": 32, "offpeak_speed": 55},
                {"road": "北四环海淀段", "congestion_index": 7.3, "peak_speed": 30, "offpeak_speed": 52},
                {"road": "上地信息路", "congestion_index": 5.8, "peak_speed": 38, "offpeak_speed": 62},
            ]
        }
    }
}

POPULATION_DATA = {
    "海淀区": {
        "2024年": {
            "area": "海淀区",
            "total_population": 3_230_000,
            "households": 1_120_000,
            "density_per_km2": 7_500,
            "age_groups": [
                {"group": "0-14岁", "count": 410_000, "ratio": 0.127},
                {"group": "15-59岁", "count": 2_200_000, "ratio": 0.681},
                {"group": "60岁以上", "count": 620_000, "ratio": 0.192},
            ],
            "employment": [
                {"sector": "信息技术", "count": 850_000, "ratio": 0.385},
                {"sector": "教育科研", "count": 520_000, "ratio": 0.236},
                {"sector": "服务业", "count": 410_000, "ratio": 0.186},
                {"sector": "制造业", "count": 180_000, "ratio": 0.082},
                {"sector": "其他", "count": 245_000, "ratio": 0.111},
            ]
        }
    },
    "朝阳区": {
        "2024年": {
            "area": "朝阳区",
            "total_population": 3_450_000,
            "households": 1_250_000,
            "density_per_km2": 7_300,
            "age_groups": [
                {"group": "0-14岁", "count": 465_000, "ratio": 0.135},
                {"group": "15-59岁", "count": 2_350_000, "ratio": 0.681},
                {"group": "60岁以上", "count": 635_000, "ratio": 0.184},
            ],
            "employment": [
                {"sector": "金融商务", "count": 920_000, "ratio": 0.392},
                {"sector": "服务业", "count": 580_000, "ratio": 0.247},
                {"sector": "信息技术", "count": 450_000, "ratio": 0.191},
                {"sector": "制造业", "count": 160_000, "ratio": 0.068},
                {"sector": "其他", "count": 240_000, "ratio": 0.102},
            ]
        }
    }
}

# ============================================================
# 参数名映射（不同数据集用不同的参数名 — 陷阱2）
# ============================================================
DATASET_PARAM_MAP = {
    "weather": "station",
    "traffic": "district",
    "population": "area",
}

DATASET_PARAM_HINT = {
    "weather": "weather: use '--station'",
    "traffic": "traffic: use '--district'",
    "population": "population: use '--area'",
}

DATASETS = {
    "weather": WEATHER_DATA,
    "traffic": TRAFFIC_DATA,
    "population": POPULATION_DATA,
}

# ============================================================
# CLI 实现
# ============================================================

def parse_year(raw: str):
    """解析年份，接受 '2024' 或 '2024年'"""
    if not raw:
        return None, "Missing required parameter"
    # 接受纯数字年份
    if raw.isdigit():
        return f"{raw}年", None
    # 接受带"年"的年份
    if raw.endswith("年") and raw[:-1].isdigit():
        return raw, None
    return None, f"Invalid year format: '{raw}'. Use '2024' or '2024年'."


def cmd_list(args):
    """列出可用数据集"""
    print("Available datasets:")
    for name in sorted(DATASETS.keys()):
        locations = list(DATASETS[name].keys())
        param = DATASET_PARAM_MAP[name]
        print(f"  {name:12s}  (--{param} <name>)  locations: {', '.join(locations)}")
    return 0


def cmd_fetch(args):
    """获取数据集"""
    # 解析 --dataset
    dataset = args.dataset
    if dataset is None:
        print("Error: Missing required option '--dataset'.")
        print(f"Available datasets: {', '.join(sorted(DATASETS.keys()))}")
        print("Usage: python3 datatool.py fetch --dataset <name> [options]")
        return 1
    if dataset not in DATASETS:
        print(f"Error: Unknown dataset '{dataset}'.")
        print(f"Available datasets: {', '.join(sorted(DATASETS.keys()))}")
        return 1

    # 确定参数名
    param_name = DATASET_PARAM_MAP[dataset]

    # 解析位置参数（--station / --district / --area）
    location = getattr(args, param_name, None)
    if location is None:
        # 检查是不是用了错误的参数名
        for wrong_param in DATASET_PARAM_MAP.values():
            if wrong_param != param_name and getattr(args, wrong_param, None):
                print(f"Error: For dataset '{dataset}', use '--{param_name}' instead of '--{wrong_param}'.")
                print(f"Hint: {DATASET_PARAM_HINT[dataset]}")
                return 1
        # 检查通用错误 --city
        if hasattr(args, 'city') and args.city:
            print(f"Error: Unknown option '--city'.")
            print(f"Hint: For dataset '{dataset}', use '--{param_name} <name>' to specify the location.")
            print(f"All dataset parameter mappings: {', '.join(f'{d}→--{p}' for d, p in DATASET_PARAM_MAP.items())}")
            return 1
        print(f"Error: Missing required option '--{param_name}' for dataset '{dataset}'.")
        locations = list(DATASETS[dataset].keys())
        print(f"Available locations for {dataset}: {', '.join(locations)}")
        print(f"Usage: python3 datatool.py fetch --dataset {dataset} --{param_name} <name> --year <year>")
        return 1

    # 解析 --year
    year_raw = args.year
    year, err = parse_year(year_raw)
    if err:
        print(f"Error: {err}")
        return 1

    # 查询数据
    ds = DATASETS[dataset]
    if location not in ds:
        print(f"Error: Location '{location}' not found in dataset '{dataset}'.")
        print(f"Available locations: {', '.join(sorted(ds.keys()))}")
        return 1

    loc_data = ds[location]
    if year not in loc_data:
        print(f"Error: Year '{year}' not found for {dataset}/{location}.")
        print(f"Available years: {', '.join(sorted(loc_data.keys()))}")
        return 1

    # 输出
    result = {
        "status": "success",
        "dataset": dataset,
        "location": location,
        "year": year,
        "data": loc_data[year],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser():
    # 顶层 parser — --help 只显示子命令（陷阱5）
    parser = argparse.ArgumentParser(
        prog="datatool.py",
        description="城市环境监测数据查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 datatool.py list
  python3 datatool.py fetch --dataset weather --station 北京 --year 2024""",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # list 子命令
    sub.add_parser("list", help="List available datasets")

    # fetch 子命令（模拟了文档里说的 search — 陷阱1）
    fetch_p = sub.add_parser("fetch", help="Fetch data from a dataset")
    fetch_p.add_argument("--dataset", type=str, help="Dataset name (weather/traffic/population)")
    # 三个不同名的位置参数（陷阱2）
    fetch_p.add_argument("--station", type=str, help="Station name (for weather dataset)")
    fetch_p.add_argument("--district", type=str, help="District name (for traffic dataset)")
    fetch_p.add_argument("--area", type=str, help="Area name (for population dataset)")
    fetch_p.add_argument("--year", type=str, help="Year (e.g., '2024')")

    # 也加一个 hidden alias: 如果用户用 search（文档说 search），给个友好错误
    # argparse 不支持，我们在 main 里处理
    return parser


def main():
    # 陷阱1: 文档说 search，实际用 fetch
    if len(sys.argv) > 1 and sys.argv[1] == "search":
        print("Error: Unknown subcommand 'search'. Did you mean 'fetch'?")
        print("Usage: python3 datatool.py fetch [options]")
        print("Run 'python3 datatool.py --help' for all available commands.")
        sys.exit(1)

    parser = build_parser()

    try:
        args = parser.parse_args()
    except SystemExit:
        return

    if args.command is None:
        parser.print_help()
        return

    if args.command == "list":
        sys.exit(cmd_list(args))
    elif args.command == "fetch":
        sys.exit(cmd_fetch(args))
    else:
        print(f"Error: Unknown command '{args.command}'.")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
