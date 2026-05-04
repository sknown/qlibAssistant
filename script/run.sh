#!/bin/bash
# ==========================================
# QlibAssistant 一键流水线
# ==========================================
# 手动用法:
#   bash script/run.sh                      # 全流程（更新+训练+预测+报告）
#   bash script/run.sh --skip-train         # 跳过训练（快速预测）
#   bash script/run.sh --skip-data          # 跳过数据更新
#   bash script/run.sh --predict-only       # 只预测+报告
#
# 定时调度用法 (配合 crontab):
#   bash script/run.sh --first-run          # 每天首次：全流程（含训练）
#   bash script/run.sh --schedule           # 非首次：只更新数据+预测（跳过训练）
# ==========================================

set -e
cd "$(dirname "$0")/.."
DIR=$(pwd)

TRAIN_MARKER="/tmp/qlib_trained_today"
SKIP_TRAIN=false
SKIP_DATA=false
SCHEDULE_MODE=false
FIRST_RUN=false

for arg in "$@"; do
  case "$arg" in
    --skip-train)   SKIP_TRAIN=true  ;;
    --skip-data)    SKIP_DATA=true   ;;
    --predict-only) SKIP_TRAIN=true; SKIP_DATA=true ;;
    --first-run)    FIRST_RUN=true  ;;
    --schedule)     SCHEDULE_MODE=true ;;
    --help|-h)
      echo ""
      echo "╔══════════════════════════════════════════════╗"
      echo "║  QlibAssistant 一键流水线                     ║"
      echo "╚══════════════════════════════════════════════╝"
      echo ""
      echo "用法: bash script/run.sh [选项]"
      echo ""
      echo "手动选项:"
      echo "  (无参数)           全流程（更新+训练+预测+报告）"
      echo "  --skip-train       跳过模型训练（用已有模型快速预测）"
      echo "  --skip-data        跳过数据更新"
      echo "  --predict-only     只跑预测+报告"
      echo ""
      echo "定时调度选项 (配合 crontab 使用):"
      echo "  --first-run        每天首次运行：全流程（含训练）"
      echo "  --schedule         非首次运行：只更新+预测（跳过训练）"
      echo ""
      echo "crontab 配置示例:"
      echo "  # 交易日 9:30~15:00 每小时运行"
      echo "  30 9 * * 1-5 $(cd "$(dirname "$0")" && pwd)/run.sh --first-run"
      echo "  30 10,11 * * 1-5 $(cd "$(dirname "$0")" && pwd)/run.sh --schedule"
      echo "  0 13,14,15 * * 1-5 $(cd "$(dirname "$0")" && pwd)/run.sh --schedule"
      echo ""
      exit 0
      ;;
  esac
done

# ── 调度模式逻辑 ──
if [ "$SCHEDULE_MODE" = true ]; then
  TODAY=$(date +%Y-%m-%d)
  if [ -f "$TRAIN_MARKER" ] && [ "$(cat "$TRAIN_MARKER")" = "$TODAY" ]; then
    echo "  今天已训练过，跳过训练"
    SKIP_TRAIN=true
  else
    echo "  今天尚未训练，执行全流程"
    FIRST_RUN=true
  fi
fi

if [ "$FIRST_RUN" = true ]; then
  SKIP_TRAIN=false
  SKIP_DATA=false
fi

# 激活虚拟环境
source "$DIR/.venv/bin/activate"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     QlibAssistant 一键流水线                  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "运行模式: $([ "$SKIP_TRAIN" = false ] && [ "$SKIP_DATA" = false ] && echo '全流程 (含训练)' || (echo '快速更新') )"
echo ""

step() {
  echo ""
  echo "========================================"
  echo "  [$(date +%H:%M:%S)] $1"
  echo "========================================"
}

cd "$DIR/roll"

# ── Step 1: 数据更新 ──
if [ "$SKIP_DATA" = false ]; then
  step "Step 1/5: 更新行情数据"
  python roll.py data update
else
  echo "  跳过数据更新"
fi

# ── Step 2: 训练模型 ──
if [ "$SKIP_TRAIN" = false ]; then
  step "Step 2/5: 训练模型（约 5~30 分钟）"
  python roll.py train start_custom
  step "  压缩模型包"
  python roll.py model compress_mlruns

  # 标记今天已训练
  date +%Y-%m-%d > "$TRAIN_MARKER"
  echo "  已记录训练标记: $TRAIN_MARKER"
else
  echo "  跳过训练"
fi

# ── Step 3: 模型预测 ──
step "Step 3/5: 模型预测选股（约 3~10 分钟）"
python roll.py model selection

# ── Step 4: 生成报告 ──
step "Step 4/5: 生成可视化报告"
python gen_report.py

# ── Step 5: 生成历史列表页 ──
step "Step 5/5: 生成历史预测列表页"
python gen_history_page.py

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  ✅ 完成！报告已生成                          ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  报告: ~/.qlibAssistant/analysis/reports/"
echo "  历史列表: ~/.qlibAssistant/analysis/history_list.html"
echo "  数据: ~/.qlib/qlib_data/cn_data/"
echo "  模型: ~/.qlibAssistant/mlruns/"
echo ""
echo "  下一轮提示:"
echo "  今天内再次运行: bash $0 --schedule"
echo "  明天首次运行:  bash $0 --first-run"
echo ""
