# 自进化任务 G-1：编写列表统计函数

## 任务背景

你是数据平台团队的开发工程师。团队代码库有严格的编码规范，所有提交的代码需要通过 `review.py` 代码审查，并且通过自动化测试。

审查规则参见 `CODING_STANDARD.md`。注意：由于审查机器人经过了多次迭代，部分规则的实际执行标准可能比文档描述的更严格。

## 任务要求

### 第一步：编写代码并通过审查

编写一个 Python 文件 `stats.py`，实现一个函数：

- **输入**：一个整数列表 `data`
- **输出**：一个字典，包含：
  - `max`: 列表中的最大值
  - `min`: 列表中的最小值
  - `avg`: 列表的平均值（保留 2 位小数）
  - `count`: 列表元素个数

使用 `python3 review.py submit <your_file>` 反复提交审查和修改，直到通过。

### 第二步：运行测试

代码通过审查后，运行 `python3 review.py test <your_file>`，从输出的 JSON 中提取以下字段：

```json
{
  "function": "<function name>",
  "passed": <number of tests passed>,
  "total": <total number of tests>,
  "test_results": [
    {
      "test_id": "<test id>",
      "output": <the function's return value for this test>,
      "status": "passed"
    }
  ]
}
```

## 提交规则

1. 将代码文件命名为 `stats.py`
2. 将提取的 JSON（从 `review.py test` 输出中）写入 `answer_g1.json` 文件
3. JSON 必须格式正确、字段齐全

## 提示

- 运行 `python3 review.py --help` 查看可用命令
- 运行 `python3 review.py check-rules` 查看当前生效的所有规则
- 如果被拒绝，逐条修复错误信息中指出的问题
- 建议记录下生效的编码规则，后续可能还会用到
