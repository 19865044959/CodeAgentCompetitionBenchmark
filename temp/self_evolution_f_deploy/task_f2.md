# 自进化任务 F-2：编写预发布环境部署配置

## 任务背景

生产环境配置完成后，还需要为 **预发布环境（staging）** 编写配置并部署。预发布环境使用 SQLite 数据库（无需远程主机）。

（工具与上一题相同：`python3 deploy.py`）

## 任务要求

### 第一步：编写配置

编写配置文件，满足以下业务需求：

| 配置项 | 目标值 |
|--------|--------|
| 应用名 | `traffic-monitor` |
| 版本 | `2.1-rc1` |
| 环境 | `staging` |
| 端口 | `3000` |
| 工作进程数 | `2` |
| 内存 | `256M` |
| 数据库类型 | `sqlite` |
| 数据库名 | `traffic_test` |

### 第二步：执行部署

配置通过验证后，运行 `python3 deploy.py deploy <your_file>`，从输出 JSON 中提取：

```json
{
  "instance_id": "<instance_id>",
  "endpoint": "<endpoint>",
  "database_connection": "<database.connection>",
  "storage": "<resources.storage>",
  "deploy_time_ms": <deploy_time_ms>
}
```

## 提交规则

1. 将配置文件命名为 `deploy_staging.yaml`
2. 将提取的 JSON 写入 `answer_f2.json` 文件

## 提示

- 如果你在上一个任务中已经摸清了验证规则，现在可以直接写出正确配置
- 注意 sqlite 模式与其他数据库的差异
