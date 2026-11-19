# -*- coding: utf-8 -*-
"""
产业趋势组合2号 · 单只基金每日净值预估流水线
2026-10-09 ~ 2026-11-16｜四算法 + 降仓强信号

A1 静态前十大       不做漂移、不补未披露仓位（≈天天基金口径）
A2 漂移+持仓补全     个股漂移再平衡 + 未披露股票用披露持仓等权代理 + 现金 + 费率日折
A3 赛道β            alpha + beta × 赛道指数日收益，滚动 6 日 OLS（严格样本外；α 已含费率）
A4 融合             0.5×A2 + 0.5×A3

信号（只报强信号）
  E 早期：连续 3 日 |残差| ≥ 100bp 且残差符号与赛道收益相反  → 有效暴露下降
  C 确认：滚动6日赛道β ÷ 10月基准β < 0.75 连续 3 日
"""
import importlib.util
import sys

from paths import DATA, load_base

base = load_base()

DATES, FUNDS = base.DATES, base.FUNDS
series_for, implied, ols = base.series_for, base.implied, base.ols

THEME = {
    "光模块产业链": ["300308", "300502", "300394", "688498", "300570", "002281", "300548",
                 "603083", "688313", "601869", "06869", "600183", "002916", "002463",
                 "002938", "002384"],
    "半导体设备": ["688072", "688012", "002371", "688120", "688037", "688361", "300567",
                "688082", "688409", "688147", "300604", "688200", "688019", "300480"],
    "存储/国产算力": ["688825", "603986", "688008", "688256", "688041", "00981", "00992",
                  "688521", "688536", "300661", "002475"],
}
MAP = {"017612": "光模块产业链", "017489": "光模块产业链", "016371": "光模块产业链",
       "013841": "半导体设备", "162214": "半导体设备", "009993": "半导体设备",
       "017745": "存储/国产算力"}
ORDER = ["017612", "017489", "016371", "013841", "162214", "009993", "017745"]
NACT = 26
BWIN = 6


def theme_ret(name):
    rs = [series_for(c) for c in THEME[name]]
    return [sum(r[t] for r in rs) / len(rs) for t in range(len(DATES))]


IDX = {k: theme_ret(k) for k in THEME}


def build(key):
    f = FUNDS[key]
    act = f["nav"] + [None]
    m1, _ = implied(key, "static")
    m2, _ = implied(key, "full")
    x = IDX[MAP[key]]
    a0, b0, _ = ols(x[:16], act[:16])
    m3 = [None] * len(DATES)
    beta, ratio, r2p = [None] * len(DATES), [None] * len(DATES), [None] * len(DATES)
    for t in range(len(DATES)):
        if t < BWIN:
            continue
        a, b, r2 = ols(x[t - BWIN:t], act[t - BWIN:t])
        m3[t] = a + b * x[t]                      # α 已含费率，不再重复扣
        beta[t], ratio[t], r2p[t] = b, b / b0, r2
    m4 = [None if m3[t] is None else 0.5 * m2[t] + 0.5 * m3[t] for t in range(len(DATES))]
    resid = [None if act[t] is None else act[t] - m2[t] for t in range(len(DATES))]
    return dict(f=f, act=act, m1=m1, m2=m2, m3=m3, m4=m4,
                beta=beta, ratio=ratio, r2=r2p, base_beta=b0, theme=x, resid=resid)


def signals(d):
    out = []
    run = 0
    for t in range(16, NACT):
        r, xr = d["resid"][t], d["theme"][t]
        if r is not None and abs(r) >= 1.0 and (r * xr) < 0:
            run += 1
            if run == 3:
                out.append(("E 暴露下降(早期)", DATES[t], run))
        else:
            run = 0
    run = 0
    for t in range(16, NACT):
        rt = d["ratio"][t]
        if rt is not None and rt < 0.75:
            run += 1
            if run == 3:
                out.append(("C 降仓确认", DATES[t], run))
        else:
            run = 0
    return out


def stats(est, act, lo=10, hi=NACT):
    e = [(est[t] - act[t]) for t in range(lo, hi) if est[t] is not None and act[t] is not None]
    if not e:
        return None
    n = len(e)
    return dict(n=n, mae=sum(abs(v) for v in e) / n * 100,
                rmse=(sum(v * v for v in e) / n) ** 0.5 * 100,
                bias=sum(e) / n * 100,
                hit=sum(1 for v in e if abs(v) <= 0.5) / n,
                mx=max(abs(v) for v in e) * 100)


def run():
    D = {k: build(k) for k in ORDER}
    for k in ORDER:
        D[k]["sig"] = signals(D[k])
        trig = min([s[1] for s in D[k]["sig"]], default=None)
        D[k]["trig"] = trig
        # 采用模型：信号触发后切 A3，之前用 A4
        adop, used = [], []
        for t in range(len(DATES)):
            if trig and DATES[t] >= trig and D[k]["m3"][t] is not None:
                adop.append(D[k]["m3"][t]); used.append("A3")
            elif D[k]["m4"][t] is not None:
                adop.append(D[k]["m4"][t]); used.append("A4")
            else:
                adop.append(D[k]["m2"][t]); used.append("A2")
        D[k]["adop"], D[k]["used"] = adop, used
        D[k]["stat"] = {n: stats(D[k][m], D[k]["act"]) for n, m in
                        (("A1", "m1"), ("A2", "m2"), ("A3", "m3"), ("A4", "m4"))}
        D[k]["stat"]["采用"] = stats(adop, D[k]["act"])
    return D


if __name__ == "__main__":
    D = run()
    print("=" * 108)
    print("样本外日均绝对误差 MAE（bp）｜对比区间 2026-10-23 ~ 2026-11-13（A3 可用起点之后）")
    print("=" * 108)
    print(f"{'基金':<15}{'A1静态':>8}{'A2补全':>8}{'A3赛道':>8}{'A4融合':>8}{'采用':>8}{'命中':>7}{'最大':>7}")
    print("-" * 108)
    for k in ORDER:
        d, s = D[k], D[k]["stat"]
        print(f"{d['f']['name']:<15}{s['A1']['mae']:>8.0f}{s['A2']['mae']:>8.0f}"
              f"{s['A3']['mae']:>8.0f}{s['A4']['mae']:>8.0f}{s['采用']['mae']:>8.0f}"
              f"{s['采用']['hit']:>7.0%}{s['采用']['mx']:>7.0f}")
    print("\n" + "=" * 108)
    print("降仓强信号")
    print("=" * 108)
    for k in ORDER:
        d = D[k]
        if d["sig"]:
            for s in d["sig"]:
                print(f"  [触发] {d['f']['name']:<14} {s[0]:<16} {s[1]}")
        else:
            mn = min([r for r in d["ratio"] if r is not None])
            print(f"  [正常] {d['f']['name']:<14} 全期无信号  最低β比值 {mn:.2f}")


def report(D, path=str(DATA / "每日预估对比_产业趋势2号.xlsx")):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    hf = PatternFill("solid", fgColor="1F3864")
    hfont = Font(color="FFFFFF", bold=True, size=10)
    thin = Side(style="thin", color="D9D9D9")
    bd = Border(left=thin, right=thin, top=thin, bottom=thin)
    red = Font(color="A32D2D", bold=True)

    def head(ws, nrow=1):
        for c in range(1, ws.max_column + 1):
            cell = ws.cell(nrow, c)
            cell.fill, cell.font = hf, hfont
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.freeze_panes = ws.cell(nrow + 1, 1)

    wb = Workbook()
    ws = wb.active
    ws.title = "模型对比"
    ws.append(["基金代码", "基金名称", "赛道", "A1静态MAE", "A2补全MAE", "A3赛道MAE", "A4融合MAE",
               "采用MAE", "MAE起点", "RMSE", "平均偏差", "±50bp命中", "最大误差", "信号", "信号日期"])
    for k in ORDER:
        d, s = D[k], D[k]["stat"]
        ws.append([k, d["f"]["name"], MAP[k], round(s["A1"]["mae"]), round(s["A2"]["mae"]),
                   round(s["A3"]["mae"]), round(s["A4"]["mae"]), round(s["采用"]["mae"]),
                   DATES[10], round(s["采用"]["rmse"]), round(s["采用"]["bias"], 1),
                   s["采用"]["hit"], round(s["采用"]["mx"]),
                   "降仓" if d["sig"] else "正常", d["trig"] or ""])
    head(ws)
    for c, w in zip(range(1, 16), [10, 17, 14, 11, 11, 11, 11, 10, 12, 8, 10, 11, 10, 8, 12]):
        ws.column_dimensions[get_column_letter(c)].width = w
    for r in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for c in r:
            c.border = bd
            c.alignment = Alignment(horizontal="center")

    ws = wb.create_sheet("每日明细")
    ws.append(["日期", "代码", "基金", "实际涨跌%", "A1%", "A2%", "A3%", "A4%", "采用%", "采用模型", "误差bp"])
    for t in range(len(DATES)):
        for k in ORDER:
            d = D[k]
            if d["act"][t] is None and d["adop"][t] is None:
                continue
            a = d["act"][t]
            ws.append([DATES[t], k, d["f"]["name"], a,
                       round(d["m1"][t], 2) if d["m1"][t] is not None else None,
                       round(d["m2"][t], 2) if d["m2"][t] is not None else None,
                       round(d["m3"][t], 2) if d["m3"][t] is not None else None,
                       round(d["m4"][t], 2) if d["m4"][t] is not None else None,
                       round(d["adop"][t], 2), d["used"][t],
                       round((d["adop"][t] - a) * 100) if a is not None else None])
    head(ws)
    for c, w in zip(range(1, 12), [12, 9, 17, 11, 8, 8, 8, 8, 9, 9, 9]):
        ws.column_dimensions[get_column_letter(c)].width = w
    for r in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for c in r:
            c.border = bd
    for r in range(2, ws.max_row + 1):
        v = ws.cell(r, 11).value
        if isinstance(v, (int, float)) and abs(v) >= 100:
            ws.cell(r, 11).font = red

    ws = wb.create_sheet("信号日志")
    ws.append(["日期", "基金", "赛道", "滚动6日β", "10月基准β", "β比值", "残差bp", "赛道收益%", "判定"])
    for k in ORDER:
        d = D[k]
        for t in range(10, NACT):
            if d["beta"][t] is None:
                continue
            flag = ""
            if d["trig"] and DATES[t] == d["trig"]:
                flag = "★ 强信号"
            elif d["ratio"][t] < 0.85:
                flag = "关注"
            ws.append([DATES[t], d["f"]["name"], MAP[k], round(d["beta"][t], 3),
                       round(d["base_beta"], 3), round(d["ratio"][t], 2),
                       round(d["resid"][t] * 100), round(d["theme"][t], 2), flag])
    head(ws)
    for c, w in zip(range(1, 10), [12, 17, 14, 11, 12, 9, 9, 11, 10]):
        ws.column_dimensions[get_column_letter(c)].width = w

    ws = wb.create_sheet("今日预估")
    ws.append(["基金", "赛道", "A1静态%", "A2补全%", "A3赛道%", "A4融合%", "采用%", "状态"])
    for k in ORDER:
        d = D[k]
        t = len(DATES) - 1
        ws.append([d["f"]["name"], MAP[k], round(d["m1"][t], 2), round(d["m2"][t], 2),
                   round(d["m3"][t], 2) if d["m3"][t] is not None else None,
                   round(d["m4"][t], 2) if d["m4"][t] is not None else None,
                   round(d["adop"][t], 2), "降仓信号生效" if d["trig"] else "正常"])
    head(ws)
    for c, w in zip(range(1, 9), [17, 14, 11, 11, 11, 11, 10, 14]):
        ws.column_dimensions[get_column_letter(c)].width = w
    wb.save(path)
    return path


def matrix(D):
    print("\n" + "=" * 108)
    print("每日误差矩阵（采用模型预估 − 实际，单位 bp）｜11-16 无实际净值，显示预估涨跌")
    print("=" * 108)
    nm = [D[k]["f"]["name"][:6] for k in ORDER]
    print(f"{'日期':<12}" + "".join(f"{x:>10}" for x in nm))
    print("-" * 108)
    for t in range(NACT + 1):
        line = f"{DATES[t]:<12}"
        for k in ORDER:
            d = D[k]
            v = d["adop"][t]
            a = d["act"][t]
            if a is None:
                line += f"{('~'+format(v, '+.2f')):>10}"
            else:
                line += f"{(v - a) * 100:>10.0f}"
        print(line)
    print("-" * 108)
    print("注：~ 表示为 11-16 的预估涨跌幅（%，非误差）")

    print("\n" + "=" * 108)
    print("今日（2026-11-16）预估涨跌 %")
    print("=" * 108)
    print(f"{'基金':<17}{'A1静态':>9}{'A2补全':>9}{'A3赛道':>9}{'A4融合':>9}{'采用':>9}")
    for k in ORDER:
        d = D[k]
        t = len(DATES) - 1
        print(f"{d['f']['name']:<17}{d['m1'][t]:>9.2f}{d['m2'][t]:>9.2f}"
              f"{(d['m3'][t] if d['m3'][t] is not None else 0):>9.2f}"
              f"{(d['m4'][t] if d['m4'][t] is not None else 0):>9.2f}{d['adop'][t]:>9.2f}")
    return None
