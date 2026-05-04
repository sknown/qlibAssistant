#!/usr/bin/env python3
"""
一键全流程脚本：更新数据 → 训练模型 → 预测选股 → 生成报告

用法：
  cd /Users/huironglin/prj/ai/qlibAssistant
  source .venv/bin/activate
  python script/pipeline.py              # 跑全流程
  python script/pipeline.py --skip-train # 跳过训练（只用已有模型预测）
  python script/pipeline.py --skip-data  # 跳过数据更新
"""

import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ROLL_DIR = BASE_DIR / "roll"
VENV_PYTHON = BASE_DIR / ".venv" / "bin" / "python"


def log(msg):
    t = time.strftime("%H:%M:%S")
    print(f"\n{'='*56}")
    print(f"  [{t}] {msg}")
    print(f"{'='*56}")


def run(cmd, cwd=None):
    """执行命令，实时输出"""
    print(f"  $ {cmd}")
    proc = subprocess.run(cmd, shell=True, cwd=cwd or BASE_DIR)
    if proc.returncode != 0:
        print(f"  ⚠️  命令退出码: {proc.returncode}")
        return False
    return True


def main():
    skip_train = "--skip-train" in sys.argv
    skip_data = "--skip-data" in sys.argv

    print("""
╔══════════════════════════════════════════════╗
║     QlibAssistant 一键全流程流水线            ║
╚══════════════════════════════════════════════╝
""")

    # ── Step 1: 更新数据 ──
    if not skip_data:
        log("Step 1/6: 更新行情数据")
        if not run(f"{VENV_PYTHON} roll.py data update", cwd=ROLL_DIR):
            print("  ❌ 数据更新失败，终止流程")
            return
    else:
        log("Step 1/6: 跳过数据更新")

    # ── Step 2: 训练模型 ──
    if not skip_train:
        log("Step 2/6: 训练模型 (5个模型 × 滚动窗口)")
        print("  预计耗时: 5~30 分钟，取决于机器性能")
        if not run(f"{VENV_PYTHON} roll.py train start_custom", cwd=ROLL_DIR):
            print("  ⚠️  部分模型训练失败，继续后续步骤...")
    else:
        log("Step 2/6: 跳过训练")

    # ── Step 3: 压缩模型 ──
    log("Step 3/6: 压缩模型包")
    run(f"{VENV_PYTHON} roll.py model compress_mlruns", cwd=ROLL_DIR)

    # ── Step 4: 模型预测 ──
    log("Step 4/6: 模型预测选股 (model selection)")
    print("  预计耗时: 3~10 分钟")
    if not run(f"{VENV_PYTHON} roll.py model selection", cwd=ROLL_DIR):
        print("  ❌ 预测失败")
        return

    # ── Step 5: 生成报告 ──
    log("Step 5/6: 生成可视化报告")
    run(f"{VENV_PYTHON} gen_report.py", cwd=ROLL_DIR)

    # ── Step 6: 生成历史列表页 ──
    log("Step 6/6: 生成历史预测列表页")
    run(f"{VENV_PYTHON} gen_history_page.py", cwd=ROLL_DIR)

    print("""
╔══════════════════════════════════════════════╗
║  ✅  全流程执行完成！                         ║
╚══════════════════════════════════════════════╝
""")

    # 列出输出文件
    reports = sorted((Path.home() / ".qlibAssistant" / "analysis" / "reports").glob("*.html"))
    if reports:
        print(f"  最新报告: {reports[-1]}")
    history_page = Path.home() / ".qlibAssistant" / "analysis" / "history_list.html"
    if history_page.exists():
        print(f"  历史列表: {history_page}")
    print(f"  分析目录: ~/.qlibAssistant/analysis/")


if __name__ == "__main__":
    main()
