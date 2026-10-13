# -*- coding: utf-8 -*-
"""
守正组合回测 —— 输出生成：Excel + 两页 PPT（对标模板 p19/p20 风格）
依赖 result.json（由 backtest.py 产出）
"""
import json, os, math
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)

# 颜色（涨红跌绿，A股惯例；主题蓝橙）
RED = "#C0392B"
GREEN = "#1E8449"
BLUE = "#01375D"
ORANGE = "#E97132"
GRAY = "#6E6D66"

FUNDS = [
    ("007045.OF", "博道沪深300指数增强C", "300+", 0.10, "2019-04-26"),
    ("008593.OF", "天弘沪深300指数增强发起式C", "300+", 0.10, "2019-12-27"),
    ("022746.OF", "博道中证A500指数增强C", "A500+", 0.09, "2025-01-23"),
    ("023820.OF", "天弘中证A500指数增强C", "A500+", 0.09, "2025-09-17"),
    ("006594.OF", "博道中证500指数增强C", "500+", 0.10, "2019-01-03"),
    ("001557.OF", "天弘中证500指数增强C", "500+", 0.10, "2019-08-12"),
    ("017954.OF", "汇添富中证1000指数增强C", "1000+", 0.10, "2023-05-19"),
    ("014202.OF", "天弘中证1000指数增强C", "1000+", 0.10, "2022-01-04"),
    ("019924.OF", "华泰柏瑞中证2000指数增强C", "2000+", 0.10, "2024-01-12"),
    ("019919.OF", "招商中证2000指数增强C", "2000+", 0.10, "2024-01-02"),
    ("000917.OF", "嘉实快线货币A", "货币基金", 0.02, "2015-06-25"),
]
STRAT_IDX_NAME = {"300+": "沪深300", "A500+": "中证A500", "500+": "中证500",
                  "1000+": "中证1000", "2000+": "中证2000", "货币基金": "—"}


def pct(x, nd=2):
    return f"{x*100:.{nd}f}%"


def color_of(x):
    if x > 1e-9:
        return "FFC0392B"
    if x < -1e-9:
        return "FF1E8449"
    return "FF3A3936"


def main():
    R = json.load(open(os.path.join(HERE, "result.json"), encoding="utf-8"))

    # ===================== Excel =====================
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    thin = Side(style="thin", color="D9D7CF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    head_fill = PatternFill("solid", fgColor="01375D")
    head_font = Font(name="微软雅黑", color="FFFFFF", bold=True, size=11)
    cell_font = Font(name="微软雅黑", size=10)
    title_font = Font(name="微软雅黑", bold=True, size=14, color="01375D")

    def style_header(ws, row, ncol):
        for c in range(1, ncol + 1):
            cell = ws.cell(row, c)
            cell.fill = head_fill
            cell.font = head_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border

    # --- Sheet1 组合净值 ---
    ws = wb.active
    ws.title = "组合净值"
    ws["A1"] = "守正组合回测净值（2020-01-02 ~ 2026-09-30，月频，含年度动平衡）"
    ws["A1"].font = title_font
    ws.append([])
    ws.append(["日期", "组合净值", "组合月度收益", "基准净值(同花顺全A等权)", "基准月度收益"])
    style_header(ws, 3, 5)
    nav_dict = dict(R["nav"])
    bench_raw = [v for _, v in R["benchmark"]["nav"]]
    b0 = bench_raw[-1] / (1 + R["benchmark"]["total_return"])   # 基日(2020-01-02)基准值
    bench_norm = [v / b0 for v in bench_raw]                     # 归一到基日=1
    bench_dict = dict(zip([d for d, _ in R["benchmark"]["nav"]], bench_norm))
    mret_dict = dict(R["monthly_returns"])
    bmret_dict = dict(R["benchmark"]["monthly_returns"])
    for i, (d, v) in enumerate(R["nav"]):
        ws.append([d, round(v, 6), mret_dict.get(d), round(bench_dict.get(d, 0), 4), bmret_dict.get(d)])
        r = ws.max_row
        ws.cell(r, 1).font = cell_font
        ws.cell(r, 2).number_format = "0.0000"
        ws.cell(r, 3).number_format = "0.00%"
        ws.cell(r, 4).number_format = "0.00"
        ws.cell(r, 5).number_format = "0.00%"
    for col, w in zip("ABCDE", [14, 12, 14, 22, 14]):
        ws.column_dimensions[col].width = w

    # --- Sheet2 年度收益 ---
    ws = wb.create_sheet("年度收益")
    ws["A1"] = "年度收益对比"
    ws["A1"].font = title_font
    ws.append([])
    ws.append(["年份", "组合年度收益", "基准年度收益", "超额收益"])
    style_header(ws, 3, 4)
    # 基准年度收益
    bench_annual = {}
    bnav = dict(R["benchmark"]["nav"])
    bdates = sorted(bnav.keys())
    prev_b = bnav[bdates[0]]
    for i, d in enumerate(bdates):
        if d[5:7] == "12":
            bench_annual[d[:4]] = bnav[d] / prev_b - 1
            prev_b = bnav[d]
    bench_annual["2026"] = bnav[bdates[-1]] / prev_b - 1
    for y in sorted(R["annual_returns"].keys()):
        a = R["annual_returns"][y]
        b = bench_annual.get(y, 0)
        ws.append([y, a, b, a - b])
        r = ws.max_row
        ws.cell(r, 1).font = cell_font
        ws.cell(r, 2).number_format = "0.00%"
        ws.cell(r, 3).number_format = "0.00%"
        ws.cell(r, 4).number_format = "0.00%"
        ws.cell(r, 2).font = Font(name="微软雅黑", size=10, color=color_of(a))
        ws.cell(r, 3).font = Font(name="微软雅黑", size=10, color=color_of(b))
        ws.cell(r, 4).font = Font(name="微软雅黑", size=10, color=color_of(a - b))
    for col, w in zip("ABCD", [10, 16, 16, 16]):
        ws.column_dimensions[col].width = w

    # --- Sheet3 月度收益矩阵 ---
    ws = wb.create_sheet("月度收益矩阵")
    ws["A1"] = "月度收益矩阵（%）"
    ws["A1"].font = title_font
    ws.append([])
    header = ["年份"] + [f"{i}月" for i in range(1, 13)] + ["年收益", "月胜率", "最大回撤"]
    ws.append(header)
    style_header(ws, 3, len(header))
    matrix = R["matrix"]
    for y in sorted(matrix.keys()):
        mo = matrix[y]["months"]
        row = [y]
        for m in range(1, 13):
            row.append(mo.get(str(m), mo.get(m)))
        row.append(R["annual_returns"].get(y))
        row.append(matrix[y]["win_rate"])
        row.append(matrix[y]["mdd"])
        ws.append(row)
        r = ws.max_row
        for c in range(1, len(header) + 1):
            cell = ws.cell(r, c)
            cell.font = cell_font
            cell.border = border
            cell.alignment = Alignment(horizontal="center")
            if c == 1:
                cell.font = Font(name="微软雅黑", size=10, bold=True)
            elif 2 <= c <= 13:
                if cell.value is not None:
                    cell.number_format = "0.00%"
                    cell.font = Font(name="微软雅黑", size=10, color=color_of(cell.value))
            elif c == 14:
                cell.number_format = "0.00%"
                cell.font = Font(name="微软雅黑", size=10, bold=True, color=color_of(cell.value))
            elif c == 15:
                cell.number_format = "0.00%"
            elif c == 16:
                cell.number_format = "0.00%"
                cell.font = Font(name="微软雅黑", size=10, color="FF1E8449")
    # 成立以来 汇总行
    ws.append(["成立以来"] + [None] * 12 + [R["total_return"], R["month_win_rate"], R["max_drawdown"]])
    r = ws.max_row
    for c in range(1, len(header) + 1):
        cell = ws.cell(r, c)
        cell.font = Font(name="微软雅黑", size=10, bold=True)
        cell.border = border
        cell.alignment = Alignment(horizontal="center")
        if c == 14:
            cell.number_format = "0.00%"
            cell.font = Font(name="微软雅黑", size=10, bold=True, color=color_of(R["total_return"]))
        elif c == 15:
            cell.number_format = "0.00%"
        elif c == 16:
            cell.number_format = "0.00%"
            cell.font = Font(name="微软雅黑", size=10, bold=True, color="FF1E8449")
    ws.column_dimensions["A"].width = 10
    for i in range(2, 17):
        ws.column_dimensions[get_column_letter(i)].width = 8

    # --- Sheet4 关键指标 ---
    ws = wb.create_sheet("关键指标")
    ws["A1"] = "关键指标（月频口径）"
    ws["A1"].font = title_font
    ws.append([])
    metrics = [
        ("回测区间", f"{R['base']} ~ {R['end']}", ""),
        ("月度数", R["months"], ""),
        ("累计收益", R["total_return"], R["benchmark"]["total_return"]),
        ("年化收益", R["annualized_return"], R["benchmark"]["annualized_return"]),
        ("年化波动率", R["annualized_volatility"], R["benchmark"]["annualized_volatility"]),
        ("区间最大回撤", R["max_drawdown"], R["benchmark"]["max_drawdown"]),
        ("夏普比率(无风险0%)", R["sharpe"], ""),
        ("月度胜率", R["month_win_rate"], ""),
        ("正收益月数", R["positive_months"], ""),
        ("动平衡次数", R["rebalance_count"], ""),
    ]
    ws.append(["指标", "守正组合", "基准(同花顺全A等权)"])
    style_header(ws, 3, 3)
    for name, v, b in metrics:
        ws.append([name, v, b])
        r = ws.max_row
        ws.cell(r, 1).font = cell_font
        if isinstance(v, float):
            ws.cell(r, 2).number_format = "0.00%"
        ws.cell(r, 2).font = cell_font
        if isinstance(b, float):
            ws.cell(r, 3).number_format = "0.00%"
        ws.cell(r, 3).font = cell_font
    for col, w in zip("ABC", [24, 18, 26]):
        ws.column_dimensions[col].width = w

    # --- Sheet5 持仓明细 ---
    ws = wb.create_sheet("持仓明细")
    ws["A1"] = "守正组合持仓明细与接续规则"
    ws["A1"].font = title_font
    ws.append([])
    ws.append(["代码", "基金名称", "策略", "配置比例", "成立日", "接续日(成立满1月)", "指数代替"])
    style_header(ws, 3, 7)
    for code, name, strat, w, inc in FUNDS:
        splice = add_months(inc, 1)
        use_idx = "是（" + STRAT_IDX_NAME.get(strat, "—") + "）" if inc >= "2020-01-01" else "否"
        ws.append([code, name, strat, w, inc, splice, use_idx])
        r = ws.max_row
        for c in range(1, 8):
            ws.cell(r, c).font = cell_font
            ws.cell(r, c).border = border
        ws.cell(r, 4).number_format = "0%"
    for col, w in zip("ABCDEFG", [12, 30, 10, 10, 12, 16, 26]):
        ws.column_dimensions[col].width = w

    xlsx_path = os.path.join(OUT, "守正组合回测结果.xlsx")
    wb.save(xlsx_path)
    print("Excel 已生成:", xlsx_path)

    # ===================== PPT =====================
    gen_ppt(R)
    print("PPT 已生成")


def add_months(dstr, n):
    y, m, d = int(dstr[:4]), int(dstr[5:7]), int(dstr[8:10])
    m += n
    while m > 12:
        m -= 12; y += 1
    last = [31, 29 if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0 else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return f"{y:04d}-{m:02d}-{min(d, last):02d}"


def gen_ppt(R):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    # 中文字体
    for fp in ["/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/PingFang.ttc"]:
        if os.path.exists(fp):
            font_manager.fontManager.addfont(fp)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
            break
    plt.rcParams["axes.unicode_minus"] = False

    # --- 净值曲线图 ---
    nav = R["nav"]
    bnav = R["benchmark"]["nav"]
    dates = [x[0] for x in nav]
    v = [x[1] for x in nav]
    _bvals = [x[1] for x in bnav]
    _b0 = _bvals[-1] / (1 + R["benchmark"]["total_return"])
    bv = [x / _b0 for x in _bvals]   # 基准归一到基日=1
    fig, ax = plt.subplots(figsize=(7.8, 3.6), dpi=200)
    ax.plot(dates, v, color=BLUE, lw=2, label="守正组合净值")
    ax.plot(dates, bv, color=ORANGE, lw=1.6, ls="--", label="同花顺全A等权")
    ax.axhline(1.0, color="#B0AFA8", lw=0.8, ls=":")
    ax.set_xlim(dates[0], dates[-1])
    ax.grid(True, color="#EAE8E1", lw=0.6)
    ax.set_facecolor("#FFFFFF")
    for sp in ax.spines.values():
        sp.set_color("#C9C7BF")
    # 精简 x 轴刻度
    n = len(dates)
    step = max(1, n // 8)
    ticks = dates[::step]
    ax.set_xticks(ticks)
    ax.set_xticklabels([d[2:7].replace("-", "/") for d in ticks], fontsize=8, color=GRAY)
    ax.tick_params(axis="y", labelsize=8, colors=GRAY)
    ax.legend(fontsize=8, loc="upper left", frameon=False)
    ax.set_title("守正组合 vs 同花顺全A等权（净值归一，起点=1）", fontsize=10, color=BLUE)
    fig.tight_layout()
    chart_path = os.path.join(OUT, "nav_chart.png")
    fig.savefig(chart_path, facecolor="white")
    plt.close(fig)

    # --- 组装 PPT ---
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    prs = Presentation()
    prs.slide_width = Emu(12192000)   # 13.333 in
    prs.slide_height = Emu(6858000)   # 7.5 in

    BLUE_C = RGBColor(0x01, 0x37, 0x5D)
    ORANGE_C = RGBColor(0xE9, 0x71, 0x32)
    RED_C = RGBColor(0xC0, 0x39, 0x2B)
    GREEN_C = RGBColor(0x1E, 0x84, 0x49)
    GRAY_C = RGBColor(0x6E, 0x6D, 0x66)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    FONT = "微软雅黑"

    def add_title(slide, num, text):
        # 椭圆 + 编号
        from pptx.enum.shapes import MSO_SHAPE
        oval = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.73), Inches(0.18), Inches(0.42), Inches(0.42))
        oval.fill.solid(); oval.fill.fore_color.rgb = BLUE_C; oval.line.fill.background()
        tf = oval.text_frame; tf.text = num
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.runs[0]; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = FONT
        # 横线
        ln = slide.shapes.add_connector(1, Inches(0.64), Inches(1.25), Inches(12.9), Inches(1.25))
        ln.line.color.rgb = BLUE_C; ln.line.width = Pt(1.5)
        # 标题
        box = slide.shapes.add_textbox(Inches(1.3), Inches(0.43), Inches(11.0), Inches(0.56))
        tf = box.text_frame; tf.text = text
        p = tf.paragraphs[0]
        r = p.runs[0]; r.font.size = Pt(20); r.font.bold = True; r.font.color.rgb = BLUE_C; r.font.name = FONT

    def add_footnote(slide, text, top=7.0):
        box = slide.shapes.add_textbox(Inches(0.4), Inches(top), Inches(12.5), Inches(0.4))
        tf = box.text_frame; tf.text = text; tf.word_wrap = True
        p = tf.paragraphs[0]; r = p.runs[0]; r.font.size = Pt(9); r.font.color.rgb = GRAY_C; r.font.name = FONT

    def add_table(slide, data, left, top, width, col_widths, header=True, fontsize=11, row_h=0.34):
        rows = len(data); cols = len(data[0])
        tbl = slide.shapes.add_table(rows, cols, Inches(left), Inches(top), Inches(width), Inches(row_h * rows)).table
        for j, w in enumerate(col_widths):
            tbl.columns[j].width = Inches(w)
        for i, row in enumerate(data):
            for j, val in enumerate(row):
                cell = tbl.cell(i, j)
                cell.text = str(val)
                cell.vertical_anchor = 1  # middle
                p = cell.text_frame.paragraphs[0]
                p.alignment = PP_ALIGN.CENTER if j > 0 or i > 0 else PP_ALIGN.LEFT
                for r in p.runs:
                    r.font.size = Pt(fontsize); r.font.name = FONT
                if header and i == 0:
                    cell.fill.solid(); cell.fill.fore_color.rgb = BLUE_C
                    for r in p.runs:
                        r.font.color.rgb = WHITE; r.font.bold = True
                else:
                    cell.fill.solid(); cell.fill.fore_color.rgb = RGBColor(0xF7, 0xF6, 0xF1) if i % 2 == 0 else WHITE
                    for r in p.runs:
                        r.font.color.rgb = RGBColor(0x2C, 0x2C, 0x2A)
        return tbl

    # ---------- 第 1 页（对标 p19） ----------
    s1 = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s1, "3.1", "基于基金池的业绩模拟：守正组合（风险级别 R4）")
    # 配置表（左）
    add_table(s1, [
        ["", "守正组合", "同花顺全A等权"],
        ["目标权重", "100%", "—"],
        ["动平衡规则", "定期动平衡：频率1年；定幅动平衡：无", ""],
    ], 0.67, 1.55, 7.2, [1.6, 3.2, 2.4], row_h=0.4)
    # 关键指标表（右）
    add_table(s1, [
        ["年化收益", pct(R["annualized_return"])],
        ["年化波动率", pct(R["annualized_volatility"])],
        ["区间最大回撤", pct(R["max_drawdown"])],
        ["夏普比率*", f"{R['sharpe']:.2f}"],
        ["动平衡次数", f"{R['rebalance_count']}次"],
    ], 8.6, 1.5, 4.1, [2.2, 1.9], header=False, row_h=0.4)
    # 净值曲线图
    s1.shapes.add_picture(chart_path, Inches(0.62), Inches(3.0), width=Inches(7.9))
    # 图右侧说明（超额收益结论）
    box = s1.shapes.add_textbox(Inches(8.7), Inches(3.7), Inches(4.2), Inches(2.6))
    tf = box.text_frame; tf.word_wrap = True
    ex = R["total_return"] - R["benchmark"]["total_return"]
    lines = [
        ("区间累计收益", pct(R["total_return"]), R["total_return"]),
        ("基准累计收益", pct(R["benchmark"]["total_return"]), R["benchmark"]["total_return"]),
        ("相对基准超额", pct(ex), ex),
    ]
    for i, (lab, val, num) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r1 = p.add_run(); r1.text = lab + "："
        r1.font.size = Pt(12); r1.font.name = FONT; r1.font.color.rgb = GRAY_C
        r2 = p.add_run(); r2.text = val
        r2.font.size = Pt(14); r2.font.bold = True; r2.font.name = FONT
        r2.font.color.rgb = RED_C if num > 0 else GREEN_C
        p.space_after = Pt(10)
    add_footnote(s1, "注：数据来源为腾讯 NeoData/同花顺 iFinD。策略历史表现不构成对未来业绩的承诺。统计区间为2020年1月2日-2026年9月30日（月频）。计算夏普比例时，无风险收益按0%计。基金成立满1个月后接续基金净值，此前用跟踪指数（价格指数）代替。")

    # ---------- 第 2 页（对标 p20） ----------
    s2 = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s2, "3.2", "基于基金池业绩模拟：守正组合")
    # 汇总文字
    matrix = R["matrix"]
    full_years = [y for y in sorted(matrix.keys()) if y < "2026"]
    pos_years = sum(1 for y in full_years if R["annual_returns"].get(y, 0) > 0)
    annual_vals = [R["annual_returns"][y] for y in full_years]
    max_a, min_a = max(annual_vals), min(annual_vals)
    mrets = [r for _, r in R["monthly_returns"]]
    pos_m = sum(1 for r in mrets if r > 1e-9)
    summary = (f"{len(full_years)}个完整年度有{pos_years}年为正收益。"
               f"最高年度收益{pct(max_a)}，最低年度收益{pct(min_a)}，年化收益率{pct(R['annualized_return'])}。"
               f"{len(mrets)}个完整月度录得{pos_m}个月({pos_m/len(mrets)*100:.1f}%)正收益。"
               f"最高月度收益{pct(max(mrets))}，最低月度收益{pct(min(mrets))}，平均月度收益{pct(sum(mrets)/len(mrets))}")
    box = s2.shapes.add_shape(1, Inches(0.78), Inches(1.45), Inches(11.6), Inches(0.8))
    box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0xF1, 0xEF, 0xE8); box.line.fill.background()
    tf = box.text_frame; tf.text = summary; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
    r = p.runs[0]; r.font.size = Pt(12); r.font.color.rgb = RGBColor(0x2C, 0x2C, 0x2A); r.font.name = FONT

    # 月度矩阵表
    header = ["年份"] + [f"{i}月" for i in range(1, 13)] + ["年收益", "月胜率", "最大回撤"]
    data = [header]
    for y in sorted(matrix.keys()):
        mo = matrix[y]["months"]
        row = [y] + [pct(mo.get(str(m), mo.get(m))) if (str(m) in mo or m in mo) else "" for m in range(1, 13)]
        row += [pct(R["annual_returns"].get(y, 0)), pct(matrix[y]["win_rate"]), pct(matrix[y]["mdd"])]
        data.append(row)
    data.append(["成立以来"] + [""] * 12 + [pct(R["total_return"]), pct(R["month_win_rate"]), pct(R["max_drawdown"])])

    col_w = [0.9] + [0.78] * 12 + [0.9, 0.78, 0.9]
    tbl = add_table(s2, data, 0.45, 2.35, 12.84, col_w, fontsize=9, row_h=0.42)
    # 给正收益红色、负收益绿色（月收益单元格）
    for ri, y in enumerate(sorted(matrix.keys())):
        mo = matrix[y]["months"]
        for m in range(1, 13):
            mv = mo.get(str(m), mo.get(m))
            if mv is not None:
                cell = tbl.cell(ri + 1, m)
                for p in cell.text_frame.paragraphs:
                    for r in p.runs:
                        r.font.color.rgb = RED_C if mv > 0 else GREEN_C
        # 年收益
        ac = tbl.cell(ri + 1, 13)
        av = R["annual_returns"].get(y, 0)
        for p in ac.text_frame.paragraphs:
            for r in p.runs:
                r.font.color.rgb = RED_C if av > 0 else GREEN_C
                r.font.bold = True
    add_footnote(s2, "数据来源：腾讯 NeoData/同花顺 iFinD。回测区间为2020/1/2-2026/9/30（月频）。历史回测不代表未来表现，以上涉及的相关数据均为假设条件或虚拟回测，仅为实现策略举例说明之目的、用于投资者教育，不涉及任何具体产品信息及其宣传推介，历史业绩不预示未来表现。", top=6.8)

    pptx_path = os.path.join(OUT, "守正组合业绩模拟两页.pptx")
    prs.save(pptx_path)
    print("PPT 已生成:", pptx_path)


if __name__ == "__main__":
    main()
