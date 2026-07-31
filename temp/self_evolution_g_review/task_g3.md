# 自进化任务 G-3：编写字符串排序函数

## 任务背景

数据平台最后一个需求：实现一个字符串按长度排序的功能。

（审查工具与前面相同：`python3 review.py`）

## 任务要求

### 第一步：编写代码并通过审查

编写一个 Python 文件 `sort_strings.py`，实现一个函数：

- **输入**：一个字符串列表 `words`
- **输出**：一个字典，包含：
  - `by_length_asc`: 按字符串长度升序排列的列表
  - `by_length_desc`: 按字符串长度降序排列的列表
  - `longest`: 最长的字符串
  - `shortest`: 最短的字符串

### 第二步：运行测试

代码通过审查后，运行 `python3 review.py test <your_file>`，将完整 JSON 输出写入 `answer_g3.json`。

## 提交规则

1. 将代码文件命名为 `sort_strings.py`
2. 将 `review.py test` 输出的**完整 JSON** 写入 `answer_g3.json`

## 提示

- 编码规则你已经完全掌握了，直接复用前面的函数模板即可
