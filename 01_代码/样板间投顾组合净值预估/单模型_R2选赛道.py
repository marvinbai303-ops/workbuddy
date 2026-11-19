# -*- coding: utf-8 -*-
"""
单模型：R² 定方向 + β 定仓位（v2）

1) 基准赛道：报告期后首个窗口（10月，16个交易日）R² 最高的赛道 —— 锁定"它原本是什么"
2) 每日滚动回归（窗口 8 日）对该赛道求 α、β、R²
3) 仓位结构 = β / 0.93（0.93 = 满仓基金对等权赛道指数的典型 β）
4) 调仓方向：
   - R² ≥ 0.88            → 结构未变
   - R² < 0.88 且存在他赛道 R² 高出 0.05 以上、且其 β ≥ 0.60 → 换赛道（连续 2 日才确认）
   - R² < 0.88 但无合格替代 → 结构模糊（降仓或换股，赛道不变）
5) 预测 = α + β × 当日赛道收益
"""
import importlib.util
import sys

from paths import DATA, load_base

base = load_base()

DATES, FUNDS = base.DATES, base.FUNDS
series_for, ols = base.series_for, base.ols

THEME = {
    "光模块": ["300308", "300502", "300394", "688498", "300570", "002281", "300548",
            "603083", "688313", "601869", "06869", "600183", "002916", "002463",
            "002938", "002384"],
    "半导体设备": ["688072", "688012", "002371", "688120", "688037", "688361", "300567",
               "688082", "688409", "688147", "300604", "688200", "688019", "300480"],
    "存储算力": ["688825", "603986", "688008", "688256", "688041", "00981", "00992",
              "688521", "688536", "300661", "002475"],
}
ORDER = ["017612", "017489", "016371", "013841", "162214", "009993", "017745"]
NAMES = list(THEME)
NACT, W, FULL = 26, 8, 0.93
R2_KEEP, R2_EDGE, B_MIN, CONFIRM = 0.88, 0.08, 0.60, 3
B_RATIO = (0.65, 1.55)   # 切换时新赛道β须与当前β同量级，防共线性假信号

TH = {}
for k, codes in THEME.items():
    rs = [series_for(c) for c in codes]
    TH[k] = [sum(r[t] for r in rs) / len(rs) for t in range(len(DATES))]


def fit(act, th, lo, hi):
    return ols(TH[th][lo:hi], act[lo:hi])


def base_theme(act):
    scores = {k: fit(act, k, 0, 16)[2] for k in NAMES}
    return max(scores, key=scores.get), scores


def run(key, w=W):
    act = FUNDS[key]["nav"] + [None]
    # 基准赛道：全样本 R² 最高（等价于给基金挑对标指数，不参与逐日切换）
    scores = {k: fit(act, k, 0, NACT)[2] for k in NAMES}
    bt = max(scores, key=scores.get)
    pred, beta, r2s, rows = [None] * 27, [None] * 27, [None] * 27, []
    for t in range(len(DATES)):
        if t < w:
            continue
        a, b, r2 = fit(act, bt, t - w, t)
        beta[t], r2s[t] = b, r2
        pred[t] = a + b * TH[bt][t]
        if r2 >= 0.88:
            st = "结构未变"
        elif r2 >= 0.75:
            st = "结构松动"
        else:
            st = "结构明显变化"
        if t >= 16:
            ref = sum(beta[i] for i in range(W, 16)) / (16 - W)   # 10月β均值
            dh = beta[t] / ref
            pos = ("降仓" if dh < 0.80 else "加仓" if dh > 1.20 else "仓位持平")
        else:
            dh, pos = 1.0, "—"
        rows.append(dict(t=t, date=DATES[t], th=bt, a=a, b=b, r2=r2,
                         pos_ratio=b / FULL, dh=dh, pred=pred[t], act=act[t], state=st,
                         pos=pos,
                         err=None if act[t] is None else (pred[t] - act[t]) * 100))
    return dict(bt=bt, scores=scores, rows=rows, pred=pred, act=act)


def ev(res, lo=W, hi=NACT):
    e = [(res["pred"][t] - res["act"][t]) for t in range(lo, hi) if res["pred"][t] is not None]
    n = len(e)
    return dict(n=n, mae=sum(abs(v) for v in e) / n * 100,
                rmse=(sum(v * v for v in e) / n) ** 0.5 * 100,
                bias=sum(e) / n * 100,
                hit=sum(1 for v in e if abs(v) <= 0.5) / n,
                mx=max(abs(v) for v in e) * 100)


if __name__ == "__main__":
    print("=" * 104)
    print(f"单模型｜R² 定方向 + β 定仓位｜窗口 {W} 日｜样本外 {DATES[W]} ~ {DATES[NACT-1]}")
    print("=" * 104)
    R = {}
    print(f"{'基金':<15}{'基准赛道':<12}{'MAE':>6}{'RMSE':>6}{'偏差':>6}{'±50bp':>7}{'最大':>6}")
    print("-" * 104)
    for k in ORDER:
        r = run(k)
        R[k] = r
        m = ev(r)
        print(f"{FUNDS[k]['name']:<15}{r['bt']:<12}{m['mae']:>6.0f}{m['rmse']:>6.0f}"
              f"{m['bias']:>6.0f}{m['hit']:>7.0%}{m['mx']:>6.0f}")

    print("\n" + "=" * 104)
    print("逐日状态（β = 有效暴露，仓位 = β/0.93，误差 = 预估−实际 bp）")
    print("=" * 104)
    for k in ORDER:
        r = R[k]
        print(f"\n{FUNDS[k]['name']}（基准 {r['bt']}，全样本R²={r['scores'][r['bt']]:.3f}）")
        print(f"  {'日期':<11}{'β':>6}{'仓位':>7}{'R²':>7}{'预估%':>8}{'实际%':>8}{'误差bp':>8}  {'方向':<12}{'仓位判定'}")
        for x in r["rows"]:
            if x["t"] < W:
                continue
            act = "—" if x["act"] is None else f"{x['act']:+.2f}"
            err = "—" if x["err"] is None else f"{x['err']:.0f}"
            print(f"  {x['date']:<11}{x['b']:>6.2f}{x['pos_ratio']:>7.0%}{x['r2']:>7.2f}"
                  f"{x['pred']:>8.2f}{act:>8}{err:>8}  {x['state']:<12}{x['pos']}")


def report(R, path=str(DATA / "单模型预估_产业趋势2号.xlsx")):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    hf = PatternFill("solid", fgColor="1F3864"); hfont = Font(color="FFFFFF", bold=True, size=10)
    thin = Side(style="thin", color="D9D9D9"); bd = Border(left=thin, right=thin, top=thin, bottom=thin)
    warn = Font(color="A32D2D", bold=True)

    def head(ws):
        for c in range(1, ws.max_column + 1):
            cell = ws.cell(1, c); cell.fill, cell.font = hf, hfont
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.freeze_panes = ws.cell(2, 1)

    wb = Workbook(); ws = wb.active; ws.title = "汇总"
    ws.append(["基金代码", "基金名称", "基准赛道", "全样本R²", "MAE(bp)", "RMSE(bp)", "平均偏差(bp)",
               "±50bp命中", "最大误差(bp)", "10月仓位%", "11-16仓位%", "仓位变化pp", "最新R²", "方向判定"])
    for k in ORDER:
        r = R[k]; m = ev(r)
        octb = sum(x["b"] for x in r["rows"] if x["t"] < 16) / len([x for x in r["rows"] if x["t"] < 16])
        last = r["rows"][-1]
        ws.append([k, FUNDS[k]["name"], r["bt"], round(r["scores"][r["bt"]], 3),
                   round(m["mae"]), round(m["rmse"]), round(m["bias"], 1), m["hit"],
                   round(m["mx"]), round(octb / FULL * 100, 1), round(last["pos_ratio"] * 100, 1),
                   round((last["pos_ratio"] - octb / FULL) * 100, 1), round(last["r2"], 2), last["state"]])
    head(ws)
    for c, w in zip(range(1, 15), [10, 16, 12, 10, 9, 9, 11, 10, 11, 10, 11, 10, 9, 14]):
        ws.column_dimensions[get_column_letter(c)].width = w
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for c in row:
            c.border = bd; c.alignment = Alignment(horizontal="center")

    ws = wb.create_sheet("逐日明细")
    ws.append(["日期", "基金", "β", "隐含仓位%", "R²", "预估%", "实际%", "误差bp", "方向", "仓位判定"])
    for k in ORDER:
        for x in R[k]["rows"]:
            ws.append([x["date"], FUNDS[k]["name"], round(x["b"], 3), round(x["pos_ratio"] * 100, 1),
                       round(x["r2"], 3), round(x["pred"], 2), x["act"],
                       None if x["err"] is None else round(x["err"]), x["state"], x["pos"]])
    head(ws)
    for c, w in zip(range(1, 11), [12, 16, 8, 10, 8, 9, 9, 9, 14, 10]):
        ws.column_dimensions[get_column_letter(c)].width = w
    for row in range(2, ws.max_row + 1):
        v = ws.cell(row, 8).value
        if isinstance(v, (int, float)) and abs(v) >= 120:
            ws.cell(row, 8).font = warn

    ws = wb.create_sheet("今日预估")
    ws.append(["基金", "基准赛道", "β", "隐含仓位%", "R²", "赛道今日涨跌%", "今日预估%", "方向"])
    for k in ORDER:
        x = R[k]["rows"][-1]
        ws.append([FUNDS[k]["name"], R[k]["bt"], round(x["b"], 3), round(x["pos_ratio"] * 100, 1),
                   round(x["r2"], 3), round(TH[R[k]["bt"]][-1], 2), round(x["pred"], 2), x["state"]])
    head(ws)
    for c, w in zip(range(1, 9), [16, 12, 8, 10, 8, 13, 11, 14]):
        ws.column_dimensions[get_column_letter(c)].width = w
    wb.save(path); return path
