# -*- coding: utf-8 -*-
"""
样板间投顾组合 —— 组合净值复算引擎（云端流水线核心）

用途：
  1) 验证：用模板内的底层净值，按模板同一套算法复算 7 个组合净值，并与模板 `实盘组合净值` 逐日对标；
  2) 复用：把「取数」换成 iFinD API（腾讯文档 / 云端定时任务）后，本文件即为计算引擎。

算法（与模板完全一致，已验证逐日精确一致，最大绝对差 < 1e-10）：
  组合净值[i] = 结转因子(段) × Σ_j [ w_j(段) × NAV_j[i] / NAV_j(段首) ] × (1 - 年化费率)^(交易日差/365)

  · 段（segment）：每个组合按调仓日切成若干段（P0 初始 / P1 / P2 / P3 / P4…）
  · 结转因子  ：调仓时把上一段的累计涨幅带过来，= 上段因子 × Σ_j [ w_j × NAV_j(本次调仓日)/NAV_j(上段基准日) ]
  · 费率      ：只在最后统一折日，指数基准为「组合自身起始日」

数据来源（模板内）：
  · `实盘净值数据(iFinD公式)` —— 底层基金复权单位净值矩阵（当前由 iFinD Excel 加载项取数）
  · `实盘持仓配置`            —— 6 个组合的初始权重 / 年化费率 / 净值起始日
  · `分期持仓明细`            —— 各组合各调仓期权重 + AO 列结转因子
  · `实盘组合净值`            —— 模板自身算出的结果（用于对标）
"""
import datetime
from openpyxl import load_workbook

XLSX = "样板间投顾组合监控模板-精简版-0917更新.xlsx"

EPOCH = datetime.date(1899, 12, 30)


def excel_date(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, (int, float)):
        return EPOCH + datetime.timedelta(days=int(v))
    if isinstance(v, str) and len(v) >= 10 and v[:2] == "20":
        return datetime.date.fromisoformat(v[:10])
    return None


def load_workbook_data(path=XLSX):
    wb = load_workbook(path, data_only=True)

    # ---- 底层净值矩阵 ----
    ws = wb["实盘净值数据(iFinD公式)"]
    nav_dates, nav = [], []
    for r in range(5, ws.max_row + 1):
        d = excel_date(ws.cell(r, 1).value)
        if d is None:
            continue
        vals = [ws.cell(r, c).value for c in range(2, 39)]  # B..AL（37 只）
        if all(v is None for v in vals):
            continue
        nav_dates.append(d)
        nav.append([float(v) if isinstance(v, (int, float)) else None for v in vals])
    idx = {d: i for i, d in enumerate(nav_dates)}

    # ---- 初始配置 ----
    ws = wb["实盘持仓配置"]
    cfg = {}
    for r in range(4, 11):                                     # 第 4~10 行 = 7 个组合
        name = str(ws.cell(r, 1).value or "").replace(" ", "").replace("权重", "").strip()
        cfg[name] = dict(
            w=[ws.cell(r, c).value or 0 for c in range(2, 38)],   # B..AK
            fee=float(ws.cell(r, 39).value or 0),                 # AM 年化费率
            start=excel_date(ws.cell(r, 40).value),               # AN 净值起始日
        )

    # ---- 分期持仓（含 AO 结转因子） ----
    ws = wb["分期持仓明细"]
    stage = {}
    for r in range(5, ws.max_row + 1):
        lab = ws.cell(r, 1).value
        if not lab:
            continue
        w = [ws.cell(r, c).value or 0 for c in range(2, 39)]     # B..AL（37 只）
        if not any(w):
            continue
        stage[r] = dict(label=str(lab), w=w,
                        factor=ws.cell(r, 41).value)             # AO 累计因子

    # ---- 模板结果（对标用） ----
    ws = wb["实盘组合净值"]
    templ = {}
    for r in range(5, ws.max_row + 1):
        d = excel_date(ws.cell(r, 1).value)
        if d is None:
            continue
        templ[d] = {c: ws.cell(r, c).value for c in (2, 5, 8, 11, 14, 17, 20)}
    return dict(nav_dates=nav_dates, nav=nav, idx=idx, cfg=cfg, stage=stage, templ=templ)


# ------------------------------------------------------------------
# 分段表：镜像模板 `实盘组合净值` 的公式结构
#   (引擎行区间, 权重来源, 权重行, 净值列, 段基准日, 上段结转(权重行, 因子基准日))
# 列范围：C24 = B..Y（1..24），C26 = B..Y+Z..AA（1..26），C37 = B..AL（1..37）
# ------------------------------------------------------------------
C24, C26, C37 = list(range(1, 25)), list(range(1, 27)), list(range(1, 38))
SEGMENTS = {
    "产业趋势":    [((5, 20),  ("cfg", 4), C24[:23], "2026-06-22", None),
                    ((21, 80), ("stg", 17), C24, "2026-07-10", (5, "2026-07-10"))],
    "产业趋势基石": [((6, 20),  ("cfg", 5), C24[:23], "2026-06-18", None),
                    ((21, 80), ("stg", 18), C24, "2026-07-10", (6, "2026-07-10"))],
    "产业趋势2号":  [((5, 20),  ("cfg", 6), C24[:23], "2026-06-23", None),
                    ((21, 80), ("stg", 19), C24, "2026-07-10", (7, "2026-07-10"))],
    "10-90":      [((5, 13),  ("cfg", 7), C24[:23], "2026-06-24", None),
                   ((14, 17), ("stg", 9),  C24, "2026-07-01", (8, "2026-07-01")),
                   ((18, 24), ("stg", 14), C24, "2026-07-07", (9, "2026-07-07")),
                   ((25, 64), ("stg", 20), C24, "2026-07-17", (14, "2026-07-17")),
                   ((65, 80), ("stg", 23), C26, "2026-09-11", (20, "2026-09-11"))],
    "10-90基石":   [((6, 13),  ("cfg", 8), C24[:23], "2026-06-18", None),
                   ((14, 17), ("stg", 11), C24, "2026-07-01", (10, "2026-07-01")),
                   ((18, 24), ("stg", 15), C24, "2026-07-07", (11, "2026-07-07")),
                   ((25, 64), ("stg", 21), C24, "2026-07-17", (15, "2026-07-17")),
                   ((65, 80), ("stg", 24), C26, "2026-09-11", (21, "2026-09-11"))],
    "30-70":      [((5, 13),  ("cfg", 9), C24[:23], "2026-06-24", None),
                   ((14, 17), ("stg", 13), C24, "2026-07-01", (12, "2026-07-01")),
                   ((18, 24), ("stg", 16), C24, "2026-07-07", (13, "2026-07-07")),
                   ((25, 64), ("stg", 22), C24, "2026-07-17", (16, "2026-07-17")),
                   ((65, 80), ("stg", 25), C26, "2026-09-11", (22, "2026-09-11"))],
    "20-80":      [((70, 80), ("stg", 26), C37, "2026-09-17", None)],
}
ENGINE_COL = {"产业趋势": 2, "产业趋势基石": 5, "产业趋势2号": 8, "10-90": 11,
              "10-90基石": 14, "30-70": 17, "20-80": 20}


def compute_series(d, name, nav_override=None):
    """返回 {交易日: 组合净值}；nav_override 可传入外部净值矩阵（云端 API 取数时使用）。"""
    nav = nav_override if nav_override is not None else d["nav"]
    idx, cfg, stage = d["idx"], d["cfg"], d["stage"]
    fee = cfg[name]["fee"]
    if fee > 1:            # 兼容以百分数（1.5）录入的情况
        fee /= 100.0
    si = idx[cfg[name]["start"]]

    def sp(wlist, cols, i_num, i_den):
        s = 0.0
        for c in cols:
            w = wlist[c - 1]
            if not w:
                continue
            s += w * nav[i_num][c - 1] / nav[i_den][c - 1]
        return s

    # cfg 行号 -> 组合名（第 4~10 行）
    cfg_row = {4: "产业趋势", 5: "产业趋势基石", 6: "产业趋势2号",
               7: "10-90", 8: "10-90基石", 9: "30-70", 10: "20-80"}

    def w_of(src, row):
        return cfg[cfg_row[row]]["w"] if src == "cfg" else stage[row]["w"]

    series, F = {}, 1.0
    prev_base = None
    for k, (rng, wsrc, cols, based, fact) in enumerate(SEGMENTS[name]):
        if k > 0:
            frow, fbased = fact
            F *= sp(w_of("stg", frow), cols, idx[excel_date(fbased)], prev_base)
        wl = w_of(wsrc[0], wsrc[1])
        b = idx[excel_date(based)]
        for i in range(max(0, rng[0] - 5), min(len(d["nav_dates"]), rng[1] - 5 + 1)):
            days = (d["nav_dates"][i] - d["nav_dates"][si]).days
            series[d["nav_dates"][i]] = round(F * sp(wl, cols, i, b) * (1 - fee) ** (days / 365.0), 15)
        prev_base = b
    return series


if __name__ == "__main__":
    d = load_workbook_data(XLSX)
    print(f"净值区间：{d['nav_dates'][0]} → {d['nav_dates'][-1]}（{len(d['nav_dates'])} 个交易日）\n")
    print(f"{'组合':<12}{'对比天数':>8}{'最大绝对差':>16}")
    print("-" * 40)
    allok = True
    for name in SEGMENTS:
        s = compute_series(d, name)
        col = ENGINE_COL[name]
        mx = 0.0
        n = 0
        for day, row in d["templ"].items():
            if day not in s:
                continue
            t = row.get(col)
            if not isinstance(t, (int, float)):
                continue
            mx = max(mx, abs(s[day] - t))
            n += 1
        allok = allok and mx < 1e-10
        print(f"{name:<12}{n:>8}{mx:>16.3e}")
    print("-" * 40)
    print("结论：", "全部组合逐日精确一致（< 1e-10）" if allok else "存在偏差")
