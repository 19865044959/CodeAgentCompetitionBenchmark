#!/bin/bash
# {name} 启动脚本
echo "Starting {name} on port {port}..."
exec python3 -m http.server {port}
