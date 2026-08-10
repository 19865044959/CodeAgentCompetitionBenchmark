#!/bin/bash
# alpha 启动脚本
echo "Starting alpha on port 8080..."
exec python3 -m http.server 8080
