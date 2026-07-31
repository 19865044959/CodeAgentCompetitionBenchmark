# 部署配置编写指南 (DEPLOY_GUIDE.md)

**版本**: v2.0

本文档描述了如何使用 `deploy.py` 验证器编写部署配置文件。配置文件采用 YAML 或 JSON 格式。

---

## 1. 配置文件结构

配置文件包含三个顶层部分：

### 1.1 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `app_name` | string | 是 | 应用名称，任意字符串 |
| `app_version` | string | 是 | 应用版本号 |

### 1.2 server 部分

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `server.port` | integer | 是 | 服务端口号，范围 80-65535 |
| `server.workers` | integer | 否 | 工作进程数，默认 1 |
| `server.memory` | string | 是 | 内存分配，格式：数字+单位（如 "512MB"） |

### 1.3 database 部分

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `database.type` | string | 是 | 数据库类型：postgres / mysql / sqlite |
| `database.host` | string | 是 | 数据库主机地址 |
| `database.name` | string | 是 | 数据库名称 |

---

## 2. 完整示例

```yaml
app_name: traffic-monitor
app_version: "2.1"
server:
  port: 8080
  workers: 4
  memory: "512MB"
database:
  type: postgres
  host: localhost
  name: traffic_db
```

## 3. 验证命令

```bash
python3 deploy.py validate deploy.yaml
```

## 4. 注意事项

1. 所有字段名区分大小写
2. 端口号必须在合法范围内
3. 环境变量支持：`env: production | staging | dev`
