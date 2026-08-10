# 应用 gamma 部署规范

## 目录要求
- logs/gamma/ 必须存在，权限为 755

## 配置文件 config/gamma.conf
- 第 3 行：`port 3000`
- 第 6 行：`name gamma-daemon`

## 脚本要求
- bin/start.sh 必须存在且可执行（权限 755）
