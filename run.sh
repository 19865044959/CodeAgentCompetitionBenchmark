#!/usr/bin/env bash
# run.sh — 串行评测: 每个模型跑 n 遍
# 用法: bash run.sh <每模型遍数> <模型短名...>
#   例: bash run.sh 3 qwen3.5 qwen3.6 deepseek   → 3 个模型各 3 遍, 共 9 次评测
#
# 模型短名:
#   qwen3.5      = qwen3.5-35b-a3b    (Qwen3.5-35B-A3B)
#   qwen3.6      = qwen3.6-35b-a3b    (Qwen3.6-35B-A3B)
#   qwen3.6-27b  = qwen3.6-27b        (Qwen3.6-27B)
#   deepseek     = deepseek-v4-pro    (DeepSeek V4 Pro)
#
# 模型切换: qwen* 自动改 GA mykey.py 的 native_oai_config['model']
#          (三个 Qwen 共用同一个 DashScope key, 只换 model 即可);
#          deepseek 的 apibase/apikey/model 脚本不知道, 会暂停等你手动切完再继续。
# 输出: 每次评测自动新建 res/<model-id>/<YYYY-MM-DD-HHMM>/ (6 个 JSON + 1 个 MD),
#       全程 stdout 同时 tee 到 logs/serial_<时间戳>.log。
set -u

REPO="/mnt/d/work/CodeAgentCompetitionBenchmark"
BENCH="$REPO/run_benchmark.py"
GA_KEY="/mnt/d/work/Hackthon/GenericAgent/mykey.py"

declare -A MODEL_ID=(
    [qwen3.5]="qwen3.5-35b-a3b"
    [qwen3.6]="qwen3.6-35b-a3b"
    [qwen3.6-27b]="qwen3.6-27b"
    [deepseek]="deepseek-v4-pro"
)
declare -A MODEL_NAME=(
    [qwen3.5]="Qwen3.5-35B-A3B"
    [qwen3.6]="Qwen3.6-35B-A3B"
    [qwen3.6-27b]="Qwen3.6-27B"
    [deepseek]="DeepSeek V4 Pro"
)

if [ $# -lt 2 ]; then
    echo "用法: bash run.sh <每模型遍数> <模型短名...>"
    echo "  例: bash run.sh 3 qwen3.5 qwen3.6 deepseek   # 3 模型各 3 遍, 共 9 次"
    echo "  短名: ${!MODEL_ID[*]}"
    exit 1
fi
N="$1"; shift
if ! [[ "$N" =~ ^[0-9]+$ ]] || [ "$N" -lt 1 ]; then
    echo "错误: 遍数必须是正整数, 得到 '$N'"; exit 1
fi
for short in "$@"; do
    if [ -z "${MODEL_ID[$short]:-}" ]; then
        echo "错误: 未知模型短名 '$short' (可选: ${!MODEL_ID[*]})"; exit 1
    fi
done

mkdir -p "$REPO/logs"
LOGFILE="$REPO/logs/serial_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOGFILE") 2>&1

# 备份 mykey.py (每次 run.sh 调用只备份一次)
BAK="$GA_KEY.bak_$(date +%Y%m%d_%H%M%S)"
cp "$GA_KEY" "$BAK"
echo "mykey.py 已备份到 $BAK"

current_model() {
    grep -m1 "^[[:space:]]*'model':" "$GA_KEY" | sed "s/.*'\([^']*\)'[^']*$/\1/"
}

switch_qwen() {  # 自动把活跃 native_oai_config 的 model 行换成 $1
    local mid="$1" cur
    cur="$(current_model)"
    if [ "$cur" = "$mid" ]; then
        echo "  [GA] mykey.py 已是 $mid, 无需切换"
        return
    fi
    sed -i "s/^\\([[:space:]]*'model': \\)'[^']*'/\\1'$mid'/" "$GA_KEY"
    echo "  [GA] mykey.py model: '$cur' → '$(current_model)'"
}

total=0
for short in "$@"; do
    mid="${MODEL_ID[$short]}"
    mname="${MODEL_NAME[$short]}"
    echo ""
    echo "════════════════════════════════════════════════════════"
    echo " 模型 $mname ($mid), 串行跑 $N 遍"
    echo "════════════════════════════════════════════════════════"

    case "$short" in
        qwen*) switch_qwen "$mid" ;;
        deepseek)
            if grep -q "deepseek" "$GA_KEY"; then
                echo "  [GA] mykey.py 已含 deepseek 配置 (当前活跃 model: $(current_model))"
            fi
            if [ -t 0 ]; then
                echo "  [提示] 请手动把 $GA_KEY 的 apibase/apikey/model 切到 deepseek-v4-pro, 然后回车继续"
                read -r _
            else
                echo "  [警告] 非交互模式, 假定 mykey.py 已切好; 当前活跃 model: $(current_model)"
            fi
            ;;
    esac

    for i in $(seq 1 "$N"); do
        echo ""
        echo "── [$mid 第 $i/$N 遍] 开始 $(date '+%F %H:%M:%S') ──"
        python3 "$BENCH" --model-name "$mname" --model-id "$mid"
        rc=$?
        echo "── [$mid 第 $i/$N 遍] 结束 $(date '+%F %H:%M:%S') 退出码 $rc ──"
        total=$((total + 1))
    done
done

echo ""
echo "全部完成: 共 $total 次评测。报告在 $REPO/自进化类任务/res/<model-id>/ 下各自的日期文件夹里。"
echo "完整日志: $LOGFILE"
