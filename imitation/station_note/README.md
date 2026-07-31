# 自进化任务 — Track D-Simple：照样板办（简化版）

## 赛题简介

Agent 扮演荒野后勤署的账册整理员。任务官不直接说明数据处理规则，只提供已经验收通过的输入/输出样板。Agent 需要通过逐列、逐行比较样板，反推出完整转换规则，再处理新的待办清单。

## 简化说明

相比完整版 D-track（3 题、规则族变化），本简化版：
- **三题**：共 3 道题（灰雀、柳莺、松鸦），每题 2 组样板
- **固定规则**：三题使用完全相同的转换规则，不涉及列名变化、精度变化
- **核心考察**：从样板归纳规则 → 应用规则处理新数据 → 自进化（题1形成的SOP可直接复用到题2、题3）
- **自验证**：每题内置 `./check` 脚本，通过即输出 TOKEN

## 文件结构

```text
self_evolution_d_simple/
├── README.md              # 本文件
├── task.md                 # 任务描述（给 Agent 看）
├── samples/
│   ├── in_1.csv           # 第 1 组原始样板（灰雀）
│   ├── out_1.csv          # 第 1 组已验收成品
│   ├── in_2.csv           # 第 2 组原始样板
│   └── out_2.csv          # 第 2 组已验收成品
├── work/
│   └── in.csv             # 待处理文件（灰雀）
├── check                  # 评测脚本（可执行）
├── expected_token.json    # Token 存储（单题模式）
├── expected_token_1.json  # 题1 Token（benchmark用）
├── expected_token_2.json  # 题2 Token（benchmark用）
├── expected_token_3.json  # 题3 Token（benchmark用）
├── generate_workspace.py  # 生成任务变体
├── _build.py              # 构建原始数据
├── _reference/            # 标准答案（Agent 不可见）
└── cases/
    ├── ws_1/              # 题目1：灰雀驿站
    │   ├── samples/       # 2组样板
    │   ├── work/in.csv    # 待处理文件
    │   ├── check          # 独立评测脚本
    │   └── spec.md        # 题面
    ├── ws_2/              # 题目2：柳莺驿站
    │   └── ...            # 同上结构
    └── ws_3/              # 题目3：松鸦驿站
        └── ...            # 同上结构
```

## 评测方式

```bash
./check
```

- 未生成 `work/out.csv` → `E_MISSING_OUTPUT`
- CSV 与标准成品不一致 → `E_DIFF` + 提示
- CSV 与标准成品逐字节一致 → `OK` + `TOKEN: <12位hex>`

## Benchmark 集成

配合 `generate_workspace.py` 可生成多套任务变体：

```bash
python3 generate_workspace.py
# 生成 cases/ws_1/, cases/ws_2/, ... 每个包含独立的 check 和 token
```

Benchmark 脚本读取 `expected_token.json`，监控 Agent 输出中是否出现 `TOKEN: xxx` 来判断通过。

## 藏在样板里的规则（组织方参考，不下发给 Agent）

1. 去掉「备注」「录入人」列，「单价」重命名为「总价」
2. 日期从 `2026/7/3` 转为 `2026-07-03`（YYYY-MM-DD，零填充）
3. 总价 = 数量 × 单价，ROUND_HALF_UP 保留 2 位小数
4. 数量缺失 → 补 0，总价 = 0.00
5. 排序仅按「站点」升序，同一站点保持输入相对顺序
6. 末尾追加合计行：编号列="合计"，数量和总价求和，其余字段留空
7. 输出 UTF-8 编码，LF 换行，文件末尾换行

## 打分参考

```text
得分 = (exp / actual_rounds) × 20
exp = 8  → 首次探索，预期形成规则与处理脚本
```

## 与完整版 D-Track 对比

| 维度 | D-Simple | D-Track（完整版） |
|------|----------|-------------------|
| 题目数 | 3 | 3 |
| 样板数 | 每题 2 组 | D1:3, D2:3, D3:2 |
| 规则变化 | 三题规则完全相同 | 列名/日期/精度跨题变化 |
| 自进化考察 | ✅（跨题复用SOP） | 有（跨题复用） |
| Token 机制 | ✅ | 待添加 |
| 评测脚本 | `./check` | `verify_d.py` |
