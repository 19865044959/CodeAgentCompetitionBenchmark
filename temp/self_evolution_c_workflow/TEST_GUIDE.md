# C 类本地测试

## C-1

创建独立选手目录，只复制：

```text
task_c1.md 
PROCESS_DOCS.md
ERROR_CODES.md
MANUAL_R-700.md
runtime_c1.json
```

在该目录启动 Agent，完成后应生成：

```text
answer_c1.json
```

组织方判题：

```powershell
python .\verify_c.py --task 1 --submission-dir D:\你的选手目录
```

## C-2

不要清空选手目录。加入 `task_c2.md`

```text
runtime_c2.json
```

完成后判题：

```powershell
python .\verify_c.py --task 2 --submission-dir D:\你的选手目录
```

## C-3

不要清空选手目录。加入 `task_c3.md`

```text
MANUAL_T-50.md
runtime_c3.json
```

完成后判题：

```powershell
python .\verify_c.py --task 3 --submission-dir D:\你的选手目录
```

## 注意事项

- 三题必须按顺序进行；
- 不得向选手目录复制 `expected_c*.json` 或 `verify_c.py`；
- C-2、C-3 开始前不要删除 Agent 在此前任务中创建的脚本、配置或笔记；
- 判题通过时输出 `C-N: OK`；
