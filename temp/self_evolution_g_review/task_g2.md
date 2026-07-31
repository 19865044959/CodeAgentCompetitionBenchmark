# 自进化任务 G-2：编写列表过滤函数

## 任务背景

继续在数据平台上的开发工作。接下来需要实现一个列表过滤函数。

（审查工 具与上一题相同：`python3 review.py`）

## 任务要求

### 第一步：编写代码并通过审查

编写一个 Python 文件 `filter_evens.py`，实现一个函数：

- **输入**：一个整数列表 `numbers`
- **输出**：一个字典，包含：
  - `evens`: 所有偶数组成的列表
  - `odds`: 所有奇数组成的列表
  - `even_count`: 偶数的个数
  - `odd_count`: 奇数的个数

### 第二步：运行测试

代码通过审查后，运行 `python3 review.py test <your_file>`，从输出的 JSON 中提取完整内容写入 `answer_g2.json`。

## 提交规则

1. 将代码文件命名为 `filter_evens.py`
2. 将 `review.py test` 输出的**完整 JSON** 写入 `answer_g2.json` 文件

## 提示

- 如果你在上一个任务中已经掌握了审查规则，现在应该可以快速通过
- 直接套用之前验证过的代码结构和命名模式
