# 推理类 & 长上下文类 Benchmark

> 基于《荒野求生》v6.0 游戏世界观设计
> 测试 GA（GenericAgent）的两项核心认知能力

---

## 一、测试目标

| 测试类别 | 游戏通道 | 核心能力 | 对应游戏机制 |
|----------|---------|---------|-------------|
| **推理类** | `worldNews.officialNews` | 经济因果推理 | 世界新闻导致矿石价格波动 → 套利策略 |
| **长上下文类** | `worldNews.folkLegends` | 跨天记忆与信息串联 | 民间传闻碎片拼凑 → 寻宝任务 |

---

## 二、目录结构

```
推理类&长上下文类/
├── README.md                          # 本文件
├── run_benchmark.py                   # Benchmark 运行器
│
├── reasoning/                         # 推理类测试
│   └── iron_price_speculation/        # 铁矿价格套利
│       ├── task.md                    # 任务描述（给 GA 阅读）
│       ├── game_state.json            # 模拟游戏状态（Day 1 首回合）
│       ├── ans/expected.json          # 期望答案
│       └── verify.py                  # 验证脚本
│
└── long_context/                      # 长上下文类测试
    └── treasure_hunt/                 # 民间传闻拼图寻宝
        ├── task.md                    # 任务描述（给 GA 阅读）
        ├── day_states/                # 每天的游戏状态
        │   ├── day1.json ~ day7.json  # Day 1-7 模拟状态
        ├── ans/expected.json          # 期望答案
        └── verify.py                  # 验证脚本
```

---

## 三、测试设计

### 3.1 推理类：铁矿价格套利

**游戏场景**：Day 1 早晨，世界新闻报导北部铁矿区发生矿井塌方事故，明天全面停工，修复需 2 天。

**测试 GA 是否能够**：
1. 从新闻中提取关键时间信息（今天可采 → 明天/后天停工 → 大后天恢复）
2. 推理因果链：停工 → 铁矿稀缺 → 小贩回收价格上涨（2 → 4 金币/单位）
3. 制定最优策略：Day 1 疯狂采集囤积 → Day 2-3 在高价窗口全部卖出 → Day 4 恢复正常

**评分维度（满分100，通过线70）**：

| 题目 | 分值 | 考察能力 |
|------|:---:|---------|
| Q1 价格预测 | 25 | 信息提取 + 时序推理 |
| Q2 囤积策略 | 25 | 前瞻性决策（涨价前囤货） |
| Q3 卖出策略 | 30 | 时序规划（在正确窗口执行正确操作） |
| Q4 利润分析 | 20 | 数学建模与策略总结 |

### 3.2 长上下文类：民间传闻拼图寻宝

**游戏场景**：Day 1-7 每天发布民间传闻，其中 Day 1/3/5/7 包含有效线索，Day 2/4/6 为纯噪声。

**测试 GA 是否能够**：
1. 从 7 条混杂传闻中识别出 4 条有效线索（不被噪声干扰）
2. 跨天串联同一物品的 4 种不同描述形式（代号→外貌→封印→凹槽→商品名）
3. 从隐晦表达推导坐标（"原点之北七、之东七" → (7,7)）
4. 制定完整行动计划（购买 → 移动 → detect）

**物品映射链**：

```
言者石(Day1) → 灰白刻字石板(Day3) → 真言之印(Day5) → 方槽(Day7) → 古符石板(15g)
光之尘(Day1) → 银白发光粉末(Day3) → 明光之印(Day5) → 圆碟(Day7) → 星辰之沙(20g)
焚之心(Day1) → 水晶瓶橙红雾(Day3) → 焚天之印(Day5) → 小孔焦痕(Day7) → 烈焰之息(25g)
```

**评分维度（满分100，通过线70）**：

| 题目 | 分值 | 能力层级 | 考察能力 |
|------|:---:|:---:|---------|
| Q1 信号识别 | 15 | Lv1 | 从噪声中识别有效信号 |
| Q2 物品映射 | 35 | Lv2-3 | 跨天四重映射 + 交叉验证 |
| Q3 位置推理 | 20 | Lv4 | 双重确认坐标位置 |
| Q4 行动计划 | 30 | Lv5 | 知道用detect触发祭坛 |

---

## 四、运行方式

### 4.1 前置条件

- GA 已部署在 `/mnt/d/work/Hackthon/GenericAgent/`
- GA 入口脚本为 `agentmain.py`
- GA 通过 stdin 接收任务文件路径，通过 stdout 输出执行日志
- Python 3.6+

### 4.2 运行全部测试

```bash
cd /mnt/d/work/CodeAgentCompetitionBenchmark/推理类\&长上下文类/
python3 run_benchmark.py
```

### 4.3 运行指定类型

```bash
# 仅运行推理类
python3 run_benchmark.py --type reasoning

# 仅运行长上下文类
python3 run_benchmark.py --type long_context
```

### 4.4 运行单个任务

```bash
python3 run_benchmark.py --task iron_price
python3 run_benchmark.py --task treasure_hunt
```

### 4.5 手动验证

```bash
# 推理类
cd reasoning/iron_price_speculation/
python3 verify.py /path/to/answer.json

# 长上下文类
cd long_context/treasure_hunt/
python3 verify.py /path/to/answer.json
```

### 4.6 自定义超时

```bash
python3 run_benchmark.py --timeout 1200  # 20分钟超时
```

---

## 五、GA 输出格式

GA 需要读取任务文件（`task.md`），分析后生成 `answer.json` 文件。

### 推理类 answer.json 格式

```json
{
  "task_id": "reasoning_iron_price",
  "answers": {
    "q1_price_prediction": {
      "reasoning": "...",
      "day1_price": 2,
      "day2_price": 4,
      "day3_price": 4,
      "day4_price": 2
    },
    "q2_hoarding_strategy": {
      "reasoning": "...",
      "day1_action": "collect_iron",
      "day1_priority": "high"
    },
    "q3_selling_strategy": {
      "reasoning": "...",
      "day2_action": "sell_all_iron",
      "day3_action": "sell_all_iron",
      "day4_action": "resume_normal"
    },
    "q4_profit_analysis": {
      "reasoning": "...",
      "max_profit_per_unit": 2,
      "optimal_strategy_summary": "Day1全力采集囤积，Day2-3高价卖出，Day4恢复"
    }
  }
}
```

### 长上下文类 answer.json 格式

```json
{
  "task_id": "long_context_treasure_hunt",
  "answers": {
    "q1_signal_detection": {
      "valid_days": [1, 3, 5, 7],
      "noise_days": [2, 4, 6]
    },
    "q2_item_identification": {
      "item_1": { "weapon_shop_item": "古符石板", "price": 15, ... },
      "item_2": { "weapon_shop_item": "星辰之沙", "price": 20, ... },
      "item_3": { "weapon_shop_item": "烈焰之息", "price": 25, ... }
    },
    "q3_location_deduction": {
      "target_x": 7,
      "target_y": 7
    },
    "q4_action_plan": {
      "required_items": ["古符石板", "星辰之沙", "烈焰之息"],
      "total_gold_needed": 60,
      "required_role": "pioneer",
      "final_action": "detect"
    }
  }
}
```

---

## 六、评估标准

### 6.1 推理类通过条件（总分 ≥ 70）

- ✅ **Lv1 信息提取**：正确识别新闻中"今天→明天停工→修2天"的时间链
- ✅ **Lv2 因果推理**：理解"停工→稀缺→涨价"的因果逻辑
- ✅ **Lv3 时序规划**：Day1囤→Day2-3卖→Day4恢复的正确动作序列
- ✅ **Lv4 利润计算**：正确计算套利利润 = (高价-基准价) × 数量

### 6.2 长上下文类通过条件（总分 ≥ 70）

- ✅ **Lv1 信号识别**：4条有效线索 + 3条噪声 → 全部分类正确
- ✅ **Lv2 跨天串联**：不因中间2天噪声而遗忘 Day1 的信息
- ✅ **Lv3 物品映射**：代号→外貌→封印→凹槽→商品 映射全对
- ✅ **Lv4 位置推理**：从"西行七里"(Day1) + "北七东七"(Day7) → (7,7)
- ✅ **Lv5 动作规划**：知道买齐三样 → 开拓者带 → detect 触发祭坛

### 6.3 GA 失败诊断

| 失败模式 | 原因分析 | 改进建议 |
|---------|---------|---------|
| Q1全错 | 无法理解世界新闻的因果含义 | 增加因果推理训练数据 |
| Q2/Q3时序错 | 能识别涨价但时机把握不对 | 加入时序规划能力训练 |
| 把噪声当天有效 | 缺乏信息筛选能力 | 加入噪声识别/信息重要性判断训练 |
| 物品映射断裂 | 跨天记忆丢失（遗忘早期信息） | 增强长上下文记忆/信息检索能力 |
| 知道物品但不知道detect | 不理解游戏机制 | 增加对action指令语义的理解 |

---

## 七、与游戏判题器的对应关系

本 Benchmark 模拟的是判题器通过 `worldNews` 字段推送信息后，GA 需要做出的**决策过程**：

| Benchmark 环节 | 对应游戏环节 |
|---------------|-------------|
| 阅读 task.md 中的世界新闻/民间传闻 | 判题器每回合 POST 的 `worldNews.officialNews` / `worldNews.folkLegends` |
| Q1-Q4 的推理与策略制定 | GA 内部决策：本回合各角色应执行什么 action |
| 生成 answer.json | GA 返回的 `roleCommandMap`（各角色指令） |
| verify.py 验证 | 判题器的预期行为 vs 实际行为的差异 |

在实际游戏中，推理类任务的正确行为表现为：
- **Day 1**：工人 → `collect` 铁矿（不 `sell`）
- **Day 2-3**：工人 → 移动到小贩 → `sell` 铁
- **Day 4+**：恢复正常采集节奏

长上下文类任务的正确行为表现为：
- **Day 1-7**：开拓者记住所有民间传闻
- **Day 7+**：开拓者 → 移动到武器商店(19,19) → `buy` 三样物品 → 移动到(7,7) → `detect`

---

## 八、扩展方向

### 8.1 推理类扩展

可设计更多新闻类型测试 GA 的经济推理泛化能力：

| 新闻类型 | 影响 |
|---------|------|
| 铜矿发现新矿脉 | 铜价下跌（供应增加） |
| 北方战事爆发 | 石头/铁涨价（军事需求增加） |
| 商路被山贼截断 | 多种矿石同时涨价（贸易受阻） |
| 新技术发明（炼金术） | 铜价暴涨（需求激增） |
| 矿区罢工结束 | 价格回落（供应恢复） |

### 8.2 长上下文类扩展

可设计不同主题的寻宝任务：

- 不同坐标（如(15,3)等）
- 不同物品组合（如寒霜药剂+荆棘护符+回音铁哨）
- 不同数量的有效天数（如3天碎片 + 4天噪声）
- 需要 `use` 指令的变体（如先使用某个物品才能激活）

---

## 九、参考资料

- 《荒野求生》v6.0 任务书 — 第五章节《任务》
- Agent 任务开发说明 v3.0 — 类型一、类型二
- 接口文档 v6.0 — `worldNews`、`vendorShopList`、`weaponShopList` 字段说明
