# 自进化任务 E-2：查询朝阳区2024年交通数据

## 任务背景

环境评估报告的下一部分，需要补充战后城市的交通拥堵数据。请使用同一个 `datatool.pyc` 工具，查询 **朝阳区 2024年** 的交通数据（traffic dataset）。

（工具与上一题相同：`python3 datatool.pyc`）

## 任务要求

使用 `python3 datatool.pyc` 查询朝阳区 2024 年的交通数据，提取以下统计信息：

```json
{
  "district": "朝阳区",
  "year": "2024年",
  "avg_congestion_index": <平均拥堵指数>,
  "total_roads": <统计道路总数>,
  "most_congested_road": "<拥堵指数最高的道路名>",
  "highest_peak_speed_road": "<高峰期速度最快的道路名>",
  "roads_count": <返回的道路数据条数>
}
```

## 提交规则

1. 将上述 JSON 写入本任务文件所在目录下的 `answer_e2.json`，完整路径为：`/tmp/自进化类任务/1固定步骤类/3CLI工具/answer_e2.json`
2. 写文件时必须使用上述绝对路径（或先 `cd` 到该目录再写），不要使用不带路径的相对文件名
3. JSON 必须格式正确、字段齐全

## 提示

- 如果你在上一个任务中已经掌握了 `datatool.pyc` 的使用模式，现在应该可以直接复用
- 注意不同数据集使用的参数名不同
