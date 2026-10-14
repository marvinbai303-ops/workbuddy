# -*- coding: utf-8 -*-
"""
守正组合回测引擎 —— 日频版
规则：
  1) 回测区间 2020-01-02 ~ 2026-09-30（日频）
  2) 基金成立满 1 个月后才用基金净值接续，此前用其跟踪指数（价格指数）代替
  3) 年度动平衡一次（每年 12 月最后一个交易日拉回原始配置）
输出 result_daily.json
"""
import json, os, math
from datetime import datetime, date

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "2020-01-02"

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
STRAT_IDX = {
    "300+": "000300.SH",
    "A500+": "000510.CSI",
    "500+": "000905.SH",
    "1000+": "000852.SH",
    "2000+": "932000.CSI",
}


def add_months(dstr, n):
    y, m, d = int(dstr[:4]), int(dstr[5:7]), int(dstr[8:10])
    m += n
    while m > 12:
        m -= 12; y += 1
    last = [31, 29 if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0 else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return f"{y:04d}-{m:02d}-{min(d, last):02d}"


def f(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").strip()
    if s in ("", "--", "-", "None", "null"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def interp(series, d):
    items = sorted(series.items())
    if not items:
        return None
    dt = datetime.strptime(d, "%Y-%m-%d")
    if dt <= datetime.strptime(items[0][0], "%Y-%m-%d"):
        return items[0][1]
    if dt >= datetime.strptime(items[-1][0], "%Y-%m-%d"):
        return items[-1][1]
    for i in range(len(items) - 1):
        d0 = datetime.strptime(items[i][0], "%Y-%m-%d")
        d1 = datetime.strptime(items[i + 1][0], "%Y-%m-%d")
        if d0 <= dt <= d1:
            if (d1 - d0).days == 0:
                return items[i][1]
            r = (dt - d0).days / (d1 - d0).days
            return items[i][1] + (items[i + 1][1] - items[i][1]) * r
    return items[-1][1]


def main():
    fund_daily = json.load(open(os.path.join(HERE, "fund_daily.json"), encoding="utf-8"))
    index_daily = json.load(open(os.path.join(HERE, "index_daily.json"), encoding="utf-8"))
    bench_raw = json.load(open(os.path.join(HERE, "benchmark.json"), encoding="utf-8"))["700001.TI"]
    money_raw = json.load(open(os.path.join(HERE, "fund_000917.json"), encoding="utf-8"))["000917.OF"]

    # 货币基金日频：采样点插值
    money = {k: f(v) for k, v in money_raw.items()}

    # 统一日频日期（取 007045 的日期，覆盖全区间交易日）
    cal = sorted(fund_daily.get("007045.OF", {}).keys())
    cal = [d for d in cal if d >= BASE]
    if BASE not in cal:
        cal = [BASE] + cal

    # ---- 每只持仓的日频增长因子 G ----
    G = {}
    for code, name, strat, w, inc in FUNDS:
        splice = add_months(inc, 1)
        idx_code = STRAT_IDX.get(strat)
        idx_series = {k: f(v) for k, v in index_daily.get(idx_code, {}).items()} if idx_code else {}
        fnd_series = {k: f(v) for k, v in fund_daily.get(code, {}).items()}
        if code == "000917.OF":
            fnd_series = money

        g = {BASE: 1.0}
        prev = BASE
        for d in cal[1:]:
            use_fund = d > splice
            if use_fund:
                cur = fnd_series.get(d)
                if cur is None:
                    cur = interp(fnd_series, d)
                pcur = fnd_series.get(prev)
                if pcur is None:
                    pcur = interp(fnd_series, prev)
            else:
                cur = idx_series.get(d)
                if cur is None:
                    cur = interp(idx_series, d)
                pcur = idx_series.get(prev)
                if pcur is None:
                    pcur = interp(idx_series, prev)
            gp = g.get(prev, 1.0)
            if cur is not None and pcur and pcur > 0:
                g[d] = gp * cur / pcur
            else:
                g[d] = gp
            prev = d
        G[code] = g

    # ---- 组合日频净值（年度动平衡）----
    codes = [f_[0] for f_ in FUNDS]
    w0 = {f_[0]: f_[3] for f_ in FUNDS}
    wcur = dict(w0)
    nav = [(BASE, 1.0)]
    V = 1.0
    for i in range(1, len(cal)):
        d = cal[i]
        pd = cal[i - 1]
        rets = {}
        for c in codes:
            gd = G[c].get(d)
            gp = G[c].get(pd, 1.0)
            rets[c] = (gd / gp) if (gd is not None and gp and gp > 0) else 1.0
        port_ret = sum(wcur[c] * rets[c] for c in codes)
        V *= port_ret
        nav.append((d, V))
        for c in codes:
            wcur[c] = wcur[c] * rets[c] / port_ret if port_ret else wcur[c]
        # 年度动平衡（12 月最后一个交易日）
        if d[5:7] == "12" and (i + 1 >= len(cal) or cal[i + 1][5:7] != "12"):
            wcur = dict(w0)

    dates = [x[0] for x in nav]
    vals = [x[1] for x in nav]
    dret = [vals[i] / vals[i - 1] - 1 for i in range(1, len(vals))]

    total_ret = vals[-1] - 1
    d0 = datetime.strptime(BASE, "%Y-%m-%d")
    d1 = datetime.strptime(dates[-1], "%Y-%m-%d")
    days = (d1 - d0).days
    ann_ret = (1 + total_ret) ** (365.0 / days) - 1 if days > 0 else 0.0

    # 最大回撤（日频）
    peak = vals[0]; mdd = 0.0
    for v in vals:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)

    # 年化波动率、夏普（日频）
    m = len(dret)
    mean = sum(dret) / m if m else 0
    var = sum((r - mean) ** 2 for r in dret) / (m - 1) if m > 1 else 0
    vol = math.sqrt(var * 252)
    sharpe = ann_ret / vol if vol > 0 else 0.0
    pos = sum(1 for r in dret if r > 1e-9)
    win_rate = pos / m if m else 0.0

    # ---- 年度收益 ----
    annual = {}
    prev_v = 1.0
    for i, d in enumerate(dates):
        if d[5:7] == "12" and (i + 1 >= len(dates) or dates[i + 1][5:7] != "12"):
            annual[d[:4]] = vals[i] / prev_v - 1
            prev_v = vals[i]
    annual["2026"] = vals[-1] / prev_v - 1

    # ---- 月度收益矩阵 ----
    matrix = {}
    for i in range(1, len(vals)):
        d = dates[i]
        y, mo = d[:4], int(d[5:7])
        matrix.setdefault(y, {"months": {}, "ret": 1.0})
        matrix[y]["months"].setdefault(mo, 1.0)
        matrix[y]["months"][mo] *= (1 + dret[i - 1])
    for y in matrix:
        for mo in matrix[y]["months"]:
            matrix[y]["months"][mo] -= 1.0
    # 月胜率、年内最大回撤
    for y in matrix:
        mo = matrix[y]["months"]
        rets_y = [mo[k] for k in sorted(mo)]
        matrix[y]["win_rate"] = sum(1 for r in rets_y if r > 1e-9) / len(rets_y) if rets_y else 0
        cum = 1.0; peak = 1.0; mdd_y = 0.0
        for r in rets_y:
            cum *= (1 + r)
            peak = max(peak, cum)
            mdd_y = min(mdd_y, cum / peak - 1)
        matrix[y]["mdd"] = mdd_y

    # 月胜率（整体，从月度矩阵汇总）
    all_monthly = []
    for y in matrix:
        all_monthly.extend(matrix[y]["months"].values())
    monthly_win_rate = sum(1 for r in all_monthly if r > 1e-9) / len(all_monthly) if all_monthly else 0

    # ---- 基准（同花顺全A加权，采样点插值到日频）----
    bench = {k: f(v) for k, v in bench_raw.items()}
    b0 = interp(bench, BASE)
    bench_nav = [interp(bench, d) for d in dates]
    bench_total = bench_nav[-1] / b0 - 1 if b0 else 0
    bench_ann = (1 + bench_total) ** (365.0 / days) - 1 if days > 0 else 0
    # 基准波动率：用采样点（约月频）收益计算，避免日频插值平滑低估波动
    bench_items = sorted(bench.items())
    bench_mret = [bench_items[i][1] / bench_items[i - 1][1] - 1 for i in range(1, len(bench_items))]
    bm = len(bench_mret)
    bmean = sum(bench_mret) / bm if bm else 0
    bvar = sum((r - bmean) ** 2 for r in bench_mret) / (bm - 1) if bm > 1 else 0
    bvol = math.sqrt(bvar * 12)
    # 基准最大回撤（用采样点，约月频）
    bpeak = bench_items[0][1]; bmdd = 0.0
    for _, v in bench_items:
        bpeak = max(bpeak, v)
        bmdd = min(bmdd, v / bpeak - 1)

    result = {
        "base": BASE, "end": dates[-1], "days": len(dates),
        "nav": nav,
        "daily_returns": list(zip(dates[1:], dret)),
        "monthly_returns": None,
        "annual_returns": annual,
        "total_return": total_ret,
        "annualized_return": ann_ret,
        "annualized_volatility": vol,
        "max_drawdown": mdd,
        "sharpe": sharpe,
        "day_win_rate": win_rate,
        "month_win_rate": monthly_win_rate,
        "positive_days": pos,
        "rebalance_count": sum(1 for i, d in enumerate(dates) if d[5:7] == "12" and (i + 1 >= len(dates) or dates[i + 1][5:7] != "12")),
        "matrix": matrix,
        "benchmark": {
            "total_return": bench_total,
            "annualized_return": bench_ann,
            "annualized_volatility": bvol,
            "max_drawdown": bmdd,
            "nav": list(zip(dates, bench_nav)),
        },
    }
    json.dump(result, open(os.path.join(HERE, "result_daily.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"日频区间 {BASE} ~ {dates[-1]}，{len(dates)} 个交易日")
    print(f"累计收益 {total_ret*100:.2f}%，年化 {ann_ret*100:.2f}%")
    print(f"年化波动率 {vol*100:.2f}%，最大回撤 {mdd*100:.2f}%，夏普 {sharpe:.2f}")
    print(f"日胜率 {win_rate*100:.1f}%（{pos}/{m}），动平衡 {result['rebalance_count']} 次")
    print(f"基准(同花顺全A加权) 累计 {bench_total*100:.2f}%，年化 {bench_ann*100:.2f}%")
    print("年度收益：", {k: f"{v*100:.2f}%" for k, v in annual.items()})


if __name__ == "__main__":
    main()
