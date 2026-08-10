# 应用 alpha 部署规范

## 目录要求
- logs/alpha/ 必须存在，权限为 755

## 配置文件 config/alpha.conf
- 第 3 行：`port 8080`
- 第 6 行：`name alpha-app`

## 脚本要求
- bin/start.sh 必须存在且可执行（权限 755）
