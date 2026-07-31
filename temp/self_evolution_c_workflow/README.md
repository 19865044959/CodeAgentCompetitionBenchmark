# 自进化任务 — Track C：应急通信流程记录

## 赛题简介

你将作为荒野通信保障队的**流程记录员**，根据步骤档案、型号手册和当前运行记录，整理电台恢复过程并生成标准 JSON。

每道题都包含相同的 6 个步骤。公共档案会说明每一步的前置状态、完成状态、字段含义和对象格式，但不会直接给出正确执行顺序。选手需要在第 1 题中推导顺序并掌握频率格式，后续题继续使用同一流程。

## 考核目标

**自进化能力**：第 1 题中需要完成以下探索：

1. 根据 `REQUIRES` 和 `PRODUCES` 推导 6 个步骤的正确顺序；
2. 根据型号手册计算工作频率；
3. 注意 `freq` 必须是 JSON 数值，并恰好保留 1 位小数；
4. 按步骤模板生成完整答案。

后续题的流程顺序和 JSON 结构不变，只更换运行数据或型号参数。理想情况下，Agent 会在第 1 题后沉淀一份可复用的 Skill/SOP。

## 文件结构

```text
self_evolution_c_workflow/
├── README.md
├── PROCESS_DOCS.md
├── ERROR_CODES.md
├── MANUAL_R-700.md
├── MANUAL_T-50.md
├── task_c1.md
├── task_c2.md
├── task_c3.md
├── runtime_c1.json
├── runtime_c2.json
├── runtime_c3.json
├── expected_c1.json
├── expected_c2.json
├── expected_c3.json
└── verify_c.py
```

## 作答流程

1. 选手依次完成 `task_c1.md → task_c2.md → task_c3.md`；
2. 同组工作目录不重置，选手创建的脚本、配置和笔记可以跨题保留；
3. 每题读取 `PROCESS_DOCS.md`、当前型号手册和当前运行记录；
4. 生成：
   - C-1：`answer_c1.json`
   - C-2：`answer_c2.json`
   - C-3：`answer_c3.json`
5. 每份答案包含顶层 `task` 和 `execution`；
6. `execution` 中包含全部 6 个步骤，最后一个实际步骤产生 `done_code`。

## 任务梯度

```text
C-1：R-700，首次推导流程；频率结果为 168.0
C-2：R-700，流程和格式不变；更换运行数据，频率为 184.5
C-3：T-50，流程和格式不变；切换额定电压和频率公式，频率为 138.5
```

三题的频率均可精确表示为 1 位小数，不涉及四舍五入。

## 打分参考

```text
得分 = (exp / actual_rounds) × 20

C-1: exp = 8  → 首次探索顺序和频率格式
C-2: exp = 3  → 应直接复用流程模板
C-3: exp = 4  → 应复用流程，仅切换型号参数
```

实际 `exp` 应根据目标 Agent 的赛前测试结果标定。

## 自进化提示

同组工作目录不会重置。选手可以在 C-1 中自行留下流程模板、型号配置、频率计算程序或答案自检器，并在后续题中继续使用。

典型的 Skill/SOP 可以包含：

```text
radio_sop.py       流程记录生成器
models.json        型号电压与频率公式
flow_notes.md      已确认的步骤顺序和格式规则
check_answer.py    输出结构与数据传递自检
```

这些本地产物不能写死某一题的 seed、授权码、ACK、DONE 码或坐标。
