#!/bin/bash
# ============================================================
# 自进化 Benchmark 运行器（文件修复类）
# 1. 生成工作区
# 2. 运行 GA benchmark
# 3. 输出报告
# ============================================================
set -e

BENCH_DIR="/mnt/d/work/CodeAgentCompetitionBenchmark/self_evolution_b_fix"
GA_DIR="/mnt/d/work/Hackthon/GenericAgent"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================"
echo "  Agent 自进化 Benchmark（文件修复类）"
echo "============================================"
echo ""

# ── 1. 清理旧数据 ──
echo -e "${YELLOW}[1/3] 清理旧数据...${NC}"
rm -rf /tmp/ws_[123]
rm -f /tmp/answer_[123].json
rm -f /tmp/benchmark_report_*.json

# ── 2. 部署工作区到 /tmp ──
echo -e "${YELLOW}[2/3] 部署工作区...${NC}"
cp -r "$BENCH_DIR/cases/ws_1" /tmp/ws_1
cp -r "$BENCH_DIR/cases/ws_2" /tmp/ws_2
cp -r "$BENCH_DIR/cases/ws_3" /tmp/ws_3
# 注入权限错误: start.sh 设为 644（应为 755）
chmod -R 755 /tmp/ws_[123]/
chmod 644 /tmp/ws_1/bin/start.sh /tmp/ws_2/bin/start.sh /tmp/ws_3/bin/start.sh
echo "  ws_1, ws_2, ws_3 已就绪"
echo ""

# ── 3. 运行 Benchmark ──
echo -e "${YELLOW}[3/3] 运行 Benchmark...${NC}"
cd "$GA_DIR"
python3 "$BENCH_DIR/run_benchmark.py" "$@"
BENCH_EXIT=$?

echo ""
if [ $BENCH_EXIT -eq 0 ]; then
    echo -e "${GREEN}Benchmark 完成!${NC}"
else
    echo -e "${RED}Benchmark 异常退出 (code: $BENCH_EXIT)${NC}"
fi
exit $BENCH_EXIT
