# 自进化任务 E-3：查询海淀区2024年人口数据

## 任务背景

环境评估报告的最后一部分，需要补充人口分布数据。请使用 `datatool.py` 查询 **海淀区 2024年** 的人口数据（population dataset）。

（工具与前面相同：`python3 datatool.py`）

## 任务要求

使用 `python3 datatool.py` 查询海淀区 2024 年的人口数据，提取以下统计信息：

```json
{
  "area": "海淀区",
  "year": "2024年",
  "total_population": <总人口>,
  "households": <总户数>,
  "density_per_km2": <人口密度>,
  "largest_age_group": "<占比最大的年龄段>",
  "largest_employment_sector": "<从业人数最多的行业>",
  "age_groups_count": <年龄段分组数>,
  "sectors_count": <就业行业分类数>
}
```

## 提交规则

1. 将上述 JSON 写入 `answer_e3.json` 文件
2. JSON 必须格式正确、字段齐全

## 提示

- 你已经在前面任务中熟悉了工具的使用模式
- 如果总结了可复用的查询脚本模板，现在直接套用即可
