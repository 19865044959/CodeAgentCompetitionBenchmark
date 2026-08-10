#!/bin/bash
# gamma 启动脚本
echo "Starting gamma on port 3000..."
exec python3 -m http.server 3000
