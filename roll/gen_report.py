#!/usr/bin/env python3
"""生成易读的量化选股分析报告 (HTML) — 含股票名称 + Top3 最优选择"""

import pandas as pd
import numpy as np
import webbrowser
from pathlib import Path
from datetime import datetime

ANALYSIS_DIR = Path.home() / ".qlibAssistant" / "analysis"
REPORT_DIR = ANALYSIS_DIR / "reports"


def get_stock_name_map():
    """获取股票名称映射表"""
    try:
        from utils import get_normalized_stock_list
        df = get_normalized_stock_list()
        if df is not None and "code" in df.columns and "name" in df.columns:
            # 统一格式：小写 sh/sz + 6位数字 → 名称
            name_map = {}
            for _, row in df.iterrows():
                code = str(row["code"]).strip()
                name = str(row["name"]).strip()
                if code and name and code != "nan" and name != "nan":
                    # 原始格式: SH600000 → 转成 sh600000
                    code_clean = code.lower().strip()
                    name_map[code_clean] = name
            return name_map
    except Exception as e:
        print(f"  ⚠️ 股票名称获取失败: {e}")
    return {}


def load_data():
    """加载最新的 analysis 目录数据"""
    selection_dirs = sorted(ANALYSIS_DIR.glob("selection_*"))
    if not selection_dirs:
        raise FileNotFoundError("未找到 analysis 数据目录")
    latest_dir = selection_dirs[-1]

    ret_file = list(latest_dir.glob("*_ret.csv"))
    filter_file = list(latest_dir.glob("*_filter_ret.csv"))
    if not ret_file or not filter_file:
        raise FileNotFoundError(f"缺少 CSV 文件: {latest_dir}")

    ret = pd.read_csv(ret_file[0])
    filtered = pd.read_csv(filter_file[0])
    return latest_dir, ret, filtered


def numeric_style(val: float, fmt: str = "{:.4f}") -> str:
    """数字着色"""
    if pd.isna(val):
        return '<span style="color:#999">-</span>'
    color = "#198038" if val > 0 else "#da1e28" if val < 0 else "#333"
    return f'<span style="color:{color};font-weight:500">{fmt.format(val)}</span>'


def score_bar(val: float, max_val: float) -> str:
    """评分可视化条"""
    pct = abs(val) / max(abs(max_val), 1e-9) * 100
    if val >= 0:
        return f'<div style="background:#e6f7ec;border-radius:3px;position:relative;width:120px;height:20px">' \
               f'<div style="background:#24a148;width:{pct:.0f}%;height:100%;border-radius:3px"></div>' \
               f'<span style="position:absolute;left:4px;top:1px;font-size:11px">{val:.4f}</span></div>'
    else:
        return f'<div style="background:#fce8e8;border-radius:3px;position:relative;width:120px;height:20px">' \
               f'<div style="background:#da1e28;width:{pct:.0f}%;height:100%;border-radius:3px"></div>' \
               f'<span style="position:absolute;left:4px;top:1px;font-size:11px;color:#fff">{val:.4f}</span></div>'


def consensus_badge(ratio: float) -> str:
    """共识度标签"""
    if ratio >= 0.9:
        return '<span style="background:#002d9c;color:#fff;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600">极高共识</span>'
    elif ratio >= 0.75:
        return '<span style="background:#0043ce;color:#fff;padding:2px 8px;border-radius:10px;font-size:12px">高共识</span>'
    elif ratio >= 0.5:
        return '<span style="background:#a6c8ff;color:#001d6c;padding:2px 8px;border-radius:10px;font-size:12px">中等共识</span>'
    else:
        return '<span style="background:#e0e0e0;color:#333;padding:2px 8px;border-radius:10px;font-size:12px">分歧较大</span>'


def generate_top3_analysis(top3, name_map) -> str:
    """生成 Top 3 最优选择的详细分析 HTML"""
    html = """<div class="card">
<h2 style="font-size:20px">🏆 最优3个选择</h2>
"""
    colors = ["#FFD700", "#C0C0C0", "#CD7F32"]
    medals = ["🥇", "🥈", "🥉"]
    reasons = []

    for idx, (_, row) in enumerate(top3.iterrows()):
        code = row["instrument"]
        name = name_map.get(code, "")
        name_html = f" {name}" if name else ""

        pos_pct = int(row["pos_ratio"] * 100)
        std5 = row.get("STD5", np.nan)
        std20 = row.get("STD20", np.nan)
        roc10 = row.get("ROC10", np.nan)
        roc20 = row.get("ROC20", np.nan)
        roc60 = row.get("ROC60", np.nan)
        ma5 = row.get("MA5", np.nan)
        ma10 = row.get("MA10", np.nan)

        # 生成推荐理由
        reasons_parts = []
        if not pd.isna(pos_pct):
            if pos_pct >= 80:
                reasons_parts.append(f"🔷 <b>{pos_pct}% 模型看多</b>·高度共识")
            elif pos_pct >= 60:
                reasons_parts.append(f"🔶 <b>{pos_pct}% 模型看多</b>·中等偏上共识")
            else:
                reasons_parts.append(f"🔸 <b>{pos_pct}% 模型看多</b>")
        if not pd.isna(roc10) and roc10 > 0.95:
            reasons_parts.append(f"📈 短期动量强 (ROC10={roc10:.2f})")
        elif not pd.isna(roc10) and roc10 > 0.85:
            reasons_parts.append(f"📊 短期趋势向好 (ROC10={roc10:.2f})")
        if not pd.isna(roc20) and roc20 > 0.95:
            reasons_parts.append(f"📈 中期动量强 (ROC20={roc20:.2f})")
        if not pd.isna(roc60) and roc60 > 0.95:
            reasons_parts.append(f"📈 长期趋势向上")
        if not pd.isna(std5) and std5 < 0.02:
            reasons_parts.append(f"🛡️ 近期波动极小 (STD5={std5:.4f})")
        elif not pd.isna(std5) and std5 < 0.04:
            reasons_parts.append(f"🛡️ 波动适中 (STD5={std5:.4f})")
        reason_str = " · ".join(reasons_parts) if reasons_parts else "综合评分领先"

        html += f"""<div style="background:linear-gradient(135deg,#fafbff,#fff);border:1px solid #e0e6f0;border-radius:12px;padding:20px;margin-bottom:12px">
<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
<span style="font-size:32px">{medals[idx]}</span>
<div>
<div style="font-size:20px;font-weight:700;color:#001d6c">{code}{name_html}</div>
<div style="font-size:13px;color:#666;margin-top:2px">{reason_str}</div>
</div>
<span style="margin-left:auto;font-size:28px;font-weight:700;color:{colors[idx]}">{row['avg_score']:.4f}</span>
</div>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:8px;font-size:13px">
<div style="background:#f5f7fa;padding:8px;border-radius:6px;text-align:center">
<div style="color:#666;font-size:11px">模型共识</div>
<div style="font-weight:600;color:#001d6c">{row['pos_ratio']:.0%}</div></div>
<div style="background:#f5f7fa;padding:8px;border-radius:6px;text-align:center">
<div style="color:#666;font-size:11px">ROC10</div>
<div>{numeric_style(roc10, '{:.3f}')}</div></div>
<div style="background:#f5f7fa;padding:8px;border-radius:6px;text-align:center">
<div style="color:#666;font-size:11px">ROC20</div>
<div>{numeric_style(roc20, '{:.3f}')}</div></div>
<div style="background:#f5f7fa;padding:8px;border-radius:6px;text-align:center">
<div style="color:#666;font-size:11px">STD5</div>
<div>{numeric_style(std5, '{:.4f}')}</div></div>
<div style="background:#f5f7fa;padding:8px;border-radius:6px;text-align:center">
<div style="color:#666;font-size:11px">STD20</div>
<div>{numeric_style(std20, '{:.4f}')}</div></div>
<div style="background:#f5f7fa;padding:8px;border-radius:6px;text-align:center">
<div style="color:#666;font-size:11px">MA10</div>
<div>{numeric_style(ma10, '{:.4f}')}</div></div>
</div>
</div>"""

    html += """</div>"""
    return html


def generate_html(latest_dir, ret, filtered, name_map):
    """生成 HTML 报告"""
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_col = [c for c in ret.columns if c.startswith("202")][0] if any(
        c.startswith("202") for c in ret.columns) else "2026-04-30"

    filtered_sorted = filtered.sort_values("avg_score", ascending=False)
    top3 = filtered_sorted.head(3)
    top30 = filtered_sorted.head(30)
    total_stocks = len(ret)
    filter_count = len(filtered)
    pass_rate = filter_count / total_stocks * 100 if total_stocks else 0

    # 评分分布区间
    bins = [-np.inf, -0.05, -0.02, -0.01, 0, 0.01, 0.02, 0.05, np.inf]
    labels = ["<-5%", "-5%~-2%", "-2%~-1%", "-1%~0%", "0%~1%", "1%~2%", "2%~5%", ">5%"]
    filtered["score_range"] = pd.cut(filtered["avg_score"], bins=bins, labels=labels)
    dist = filtered["score_range"].value_counts().sort_index()

    # 共识度分布
    all_pos = (filtered["pos_ratio"] == 1.0).sum()
    high = ((filtered["pos_ratio"] >= 0.75) & (filtered["pos_ratio"] < 1.0)).sum()
    mid = ((filtered["pos_ratio"] >= 0.5) & (filtered["pos_ratio"] < 0.75)).sum()
    low = (filtered["pos_ratio"] < 0.5).sum()

    # 模型权重信息
    md_file = latest_dir / "total.md"
    model_info_lines = []
    if md_file.exists():
        content = md_file.read_text(encoding="utf-8")
        import re
        for m in re.finditer(r"'model':\s*'(\w+)'.*?'ic_info':\s*\{'IC':\s*([\d.]+).*?'rank_icir':\s*'([\d.]+)'.*?'weight':\s*'([\d.]+)'", content, re.DOTALL):
            model_info_lines.append((m.group(1), m.group(2), m.group(3), m.group(4)))

    # === HTML 构建 ===
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>量化选股报告 - {date_col}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#f5f7fa; color:#1a1a1a; font-size:14px; line-height:1.6 }}
.container {{ max-width:1100px; margin:0 auto; padding:24px 16px }}

/* Header */
.header {{ background:linear-gradient(135deg,#001d6c,#0043ce); color:#fff; border-radius:12px; padding:32px; margin-bottom:24px }}
.header h1 {{ font-size:28px; margin-bottom:8px; font-weight:700 }}
.header .sub {{ opacity:.85; font-size:15px }}
.header .date {{ margin-top:8px; font-size:13px; opacity:.7 }}

/* Cards */
.card {{ background:#fff; border-radius:10px; padding:20px; margin-bottom:16px; box-shadow:0 1px 4px rgba(0,0,0,.06) }}
.card h2 {{ font-size:17px; margin-bottom:16px; color:#001d6c; border-left:3px solid #0043ce; padding-left:10px }}
.card h2 .badge {{ font-size:13px; color:#666; font-weight:400; margin-left:8px }}

/* Summary Grid */
.summary-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px }}
.stat-box {{ text-align:center; padding:16px 8px; border-radius:8px; background:#f8f9fb }}
.stat-box .num {{ font-size:28px; font-weight:700; color:#001d6c }}
.stat-box .num.green {{ color:#198038 }}
.stat-box .num.orange {{ color:#e67e22 }}
.stat-box .num.red {{ color:#da1e28 }}
.stat-box .label {{ font-size:12px; color:#666; margin-top:4px }}

/* Table */
.table-wrap {{ overflow-x:auto }}
table {{ width:100%; border-collapse:collapse; font-size:13px }}
th {{ background:#f0f4ff; color:#001d6c; padding:10px 8px; text-align:left; font-weight:600; white-space:nowrap; border-bottom:2px solid #d0d9f0 }}
td {{ padding:8px; border-bottom:1px solid #eee; white-space:nowrap }}
tr:hover {{ background:#f8faff }}

/* Model info */
.model-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:10px }}
.model-item {{ padding:12px; border-radius:8px; background:#f8f9fb; text-align:center }}
.model-item .mname {{ font-weight:600; color:#001d6c; font-size:14px }}
.model-item .minfo {{ font-size:12px; color:#666; margin-top:4px }}

/* Distribution */
.dist-bar {{ display:flex; align-items:center; gap:8px; margin:4px 0 }}
.dist-bar .dlabel {{ width:80px; font-size:12px; color:#555; text-align:right }}
.dist-bar .dtrack {{ flex:1; height:22px; background:#f0f0f0; border-radius:4px; position:relative; overflow:hidden }}
.dist-bar .dfill {{ height:100%; background:#0043ce; border-radius:4px; transition:width .3s }}
.dist-bar .dnum {{ width:40px; font-size:12px; color:#333 }}

/* Scroll hint */
.scroll-hint {{ font-size:12px; color:#999; text-align:right; padding:4px 0 }}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<div class="header">
<h1>📊 量化选股分析报告</h1>
<div class="sub">基于 5 模型集成加权投票 · Alpha158 因子 · 稳健性过滤</div>
<div class="date">预测日期: <strong>{date_col}</strong> &nbsp;·&nbsp; 生成时间: {report_time}</div>
</div>

<!-- Summary Cards -->
<div class="card">
<h2>关键指标</h2>
<div class="summary-grid">
<div class="stat-box">
<div class="num">{total_stocks}</div>
<div class="label">覆盖股票数</div>
</div>
<div class="stat-box">
<div class="num green">{filter_count}</div>
<div class="label">过滤后入选</div>
</div>
<div class="stat-box">
<div class="num orange">{pass_rate:.1f}%</div>
<div class="label">通过率</div>
</div>
<div class="stat-box">
<div class="num">{ret['avg_score'].mean():.4f}</div>
<div class="label">平均评分</div>
</div>
<div class="stat-box">
<div class="num">{ret['avg_score'].median():.4f}</div>
<div class="label">中位数评分</div>
</div>
<div class="stat-box">
<div class="num">{ret['avg_score'].max():.4f}</div>
<div class="label">最高评分</div>
</div>
</div>
</div>
"""

    # Top 3 最优选择
    html += generate_top3_analysis(top3, name_map)

    # 模型信息
    html += """<div class="card">
<h2>集成模型 <span class="badge">共 {} 个有效记录器</span></h2>
<div class="model-grid">
""".format(len(model_info_lines))
    seen_models = set()
    for model_name, ic, rank_icir, weight in model_info_lines:
        if model_name not in seen_models:
            seen_models.add(model_name)
            html += f"""<div class="model-item">
<div class="mname">{model_name}</div>
<div class="minfo">IC: {ic} · 权重: {weight}</div>
</div>
"""
    html += """</div>
</div>
"""

    # 评分分布
    html += """<div class="card">
<h2>评分分布 <span class="badge">过滤后 {} 只股票</span></h2>""".format(filter_count)
    max_dist = dist.max() if dist.max() > 0 else 1
    for label, count in dist.items():
        pct = count / filter_count * 100
        width = count / max_dist * 100
        html += f"""<div class="dist-bar">
<div class="dlabel">{label}</div>
<div class="dtrack"><div class="dfill" style="width:{width:.0f}%"></div></div>
<div class="dnum">{count}</div>
</div>"""
    html += "</div>"

    # 共识度
    html += """<div class="card">
<h2>模型共识度 <span class="badge">11 个预测器投票一致率</span></h2>
<div class="summary-grid">
<div class="stat-box"><div class="num">{}</div><div class="label">全部看多</div></div>
<div class="stat-box"><div class="num">{}</div><div class="label">高共识 (75%+)</div></div>
<div class="stat-box"><div class="num">{}</div><div class="label">中等共识 (50-75%)</div></div>
<div class="stat-box"><div class="num red">{}</div><div class="label">分歧较大 (&lt;50%)</div></div>
</div>
</div>""".format(all_pos, high, mid, low)

    # Top 30 选股
    html += f"""<div class="card">
<h2>📈 Top 30 选股推荐 <span class="badge">按评分降序</span></h2>
<div class="scroll-hint">← 左右滚动查看更多指标 →</div>
<div class="table-wrap">
<table>
<thead><tr>
<th>#</th><th>代码</th><th>名称</th><th>评分</th><th>共识度</th><th>ROC10</th><th>ROC20</th><th>ROC60</th><th>STD5</th><th>STD20</th><th>STD60</th><th>MA5</th><th>MA10</th>
</tr></thead>
<tbody>
"""
    for i, (_, row) in enumerate(top30.iterrows(), 1):
        code = row["instrument"]
        name = name_map.get(code, "")
        roc10 = numeric_style(row.get("ROC10", np.nan), "{:.3f}")
        roc20 = numeric_style(row.get("ROC20", np.nan), "{:.3f}")
        roc60 = numeric_style(row.get("ROC60", np.nan), "{:.3f}")
        std5 = numeric_style(row.get("STD5", np.nan), "{:.4f}")
        std20 = numeric_style(row.get("STD20", np.nan), "{:.4f}")
        std60 = numeric_style(row.get("STD60", np.nan), "{:.4f}")
        ma5 = numeric_style(row.get("MA5", np.nan), "{:.4f}")
        ma10 = numeric_style(row.get("MA10", np.nan), "{:.4f}")
        html += f"""<tr>
<td>{i}</td>
<td><strong>{code}</strong></td>
<td>{name}</td>
<td>{score_bar(row['avg_score'], 0.08)}</td>
<td>{consensus_badge(row['pos_ratio'])}</td>
<td>{roc10}</td>
<td>{roc20}</td>
<td>{roc60}</td>
<td>{std5}</td>
<td>{std20}</td>
<td>{std60}</td>
<td>{ma5}</td>
<td>{ma10}</td>
</tr>"""
    html += """</tbody>
</table>
</div>
</div>
"""

    # 全部入选(压缩表格)
    html += f"""<div class="card">
<h2>📋 全部入选股票 <span class="badge">{filter_count} 只 · 可滚动查看</span></h2>
<div class="table-wrap" style="max-height:400px;overflow-y:auto">
<table>
<thead><tr><th>#</th><th>代码</th><th>名称</th><th>评分</th><th>共识度</th></tr></thead>
<tbody>
"""
    for i, (_, row) in enumerate(filtered_sorted.iterrows(), 1):
        code = row["instrument"]
        name = name_map.get(code, "")
        html += f"""<tr>
<td>{i}</td>
<td>{code}</td>
<td>{name}</td>
<td>{numeric_style(row['avg_score'], '{:.4f}')}</td>
<td>{consensus_badge(row['pos_ratio'])}</td>
</tr>"""
    html += """</tbody></table></div></div>
"""

    # Footer
    html += """<div style="text-align:center;padding:20px;color:#999;font-size:12px">
由 QlibAssistant 自动生成 · 仅供参考，不构成投资建议
</div>
</div>
</body>
</html>"""
    return html


def main():
    print("📥 加载股票名称...")
    name_map = get_stock_name_map()
    print(f"   ✅ 获取到 {len(name_map)} 只股票名称")

    print("📂 加载分析数据...")
    latest_dir, ret, filtered = load_data()

    print("📝 生成报告...")
    html = generate_html(latest_dir, ret, filtered, name_map)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = REPORT_DIR / f"report_{date_str}.html"

    out_path.write_text(html, encoding="utf-8")
    print(f"✅ 报告已生成: {out_path}")
    print(f"📎 请在浏览器中打开查看")
    webbrowser.open(f"file://{out_path}")


if __name__ == "__main__":
    main()
