# 应用 {name} 部署规范

## 目录要求
- logs/{name}/ 必须存在，权限为 755

## 配置文件 config/{name}.conf
- 第 3 行：`port {port}`
- 第 6 行：`name {svc_name}`

## 脚本要求
- bin/start.sh 必须存在且可执行（权限 755）
