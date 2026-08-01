#!/usr/bin/env python3
"""
国家文化遗产数字档案查询系统 — Mock API Server
==============================================
自进化任务 Type A: 未知API类
运行方式: python3 api_server.py
监听地址: http://localhost:8899

这个服务由大赛组织方启动，选手 Agent 通过终端与它交互。
"""

import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================================
# 模拟数据库
# ============================================================
HERITAGE_DATA = {
    "北京": [
        {"id": "BJ001", "name": "故宫", "type": "建筑", "era": "明清", "protected_level": "世界遗产"},
        {"id": "BJ002", "name": "天坛", "type": "建筑", "era": "明", "protected_level": "世界遗产"},
        {"id": "BJ003", "name": "颐和园", "type": "园林", "era": "清", "protected_level": "世界遗产"},
        {"id": "BJ004", "name": "明十三陵", "type": "陵墓", "era": "明", "protected_level": "世界遗产"},
        {"id": "BJ005", "name": "长城(北京段)", "type": "军事防御", "era": "明", "protected_level": "世界遗产"},
        {"id": "BJ006", "name": "周口店遗址", "type": "遗址", "era": "旧石器时代", "protected_level": "世界遗产"},
        {"id": "BJ007", "name": "雍和宫", "type": "宗教建筑", "era": "清", "protected_level": "全国重点"},
        {"id": "BJ008", "name": "恭王府", "type": "建筑", "era": "清", "protected_level": "全国重点"},
        {"id": "BJ009", "name": "北海公园", "type": "园林", "era": "辽金元明清", "protected_level": "全国重点"},
        {"id": "BJ010", "name": "国子监", "type": "教育建筑", "era": "元明清", "protected_level": "全国重点"},
        {"id": "BJ011", "name": "潭柘寺", "type": "宗教建筑", "era": "晋", "protected_level": "全国重点"},
        {"id": "BJ012", "name": "卢沟桥", "type": "桥梁", "era": "金", "protected_level": "全国重点"},
        {"id": "BJ013", "name": "正阳门", "type": "城门", "era": "明", "protected_level": "全国重点"},
        {"id": "BJ014", "name": "鼓楼", "type": "建筑", "era": "元", "protected_level": "全国重点"},
        {"id": "BJ015", "name": "圆明园遗址", "type": "遗址", "era": "清", "protected_level": "全国重点"},
    ],
    "南京": [
        {"id": "NJ001", "name": "明孝陵", "type": "陵墓", "era": "明", "protected_level": "世界遗产"},
        {"id": "NJ002", "name": "中山陵", "type": "陵墓", "era": "民国", "protected_level": "全国重点"},
        {"id": "NJ003", "name": "夫子庙", "type": "建筑群", "era": "宋", "protected_level": "全国重点"},
        {"id": "NJ004", "name": "南京城墙", "type": "军事防御", "era": "明", "protected_level": "全国重点"},
        {"id": "NJ005", "name": "总统府", "type": "建筑", "era": "民国", "protected_level": "全国重点"},
        {"id": "NJ006", "name": "鸡鸣寺", "type": "宗教建筑", "era": "南北朝", "protected_level": "全国重点"},
        {"id": "NJ007", "name": "栖霞寺", "type": "宗教建筑", "era": "南北朝", "protected_level": "全国重点"},
        {"id": "NJ008", "name": "灵谷寺", "type": "宗教建筑", "era": "明", "protected_level": "全国重点"},
        {"id": "NJ009", "name": "瞻园", "type": "园林", "era": "明", "protected_level": "全国重点"},
        {"id": "NJ010", "name": "南京博物院", "type": "建筑", "era": "民国", "protected_level": "全国重点"},
        {"id": "NJ011", "name": "美龄宫", "type": "建筑", "era": "民国", "protected_level": "全国重点"},
        {"id": "NJ012", "name": "雨花台", "type": "纪念地", "era": "现代", "protected_level": "全国重点"},
    ],
    "成都": [
        {"id": "CD001", "name": "武侯祠", "type": "祠堂", "era": "三国", "protected_level": "全国重点"},
        {"id": "CD002", "name": "杜甫草堂", "type": "园林", "era": "唐", "protected_level": "全国重点"},
        {"id": "CD003", "name": "金沙遗址", "type": "遗址", "era": "商周", "protected_level": "全国重点"},
        {"id": "CD004", "name": "都江堰", "type": "水利工程", "era": "战国", "protected_level": "世界遗产"},
        {"id": "CD005", "name": "青羊宫", "type": "宗教建筑", "era": "唐", "protected_level": "全国重点"},
        {"id": "CD006", "name": "望江楼", "type": "建筑", "era": "清", "protected_level": "全国重点"},
        {"id": "CD007", "name": "文殊院", "type": "宗教建筑", "era": "唐", "protected_level": "全国重点"},
        {"id": "CD008", "name": "宽窄巷子", "type": "街区", "era": "清", "protected_level": "省级"},
        {"id": "CD009", "name": "锦里", "type": "街区", "era": "三国", "protected_level": "省级"},
        {"id": "CD010", "name": "永陵", "type": "陵墓", "era": "五代", "protected_level": "全国重点"},
    ],
}

VALID_API_KEYS = {"heritage-api-key-2024"}


class HeritageAPIHandler(BaseHTTPRequestHandler):
    """文化遗产档案查询 API 请求处理器

    与 API_DOCS.md 之间的 3 个陷阱:
      1. 认证: 文档说 X-API-Key header, 实际用 Authorization: Bearer <key>
      2. 参数: 文档说 city, 实际用 location
      3. 分页: 默认分页10，没说分页到底多少
    """

    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.wfile.write(body)

    # ── 陷阱1: 认证 ────────────────────────────────────────────
    def _check_auth(self):
        """返回 (is_authenticated, error_detail)"""

        auth_header = self.headers.get("Authorization", "")
        if not auth_header:
            return False, "Missing 'Authorization' header. Expected format: 'Authorization: Bearer <api_key>'"

        if not auth_header.startswith("Bearer "):
            return False, f"Authorization scheme must be 'Bearer', got: '{auth_header.split()[0] if auth_header.split() else auth_header}'"

        key = auth_header[len("Bearer "):]
        if key not in VALID_API_KEYS:
            return False, f"Invalid API key: '{key}'. Valid keys: {', '.join(sorted(VALID_API_KEYS))}"

        return True, ""

    # ── 错误响应（与文档不一致，文档说 {"error":"msg"}） ──────
    def _error(self, code, message):
        self._send_json(code, {
            "status": "error",
            "message": message,
            "code": code,
        })

    # ── 路由 ───────────────────────────────────────────────────
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 兼容未编码的中文参数
        raw_query = parsed.query
        try:
            raw_query = raw_query.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
        params = urllib.parse.parse_qs(raw_query)

        if path == "/api/v1/heritage/search":
            # 认证
            authed, err_detail = self._check_auth()
            if not authed:
                self._error(401, f"Authentication failed: {err_detail}")
                return

            # 陷阱2: 文档说 city，实际用 location
            city = params.get("location", [None])[0]
            if not city:
                self._error(400, "Missing required parameter: location")
                return

            if city not in HERITAGE_DATA:
                self._error(404, f"No heritage records found for location: {city}")
                return

            all_records = HERITAGE_DATA[city]
            try:
                offset = int(params.get("offset", [0])[0])
                limit = int(params.get("limit", [10])[0])
            except ValueError:
                offset = 0
                limit = 10

            page_records = all_records[offset: offset + limit]
            total = len(all_records)

            # 响应结构: 嵌套（文档说 {"items":[],"total":N}）
            self._send_json(200, {
                "code": 200,
                "data": {
                    "records": page_records,
                    "pagination": {
                        "total_count": total,
                        "offset": offset,
                        "limit": limit,
                    },
                },
            })

        else:
            self._error(404, f"Endpoint not found: {path}")

    def log_message(self, format, *args):
        print(f"[API] {args[0]}")


if __name__ == "__main__":
    server = HTTPServer(("localhost", 8899), HeritageAPIHandler)
    print("=" * 55)
    print("  国家文化遗产数字档案查询系统 (NCHDA)")
    print("  Mock API Server")
    print("=" * 55)
    print(f"  监听地址: http://localhost:8899")
    print(f"  可用 API Key: {', '.join(VALID_API_KEYS)}")
    print()
    print("  可用城市: 北京, 南京, 成都")
    print("  按 Ctrl+C 停止服务")
    print("=" * 55)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止。")
        server.server_close()
