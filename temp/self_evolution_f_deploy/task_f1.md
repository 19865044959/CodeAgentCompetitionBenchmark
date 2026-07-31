# 自进化任务 F-1：编写生产环境部署配置

## 任务背景

你是 DevOps 团队的部署工程师。团队使用一个名为 `deploy.py` 的配置验证和部署工具。你需要编写一个符合验证规则的配置文件，然后执行部署。

部署配置的编写指南参见 `DEPLOY_GUIDE.md`。注意：由于工具经过了长期迭代，指南中的部分内容可能与验证器的实际规则不完全一致。

## 任务要求

### 第一步：编写配置

编写一个部署配置文件，满足以下业务需求：

| 配置项 | 目标值 |
|--------|--------|
| 应用名 | `traffic-monitor` |
| 版本 | `2.1` |
| 环境 | `production` |
| 端口 | `8080` |
| 工作进程数 | `4` |
| 内存 | `512M` |
| 数据库类型 | `postgres` |
| 数据库主机 | `localhost` |
| 数据库名 | `traffic_db` |

使用 `python3 deploy.py validate <your_file>` 反复验证和修改，直到通过。

### 第二步：执行部署

配置通过验证后，运行 `python3 deploy.py deploy <your_file>`，从输出的 JSON 中提取以下字段：

```json
{
  "instance_id": "<instance_id>",
  "endpoint": "<endpoint>",
  "database_connection": "<database.connection>",
  "deploy_time_ms": <deploy_time_ms>
}
```

## 提交规则

1. 将配置文件命名为 `deploy.yaml`（或 `deploy.json`）
2. 将提取的 JSON 写入 `answer_f1.json` 文件
3. JSON 必须格式正确、字段齐全
4. 数据必须来源于 `deploy.py deploy` 的实际输出

## 提示

- 运行 `python3 deploy.py --help` 查看所有命令
- 运行 `python3 deploy.py template` 生成配置模板
- 如果验证报错，仔细阅读错误信息，每个错误都包含了修改提示
- 建议记录下最终的配置结构，后续可能还会用到
