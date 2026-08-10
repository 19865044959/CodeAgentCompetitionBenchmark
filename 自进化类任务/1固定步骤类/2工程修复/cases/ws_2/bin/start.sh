#!/bin/bash
# beta 启动脚本
echo "Starting beta on port 9090..."
exec python3 -m http.server 9090
