# 应用 beta 部署规范

## 目录要求
- logs/beta/ 必须存在，权限为 755

## 配置文件 config/beta.conf
- 第 3 行：`port 9090`
- 第 6 行：`name beta-svc`

## 脚本要求
- bin/start.sh 必须存在且可执行（权限 755）
