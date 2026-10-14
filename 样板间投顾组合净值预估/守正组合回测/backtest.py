# -*- coding: utf-8 -*-
"""
守正组合回测引擎 v2
规则：
  1) 回测区间 2020-01-02 ~ 2026-09-30（月频，月末最后交易日）
  2) 基金成立满 1 个月后才用基金净值接续，此前用其跟踪指数（价格指数）代替
  3) 年度动平衡一次（每年年末最后一个交易日拉回原始配置）
输出 result.json
"""
import json, os, math
from datetime import datetime

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
    """在 {date: value} 序列上对日期 d 线性插值"""
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
    fund_month = json.load(open(os.path.join(HERE, "fund_month.json"), encoding="utf-8"))
    index_month = json.load(open(os.path.join(HERE, "index_month.json"), encoding="utf-8"))
    bench_raw = json.load(open(os.path.join(HERE, "benchmark.json"), encoding="utf-8"))["700001.TI"]
    base = json.load(open(os.path.join(HERE, "base.json"), encoding="utf-8"))
    # 货币基金（NeoData 无数据，走 iFinD 采样点插值）
    fund_917 = json.load(open(os.path.join(HERE, "fund_000917.json"), encoding="utf-8"))["000917.OF"]
    for d, v in fund_917.items():
        fund_month.setdefault("000917.OF", {})[d] = v

    # ---- 统一月末日期：取沪深300 指数的日期（覆盖全区间、交易日口径最全）----
    idx300 = index_month.get("000300.SH", {})
    month_ends = sorted(idx300.keys())
    if not month_ends:
        # 退路：取所有数据日期并集
        s = set()
        for d in fund_month.values():
            s.update(d.keys())
        for d in index_month.values():
            s.update(d.keys())
        month_ends = sorted(x for x in s if x >= BASE)
    month_ends = [d for d in month_ends if d >= BASE]

    # ---- 每只持仓的月末增长因子 G（指数代替期 + 基金期）----
    G = {}
    for code, name, strat, w, inc in FUNDS:
        splice = add_months(inc, 1)
        idx_code = STRAT_IDX.get(strat)
        idx_series = {k: f(v) for k, v in index_month.get(idx_code, {}).items()} if idx_code else {}
        fnd_series = {k: f(v) for k, v in fund_month.get(code, {}).items()}
        base_idx = f(base.get("index", {}).get(idx_code)) if idx_code else None
        base_fnd = f(base.get("fund", {}).get(code))
        if code == "000917.OF":
            base_fnd = interp(fund_917, BASE)

        g = {BASE: 1.0}
        prev = BASE
        for d in month_ends:
            use_fund = d > splice
            if use_fund:
                cur = fnd_series.get(d)
                if cur is None:
                    cur = interp(fnd_series, d)
                prev_v = g.get(prev, 1.0)
                pcur = fnd_series.get(prev)
                if pcur is None:
                    pcur = base_fnd if prev == BASE else interp(fnd_series, prev)
                if cur is not None and pcur and pcur > 0:
                    g[d] = prev_v * cur / pcur
                else:
                    g[d] = prev_v
            else:
                cur = idx_series.get(d)
                if cur is None:
                    cur = interp(idx_series, d)
                prev_v = g.get(prev, 1.0)
                pcur = idx_series.get(prev)
                if pcur is None:
                    pcur = base_idx if prev == BASE else interp(idx_series, prev)
                if cur is not None and pcur and pcur > 0:
                    g[d] = prev_v * cur / pcur
                else:
                    g[d] = prev_v
            prev = d
        G[code] = g

    # ---- 组合净值（年度动平衡）----
    codes = [f_[0] for f_ in FUNDS]
    w0 = {f_[0]: f_[3] for f_ in FUNDS}
    wcur = dict(w0)
    nav = []
    V = 1.0
    for i, d in enumerate(month_ends):
        pd = month_ends[i - 1] if i > 0 else BASE
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
        # 年度动平衡（年末）
        if d[5:7] == "12":
            wcur = dict(w0)

    dates = [x[0] for x in nav]
    vals = [x[1] for x in nav]
    mrets = [vals[i] / vals[i - 1] - 1 if i > 0 else vals[i] - 1 for i in range(len(vals))]

    # ---- 年度收益 ----
    annual = {}
    prev_v = 1.0
    year_start = {d[:4]: i for i, d in enumerate(dates)}
    for i, d in enumerate(dates):
        y = d[:4]
        if d[5:7] == "12":
            annual[y] = vals[i] / prev_v - 1
            prev_v = vals[i]
    # 2026 年（截至 9 月末）
    annual["2026"] = vals[-1] / prev_v - 1

    total_ret = vals[-1] - 1
    d0 = datetime.strptime(BASE, "%Y-%m-%d")
    d1 = datetime.strptime(dates[-1], "%Y-%m-%d")
    days = (d1 - d0).days
    ann_ret = (1 + total_ret) ** (365.0 / days) - 1 if days > 0 else 0.0

    # 最大回撤
    peak = vals[0]; mdd = 0.0
    for v in vals:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)

    # 年化波动率、夏普
    m = len(mrets)
    mean = sum(mrets) / m if m else 0
    var = sum((r - mean) ** 2 for r in mrets) / (m - 1) if m > 1 else 0
    vol = math.sqrt(var * 12)
    sharpe = ann_ret / vol if vol > 0 else 0.0
    pos = sum(1 for r in mrets if r > 1e-9)
    win_rate = pos / m if m else 0.0

    # ---- 基准（同花顺全A等权 700082.TI，采样点插值到月末）----
    bench = {k: f(v) for k, v in bench_raw.items()}
    bench_nav = [interp(bench, d) for d in dates]
    b0 = interp(bench, BASE)
    bench_ret_total = bench_nav[-1] / b0 - 1 if b0 else 0
    bench_ann = (1 + bench_ret_total) ** (365.0 / days) - 1 if days > 0 else 0
    bench_mrets = [bench_nav[i] / bench_nav[i - 1] - 1 if i > 0 else bench_nav[i] / b0 - 1 for i in range(len(bench_nav))]
    # 基准回撤/波动
    bpeak = bench_nav[0]; bmdd = 0.0
    for v in bench_nav:
        bpeak = max(bpeak, v)
        bmdd = min(bmdd, v / bpeak - 1)
    bm = len(bench_mrets)
    bmean = sum(bench_mrets) / bm if bm else 0
    bvar = sum((r - bmean) ** 2 for r in bench_mrets) / (bm - 1) if bm > 1 else 0
    bvol = math.sqrt(bvar * 12)

    # ---- 月度矩阵（年 × 月）----
    matrix = {}
    for i, d in enumerate(dates):
        y, mo = d[:4], int(d[5:7])
        r = mrets[i]
        matrix.setdefault(y, {"months": {}, "nav": vals[i]})
        matrix[y]["months"][mo] = r
        matrix[y]["nav"] = vals[i]
    # 年收益、月胜率、年内最大回撤（补充进 matrix）
    for y in matrix:
        mo = matrix[y]["months"]
        rets_y = [mo[k] for k in sorted(mo)]
        # 年收益 = 该年12月末nav / 上年12月末nav -1（用 annual 兜底）
        # 年内最大回撤
        yr_peak = -1e18; yr_mdd = 0.0
        cum = 1.0
        for k in sorted(mo):
            cum *= (1 + mo[k])
            yr_peak = max(yr_peak, cum)
            yr_mdd = min(yr_mdd, cum / yr_peak - 1)
        matrix[y]["win_rate"] = sum(1 for r in rets_y if r > 1e-9) / len(rets_y) if rets_y else 0
        matrix[y]["mdd"] = yr_mdd

    result = {
        "base": BASE, "end": dates[-1], "months": len(dates),
        "nav": nav,
        "monthly_returns": list(zip(dates, mrets)),
        "annual_returns": annual,
        "total_return": total_ret,
        "annualized_return": ann_ret,
        "annualized_volatility": vol,
        "max_drawdown": mdd,
        "sharpe": sharpe,
        "month_win_rate": win_rate,
        "positive_months": pos,
        "rebalance_count": sum(1 for d in dates if d[5:7] == "12"),
        "matrix": matrix,
        "benchmark": {
            "total_return": bench_ret_total,
            "annualized_return": bench_ann,
            "annualized_volatility": bvol,
            "max_drawdown": bmdd,
            "nav": list(zip(dates, bench_nav)),
            "monthly_returns": list(zip(dates, bench_mrets)),
        },
    }
    json.dump(result, open(os.path.join(HERE, "result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"区间 {BASE} ~ {dates[-1]}，{len(dates)} 个月")
    print(f"累计收益 {total_ret*100:.2f}%，年化 {ann_ret*100:.2f}%")
    print(f"年化波动率 {vol*100:.2f}%，最大回撤 {mdd*100:.2f}%，夏普 {sharpe:.2f}")
    print(f"月胜率 {win_rate*100:.1f}%（{pos}/{m}），动平衡 {result['rebalance_count']} 次")
    print(f"基准(同花顺全A加权 700001.TI) 累计 {bench_ret_total*100:.2f}%，年化 {bench_ann*100:.2f}%")
    print("年度收益：", {k: f"{v*100:.2f}%" for k, v in annual.items()})


if __name__ == "__main__":
    main()
