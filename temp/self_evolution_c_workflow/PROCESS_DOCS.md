# 荒野应急通信流程记录规范

## 1. 答案结构

每题答案包含两个顶层字段：

```json
{
  "task":
  "execution": [
    "<按照正确顺序填写全部步骤对象>"
  ]
}
```

| 字段 | 含义 |
|---|---|
| `task` | 当前任务编号，取自 `runtime_cN.json` |
| `execution` | 完整执行过程，包含全部 6 个步骤对象 |

---

## 2. 顺序推导规则

由于记录缺失，只记录了少部分前置状态和完成状态：

```text
REQUIRES=<执行前所需状态>
PRODUCES=<执行后产生状态>
```

推导方法：

1. 初始状态为 `idle`；
2. 选择 `REQUIRES` 等于当前状态的步骤；
3. 执行后，当前状态变为该步骤的 `PRODUCES`；
4. 每个步骤恰好使用一次；
5. 最终状态必须为 `done`。

下面的步骤按档案编号排列，**出现顺序不代表正确执行顺序**。

---

## 3. 无序步骤模板

### 档案 P-17：log

```text
REQUIRES=ack_ready
PRODUCES=done
```

含义：登记发送回执并产生最终完成凭证。

```json
{
  "step": "log",
  "request": {
    "ack": "<runtime 中的 ack>"
  },
  "response": {
    "done_code": "<runtime 中的 done_code>"
  }
}
```

- `done_code` 是本题完成凭证；
- `log` 完成后流程到达 `done`。

### 档案 P-04：tune


```json
{
  "step": "tune",
  "request": {
    "freq": 
  }
}
```

### 档案 P-21：auth


```json
{
  "step": "auth",
  "response": {
    "code": 
  }
}
```

### 档案 P-02：power

```json
{
  "step": "power",
  "request": {
    "model": ,
    "voltage": 
  }
}
```

### 档案 P-13：transmit


```json
{
  "step": "transmit",
  "request": {
    "code":,
    "coord": 
  },
  "response": {
    "ack": 
  }
}
```

### 档案 P-09：seed

```json
{
  "step": "seed",
  "response": {
    "freq_seed": 
  }
}
```

- `freq_seed` 取自当前运行记录；
- 该值用于计算 tune 步骤的 `freq`。

---
