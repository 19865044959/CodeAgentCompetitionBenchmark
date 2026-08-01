#!/bin/bash
# ============================================================
# 自进化 Benchmark 运行器
# 1. 启动 API 服务
# 2. 运行 GA benchmark
# 3. 停止 API 服务
# 4. 输出报告
# ============================================================
set -e

API_DIR="/mnt/d/work/CodeAgentCompetitionBenchmark/self_evolution_a_api"
TEMP_DIR="/mnt/d/work/temp"
GA_DIR="/mnt/d/work/Hackthon/GenericAgent"

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================"
echo "  Agent 自进化 Benchmark"
echo "============================================"
echo ""

# ── 1. 清理旧数据 ──────────────────────────────────────
echo -e "${YELLOW}[1/5] 清理旧数据...${NC}"
rm -f "$TEMP_DIR"/answer_[123].json
rm -f "$TEMP_DIR"/benchmark_report_*.json
fuser -k 8899/tcp 2>/dev/null || true
sleep 0.5

# ── 2. 启动 API 服务 ────────────────────────────────────
echo -e "${YELLOW}[2/5] 启动 API 服务...${NC}"
"$API_DIR/nchda_server" > /tmp/nchda_server.log 2>&1 &
API_PID=$!
sleep 1

# 验证 API 是否就绪
if curl -s "http://localhost:8899/api/v1/heritage/search?location=北京" > /dev/null 2>&1; then
    echo -e "${GREEN}  API 服务已就绪 (PID: $API_PID)${NC}"
else
    echo -e "${RED}  API 服务启动失败!${NC}"
    cat /tmp/nchda_server.log
    exit 1
fi

# ── 3. 确保任务文件和 API 文档就位 ──────────────────────
echo -e "${YELLOW}[3/5] 检查任务文件...${NC}"
for f in task_1_beijing.md task_2_nanjing.md task_3_chengdu.md API_DOCS.md; do
    if [ -f "$TEMP_DIR/$f" ]; then
        echo "  ✓ $f"
    else
        echo -e "${RED}  ✗ $f 缺失!${NC}"
        exit 1
    fi
done

# ── 4. 运行 Benchmark ──────────────────────────────────
echo -e "${YELLOW}[4/5] 运行 Benchmark...${NC}"
echo "  (预计需要 3-10 分钟)"
echo ""

cd "$GA_DIR"
python3 "$API_DIR/run_benchmark.py" "$@"
BENCH_EXIT=$?

echo ""

# ── 5. 停止 API 服务 ────────────────────────────────────
echo -e "${YELLOW}[5/5] 停止 API 服务...${NC}"
kill $API_PID 2>/dev/null || fuser -k 8899/tcp 2>/dev/null
echo "  API 服务已停止"

# ── 最终报告摘要 ────────────────────────────────────────
if [ $BENCH_EXIT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}Benchmark 完成!${NC}"
else
    echo ""
    echo -e "${RED}Benchmark 异常退出 (code: $BENCH_EXIT)${NC}"
fi

exit $BENCH_EXIT
