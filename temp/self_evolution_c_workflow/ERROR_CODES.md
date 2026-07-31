# 流程记录判题错误码

| 错误码 | 含义 |
|---|---|
| `E_MISSING` | 未找到当前题答案文件 |
| `E_JSON` | 答案不是合法 JSON |
| `E_SCHEMA` | 顶层结构或步骤对象结构不正确 |
| `E_SEQUENCE position=N` | 第 N 个步骤顺序错误 |
| `E_POWER` | power 步骤的型号或电压错误 |
| `E_SEED` | seed 步骤的频率种子错误 |
| `E_FREQUENCY` | tune 步骤的频率值或类型错误 |
| `E_PRECISION` | `freq` 保留小数位位数错误 |
| `E_AUTH` | auth 步骤的授权码错误 |
| `E_TRANSMIT` | transmit 步骤的授权码、坐标或 ACK 错误 |
| `E_LOG` | log 步骤的 ACK 或完成凭证错误 |

错误反馈不会返回正确步骤或正确字段值。
