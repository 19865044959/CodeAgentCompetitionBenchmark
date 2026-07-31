# CSV 编码陷阱构建方法

## 1. UTF-8 BOM 陷阱

### 原理

BOM (Byte Order Mark) 是 UTF-8 文件头的 3 个字节 `EF BB BF`，Windows 的记事本保存 UTF-8 时会自动带上。
Python 的 `open(encoding='utf-8')` 不会自动去除，导致第一个列名变成 `﻿序号` 而不是 `序号`，
`DictReader` 按列名取数据时 KeyError。

### 构造（Python）

```python
import csv

data = [
    ["序号", "物品名称", "类别", "数量"],
    ["1", "铁锹", "工具", "50"],
]

# encoding='utf-8-sig' 写入会自带 BOM
with open("data.csv", "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    for row in data:
        writer.writerow(row)

# 验证 BOM 存在
with open("data.csv", "rb") as f:
    print(f.read(3).hex())  # 输出: efbbbf
```

### 构造（Shell）

```bash
# 方式1: printf 写入 BOM + 内容
printf '\xef\xbb\xbf序号,物品名称,类别,数量\n1,铁锹,工具,50\n' > data.csv

# 方式2: 用 Python 一行搞定
python3 -c "
import csv
with open('data.csv','w',encoding='utf-8-sig',newline='') as f:
    csv.writer(f).writerows([['序号','物品名称','类别','数量'],['1','铁锹','工具','50']])
"
```

### Agent 踩坑流程

```
第1轮: open('data.csv', encoding='utf-8')  → csv.DictReader → row['序号'] KeyError
第2轮: 打印 fieldnames，发现 ['﻿序号', ...]  → 意识到 BOM
第3轮: 改用 encoding='utf-8-sig' 或 fieldnames[0].lstrip('﻿')  → 修复
```

### 为什么 Agent 可能不会被拦住

现代 LLM 训练数据中大量出现 BOM + `utf-8-sig` 的代码片段，模型可能**自动使用 `utf-8-sig`** 读取 CSV，
绕过了这个坑。

---

## 2. GBK/GB2312 编码陷阱

### 原理

GBK 是中国大陆最常用的中文编码之一（Windows 中文版的默认 ANSI 编码）。
如果一个 CSV 文件用 GBK 编码保存，Python 用 `open(encoding='utf-8')` 读取时会抛出
`UnicodeDecodeError`，因为 GBK 的多字节序列不是合法的 UTF-8。

Agent 需要：
1. 看到报错后意识到是编码问题
2. 用 `chardet` 探测或用 `try/except` 逐个尝试常见编码（gbk, gb2312, gb18030, latin-1）
3. 找到正确编码后继续处理

### 构造（Python）

```python
import csv

data = [
    ["序号", "物品名称", "类别", "数量", "单位"],
    ["1", "铁锹", "工具", "50", "把"],
    ["2", "锤子", "工具", "30", "把"],
    # ... 必须包含中文以确保非 UTF-8 字节
]

# GBK 写入（注意：GBK 不能编码 BOM 字符 ﻿）
with open("data.csv", "w", encoding="gbk", newline="") as f:
    writer = csv.writer(f)
    for row in data:
        writer.writerow(row)

# Python 验证
with open("data.csv", "rb") as f:
    raw = f.read()
print(f"文件大小: {len(raw)} bytes")

# 确认 utf-8 读取会炸
try:
    with open("data.csv", encoding="utf-8") as f:
        f.read()
    print("没炸 — 文件中可能没有非ASCII字符")
except UnicodeDecodeError as e:
    print(f"✅ 陷阱就位: {e}")

# chardet 可以自动探测（Agent 可能会用）
import chardet
result = chardet.detect(raw)
print(f"chardet 探测: {result['encoding']} (置信度 {result['confidence']:.0%})")
```

### 构造（Shell + Python 一行）

```bash
# 用 Python 写入 GBK 编码的 CSV（保证中文列名）
python3 -c "
import csv
data = [
    ['序号','物品名称','类别','数量'],
    ['1','铁锹','工具','50'],
    ['2','锤子','工具','30'],
]
with open('data.csv','w',encoding='gbk',newline='') as f:
    csv.writer(f).writerows(data)
"
```

### 纯 Shell 方式（用 iconv）

```bash
# 先正常创建 UTF-8 文件
cat > /tmp/data_utf8.csv << 'EOF'
序号,物品名称,类别,数量
1,铁锹,工具,50
2,锤子,工具,30
EOF

# 转码为 GBK
iconv -f utf-8 -t gbk /tmp/data_utf8.csv > data.csv

# 验证
file data.csv
# data.csv: ISO-8859 text (或 Non-ISO extended-ASCII text)
```

### Agent 踩坑流程

```
第1轮: open('data.csv', encoding='utf-8')  → UnicodeDecodeError
第2轮: 用 file 命令或 hexdump 检查  → 确认不是 UTF-8
第3轮: 尝试 encoding='gbk' 或 import chardet  → 成功
第4轮: 正常处理数据
```

### 关键点

- **必须有中文内容**，纯 ASCII 的 GBK 文件就是合法的 UTF-8，不会触发错误
- `chardet` 能 99% 置信度自动识别 GB2312/GBK
- GBK/GB2312/GB18030 是兼容的：GB18030 ⊃ GBK ⊃ GB2312，选 gbk 通常够用

---

## 3. 两个陷阱的效果对比

| | BOM | GBK |
|---|---|---|
| 表现形式 | 静默 bug（列名错） | 直接报错（UnicodeDecodeError） |
| Agent 发现难度 | 中（KeyError 需要调试） | 低（错误直接暴露） |
| Agent 修复难度 | 低（一行改 encoding） | 中（需要知道正确的编码名） |
| LLM 肌肉记忆 | `utf-8-sig` 常见 | gbk/gb2312 较少见 |
| 跨文件复用性 | 脚本改了 encoding 后面都能用 | 同左 |
| 额外依赖 | 无 | 可能需要 chardet |
| 预计消耗 | 2-3 轮 | 3-4 轮 |

建议两个组合使用：BOM + GBK 双坑叠加（同时用 `utf-8-sig` + `gbk` 错误编码去读），让 Agent 面对"先处理 BOM 再处理编码"的二段问题。
