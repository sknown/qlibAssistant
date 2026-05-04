#!/usr/bin/env python3
"""
生成量化选股历史预测列表页(固定网页)
读取所有 selection_* 目录，按预测日期分组，生成列表式 HTML 页面。
"""
import re
import sys
from pathlib import Path
from datetime import datetime
from collections import OrderedDict
from typing import Optional

import pandas as pd
import numpy as np

ANALYSIS_DIR = Path.home() / ".qlibAssistant" / "analysis"
OUTPUT_FILE = ANALYSIS_DIR / "history_list.html"


# ========== 股票名称映射 ==========

def get_stock_name_map() -> dict:
    """获取股票名称映射表"""
    try:
        from utils import get_normalized_stock_list
        df = get_normalized_stock_list()
        if df is not None and "code" in df.columns and "name" in df.columns:
            name_map = {}
            for _, row in df.iterrows():
                code = str(row["code"]).strip()
                name = str(row["name"]).strip()
                if code and name and code != "nan" and name != "nan":
                    code_clean = code.lower().strip()
                    name_map[code_clean] = name
            return name_map
    except Exception as e:
        print(f"  ⚠️ 股票名称获取失败: {e}")
    return {}


# ========== 数据加载 ==========

def load_selection_dirs() -> list:
    """加载所有 selection 目录，返回排序后的列表(新→旧)"""
    dirs = sorted(ANALYSIS_DIR.glob("selection_*"), reverse=True)
    return dirs


def parse_ret_filename(ret_path: Path) -> Optional[str]:
    """从 *_ret.csv 文件名提取预测日期，如 2026-04-30_ret.csv → 2026-04-30"""
    m = re.match(r"(\d{4}-\d{2}-\d{2})_ret\.csv", ret_path.name)
    if m:
        return m.group(1)
    return None


def load_selection_data(sel_dir: Path) -> Optional[dict]:
    """加载单个 selection 目录的数据"""
    ret_files = list(sel_dir.glob("*_ret.csv"))
    filter_files = list(sel_dir.glob("*_filter_ret.csv"))
    if not ret_files or not filter_files:
        return None

    pred_date = parse_ret_filename(ret_files[0])
    if not pred_date:
        return None

    ret = pd.read_csv(ret_files[0])
    filtered = pd.read_csv(filter_files[0])

    return {
        "dir_name": sel_dir.name,
        "pred_date": pred_date,
        "ret": ret,
        "filtered": filtered,
    }


def group_by_date(selections: list) -> OrderedDict:
    """按预测日期分组，同日期只保留最新的 selection"""
    date_groups = {}
    for s in selections:
        date = s["pred_date"]
        if date not in date_groups:
            date_groups[date] = s
        # 已存在时保留先遍历到的(目录名按倒序，先遍历到的是最新的)
    # 按日期倒序排列
    result = OrderedDict()
    for date in sorted(date_groups.keys(), reverse=True):
        result[date] = date_groups[date]
    return result


# ========== HTML 生成 ==========

def numeric_style(val, fmt="{:.4f}") -> str:
    """数字着色"""
    if pd.isna(val):
        return '<span style="color:#999">-</span>'
    color = "#198038" if val > 0 else "#da1e28" if val < 0 else "#333"
    return f'<span style="color:{color};font-weight:500">{fmt.format(val)}</span>'


def score_bar(val, max_val=0.08) -> str:
    """评分可视化条"""
    pct = min(abs(val) / max(abs(max_val), 1e-9) * 100, 100)
    if val >= 0:
        return (f'<div style="background:#e6f7ec;border-radius:3px;position:relative;'
                f'width:100px;height:18px;display:inline-block;vertical-align:middle">'
                f'<div style="background:#24a148;width:{pct:.0f}%;height:100%;'
                f'border-radius:3px"></div>'
                f'<span style="position:absolute;left:4px;top:0;font-size:10px;'
                f'color:#333">{val:.4f}</span></div>')
    else:
        return (f'<div style="background:#fce8e8;border-radius:3px;position:relative;'
                f'width:100px;height:18px;display:inline-block;vertical-align:middle">'
                f'<div style="background:#da1e28;width:{pct:.0f}%;height:100%;'
                f'border-radius:3px"></div>'
                f'<span style="position:absolute;left:4px;top:0;font-size:10px;'
                f'color:#fff">{val:.4f}</span></div>')


def consensus_badge(ratio) -> str:
    """共识度标签"""
    if pd.isna(ratio):
        return '<span style="color:#999">-</span>'
    if ratio >= 0.9:
        return '<span style="background:#002d9c;color:#fff;padding:1px 6px;border-radius:8px;font-size:11px;font-weight:600">极高</span>'
    elif ratio >= 0.75:
        return '<span style="background:#0043ce;color:#fff;padding:1px 6px;border-radius:8px;font-size:11px">高</span>'
    elif ratio >= 0.5:
        return '<span style="background:#a6c8ff;color:#001d6c;padding:1px 6px;border-radius:8px;font-size:11px">中</span>'
    else:
        return '<span style="background:#e0e0e0;color:#333;padding:1px 6px;border-radius:8px;font-size:11px">低</span>'


def generate_date_section(data: dict, name_map: dict) -> str:
    """生成单个预测日期的 HTML 段落"""
    ret = data["ret"]
    filtered = data["filtered"]
    pred_date = data["pred_date"]

    total = len(ret)
    filter_count = len(filtered)
    pass_rate = filter_count / total * 100 if total else 0
    avg_score = ret["avg_score"].mean()
    max_score = ret["avg_score"].max()
    run_time = data["dir_name"].replace("selection_", "").replace("_", ":")

    # Top 10
    top10 = filtered.sort_values("avg_score", ascending=False).head(10)

    lines = []
    lines.append(f"""
<div class="date-block">
  <div class="date-header">
    <div class="date-title">
      <span class="date-label">{pred_date}</span>
      <span class="date-badge">{data["dir_name"]}</span>
    </div>
    <div class="date-meta">运行时间: {run_time}</div>
  </div>
  <div class="date-summary">
    <div class="s-item"><span class="s-num">{total}</span><span class="s-label">覆盖</span></div>
    <div class="s-item"><span class="s-num green">{filter_count}</span><span class="s-label">入选</span></div>
    <div class="s-item"><span class="s-num orange">{pass_rate:.1f}%</span><span class="s-label">通过率</span></div>
    <div class="s-item"><span class="s-num">{avg_score:.4f}</span><span class="s-label">平均分</span></div>
    <div class="s-item"><span class="s-num green">{max_score:.4f}</span><span class="s-label">最高分</span></div>
  </div>
""")

    # 共识度分布
    all_pos = (filtered["pos_ratio"] == 1.0).sum()
    high = ((filtered["pos_ratio"] >= 0.75) & (filtered["pos_ratio"] < 1.0)).sum()
    mid = ((filtered["pos_ratio"] >= 0.5) & (filtered["pos_ratio"] < 0.75)).sum()
    low = (filtered["pos_ratio"] < 0.5).sum()

    lines.append(f"""  <div class="consensus-bar">
    <span class="c-label">共识分布:</span>
    <span class="c-item" style="background:#002d9c;color:#fff">全部 {all_pos}</span>
    <span class="c-item" style="background:#0043ce;color:#fff">高 {high}</span>
    <span class="c-item" style="background:#a6c8ff;color:#001d6c">中 {mid}</span>
    <span class="c-item" style="background:#e0e0e0;color:#333">低 {low}</span>
  </div>
""")

    # 评分分布
    bins = [-np.inf, -0.05, -0.02, -0.01, 0, 0.01, 0.02, 0.05, np.inf]
    labels = ["<-5%", "-5%~-2%", "-2%~-1%", "-1%~0%", "0%~1%", "1%~2%", "2%~5%", ">5%"]
    ret_range = ret.copy()
    ret_range["score_range"] = pd.cut(ret_range["avg_score"], bins=bins, labels=labels)
    dist = ret_range["score_range"].value_counts().sort_index()

    max_dist = dist.max() if dist.max() > 0 else 1
    lines.append("""  <div class="dist-section">
    <div class="dist-header">评分分布</div>
    <div class="dist-grid">
""")
    for label, count in dist.items():
        width = count / max_dist * 100
        lines.append(f"""      <div class="dist-row">
        <span class="dist-label">{label}</span>
        <div class="dist-track"><div class="dist-fill" style="width:{width:.0f}%"></div></div>
        <span class="dist-num">{count}</span>
      </div>
""")
    lines.append("    </div>\n  </div>\n")

    # Top 10 列表
    lines.append(f"""  <div class="top-section">
    <div class="top-header">🏆 Top 10 推荐</div>
    <table class="top-table">
      <thead>
        <tr>
          <th>#</th><th>代码</th><th>名称</th><th>评分</th><th>共识</th>
          <th>ROC10</th><th>ROC20</th><th>STD5</th><th>STD20</th>
        </tr>
      </thead>
      <tbody>
""")

    for i, (_, row) in enumerate(top10.iterrows(), 1):
        code = row["instrument"]
        name = name_map.get(code, "")
        roc10 = numeric_style(row.get("ROC10", np.nan), "{:.3f}")
        roc20 = numeric_style(row.get("ROC20", np.nan), "{:.3f}")
        std5 = numeric_style(row.get("STD5", np.nan), "{:.4f}")
        std20 = numeric_style(row.get("STD20", np.nan), "{:.4f}")

        # 行着色：Top3 金色
        row_class = "top-row" if i <= 3 else ""
        lines.append(f"""        <tr class="{row_class}">
          <td>{i}</td>
          <td><strong>{code}</strong></td>
          <td>{name}</td>
          <td>{score_bar(row["avg_score"])}</td>
          <td>{consensus_badge(row["pos_ratio"])}</td>
          <td>{roc10}</td>
          <td>{roc20}</td>
          <td>{std5}</td>
          <td>{std20}</td>
        </tr>
""")

    lines.append("""      </tbody>
    </table>
  </div>
</div>
""")

    return "\n".join(lines)


def generate_html(date_data: OrderedDict, name_map: dict, total_runs: int = 0) -> str:
    """生成完整 HTML 页面"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    total_dates = len(date_data)
    total_selections = total_runs if total_runs > 0 else len(date_data)
    total_stocks_all = sum(len(v["ret"]) for v in date_data.values())
    total_filtered_all = sum(len(v["filtered"]) for v in date_data.values())

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>量化选股历史预测列表</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#f5f7fa; color:#1a1a1a; font-size:14px; line-height:1.6 }}
.container {{ max-width:1100px; margin:0 auto; padding:24px 16px }}

/* Header */
.header {{ background:linear-gradient(135deg,#001d6c,#0043ce); color:#fff; border-radius:12px; padding:32px; margin-bottom:24px }}
.header h1 {{ font-size:26px; margin-bottom:8px; font-weight:700 }}
.header .sub {{ opacity:.85; font-size:14px }}
.header .date {{ margin-top:8px; font-size:13px; opacity:.7 }}
.header .stats {{ display:flex; gap:20px; margin-top:16px; flex-wrap:wrap }}
.header .stats .st {{ background:rgba(255,255,255,.12); padding:8px 16px; border-radius:8px; text-align:center }}
.header .stats .st .num {{ font-size:22px; font-weight:700 }}
.header .stats .st .label {{ font-size:11px; opacity:.75 }}

/* Date Block */
.date-block {{ background:#fff; border-radius:10px; padding:20px; margin-bottom:16px; box-shadow:0 1px 4px rgba(0,0,0,.06) }}
.date-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:8px }}
.date-title {{ display:flex; align-items:center; gap:10px }}
.date-label {{ font-size:22px; font-weight:700; color:#001d6c }}
.date-badge {{ background:#e8edf5; color:#001d6c; font-size:11px; padding:2px 8px; border-radius:4px; font-family:monospace }}
.date-meta {{ font-size:12px; color:#999 }}

/* Summary */
.date-summary {{ display:flex; gap:12px; margin-bottom:10px; flex-wrap:wrap }}
.s-item {{ background:#f8f9fb; border-radius:6px; padding:8px 14px; text-align:center; min-width:70px }}
.s-item .s-num {{ font-size:18px; font-weight:700; color:#001d6c }}
.s-item .s-num.green {{ color:#198038 }}
.s-item .s-num.orange {{ color:#e67e22 }}
.s-item .s-label {{ font-size:11px; color:#666; display:block; margin-top:2px }}

/* Consensus */
.consensus-bar {{ display:flex; align-items:center; gap:6px; margin-bottom:12px; flex-wrap:wrap }}
.consensus-bar .c-label {{ font-size:12px; color:#666; margin-right:4px }}
.consensus-bar .c-item {{ padding:2px 8px; border-radius:6px; font-size:11px }}

/* Distribution */
.dist-section {{ margin-bottom:12px }}
.dist-header {{ font-size:13px; font-weight:600; color:#001d6c; margin-bottom:6px }}
.dist-grid {{ display:flex; flex-direction:column; gap:3px }}
.dist-row {{ display:flex; align-items:center; gap:8px }}
.dist-label {{ width:65px; font-size:11px; color:#555; text-align:right }}
.dist-track {{ flex:1; height:16px; background:#f0f0f0; border-radius:3px; overflow:hidden }}
.dist-fill {{ height:100%; background:#0043ce; border-radius:3px; transition:width .3s }}
.dist-num {{ width:28px; font-size:11px; color:#333; text-align:right }}

/* Top Section */
.top-section {{ margin-top:4px }}
.top-header {{ font-size:15px; font-weight:600; color:#001d6c; margin-bottom:8px }}
.top-table {{ width:100%; border-collapse:collapse; font-size:13px }}
.top-table th {{ background:#f0f4ff; color:#001d6c; padding:8px 6px; text-align:left; font-weight:600; white-space:nowrap; border-bottom:2px solid #d0d9f0; font-size:12px }}
.top-table td {{ padding:6px; border-bottom:1px solid #eee; white-space:nowrap }}
.top-table tr:hover {{ background:#f8faff }}
.top-table .top-row {{ background:#fffdf0 }}
.top-table .top-row td {{ border-bottom-color:#f0e6b8 }}

/* Scroll hint */
.scroll-hint {{ font-size:12px; color:#999; text-align:right; padding:2px 0 6px }}

/* Responsive */
.table-wrap {{ overflow-x:auto }}
@media (max-width:768px) {{ .date-summary {{ gap:6px }} .s-item {{ min-width:55px; padding:6px 8px }} .s-item .s-num {{ font-size:15px }} }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>📊 量化选股历史预测列表</h1>
  <div class="sub">基于多模型集成加权投票 · Alpha158 因子 · 稳健性过滤</div>
  <div class="date">生成时间: {now}</div>
  <div class="stats">
    <div class="st"><div class="num">{total_dates}</div><div class="label">预测日期</div></div>
    <div class="st"><div class="num">{total_selections}</div><div class="label">运行次数</div></div>
    <div class="st"><div class="num">{total_stocks_all}</div><div class="label">累计评测</div></div>
    <div class="st"><div class="num">{total_filtered_all}</div><div class="label">累计入选</div></div>
  </div>
</div>
"""

    for pred_date, data in date_data.items():
        html += generate_date_section(data, name_map)

    html += """
<div style="text-align:center;padding:20px;color:#999;font-size:12px">
由 QlibAssistant 自动生成 · 仅供参考，不构成投资建议
</div>
</div>
</body>
</html>"""
    return html


# ========== 主流程 ==========

def main():
    print("📥 加载股票名称...")
    name_map = get_stock_name_map()
    print(f"   ✅ 获取到 {len(name_map)} 只股票名称")

    print("📂 加载所有历史 selection 数据...")
    sel_dirs = load_selection_dirs()
    if not sel_dirs:
        print("   ❌ 未找到 selection 目录")
        return
    print(f"   ✅ 发现 {len(sel_dirs)} 个 selection 目录")

    selections = []
    for d in sel_dirs:
        data = load_selection_data(d)
        if data:
            selections.append(data)
            print(f"   📄 {d.name} → 预测日期: {data['pred_date']}, "
                  f"覆盖 {len(data['ret'])} 只, 入选 {len(data['filtered'])} 只")

    date_data = group_by_date(selections)
    print(f"\n   ✅ 按日期分组后: {len(date_data)} 个预测日期")
    for date, data in date_data.items():
        print(f"      {date} ← {data['dir_name']}")

    print("\n📝 生成页面...")
    html = generate_html(date_data, name_map, total_runs=len(selections))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"\n✅ 历史列表页已生成: {OUTPUT_FILE}")
    print(f"📎 请在浏览器中打开查看: file://{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
