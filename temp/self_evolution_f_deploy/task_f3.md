# 自进化任务 F-3：编写开发环境部署配置

## 任务背景

最后，为开发环境（dev）编写配置并部署，使用 MySQL 数据库。

（工具与前面相同：`python3 deploy.py`）

## 任务要求

### 第一步：编写配置

编写配置文件，满足以下业务需求：

| 配置项 | 目标值 |
|--------|--------|
| 应用名 | `traffic-monitor` |
| 版本 | `2.2-dev` |
| 环境 | `dev` |
| 端口 | `5000` |
| 工作进程数 | `1` |
| 内存 | `128M` |
| 数据库类型 | `mysql` |
| 数据库主机 | `db-dev.internal` |
| 数据库名 | `traffic_dev` |

### 第二步：执行部署

配置通过验证后，运行 `python3 deploy.py deploy <your_file>`，从输出 JSON 中提取：

```json
{
  "instance_id": "<instance_id>",
  "endpoint": "<endpoint>",
  "database_connection": "<database.connection>",
  "cpu_cores": <resources.cpu_cores>,
  "deploy_time_ms": <deploy_time_ms>
}
```

## 提交规则

1. 将配置文件命名为 `deploy_dev.yaml`
2. 将提取的 JSON 写入 `answer_f3.json` 文件

## 提示

- 验证规则的框架你已经完全掌握了，直接复用前面的经验即可
