# -*- coding: utf-8 -*-
"""
今日（2026-11-16）大跌的场景判别表
用途：把「预估区间的分歧」转成「今晚净值落点 → 对应仓位状态」的判读尺
"""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("base", "持仓回归验证_组合2号.py")
base = importlib.util.module_from_spec(spec)
sys.modules["base"] = base
spec.loader.exec_module(base)

DATES, FUNDS = base.DATES, base.FUNDS
series_for, ols = base.series_for, base.ols

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

TH = {}
for k, codes in THEME.items():
    rs = [series_for(c) for c in codes]
    TH[k] = [sum(r[t] for r in rs) / len(rs) for t in range(len(DATES))]

TODAY = len(DATES) - 1


def grid(key, levels):
    """给定赛道，按不同 β 推算今日涨跌"""
    th = TH[MAP[key]]
    return [(b, b * th[TODAY]) for b in levels]


def factor_decomp(key, lo, hi):
    """对三条赛道做无约束多元回归，返回暴露权重（% 净资产）"""
    y = FUNDS[key]["nav"][lo:hi]
    xs = [[TH[name][t] for t in range(lo, hi)] for name in TH]
    # 正规方程（3 变量）
    import itertools
    n = len(xs)
    A = [[sum(xs[i][k] * xs[j][k] for k in range(len(y))) for j in range(n)] for i in range(n)]
    b = [sum(xs[i][k] * y[k] for k in range(len(y))) for i in range(n)]
    # 高斯消元
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12:
            return None
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c and abs(M[r][c]) > 1e-15:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


if __name__ == "__main__":
    print("=" * 92)
    print("今日赛道涨跌（等权口径）")
    for k in TH:
        print(f"  {k:<12}{TH[k][TODAY]:>8.2f}%")

    print("\n" + "=" * 92)
    print("宏利复兴伟业（017612 / 001170）：今晚净值 → 仓位状态 判别表")
    print("=" * 92)
    print(f"{'今日涨跌':>9}{'β':>6}{'有效股票仓位':>12}{'对应状态':>26}")
    for b in [0.94, 0.80, 0.63, 0.50, 0.45, 0.35, 0.28, 0.20, 0.10, 0.0]:
        pos = b / 0.93
        tag = ""
        if abs(b - 0.94) < 1e-9: tag = "10月水平，完全没动"
        elif abs(b - 0.63) < 1e-9: tag = "10月下旬已减到约七成"
        elif abs(b - 0.28) < 1e-9: tag = "11月水平，约三成"
        elif b == 0.0: tag = "清空或完全对冲"
        print(f"{b * TH['光模块产业链'][TODAY]:>8.2f}%{b:>6.2f}{pos:>11.0%}  {tag:>26}")

    print("\n" + "=" * 92)
    print("结构分解：11 月 10 个交易日对三条赛道做多元回归（无约束，暴露 = %净资产）")
    print("=" * 92)
    print(f"{'基金':<16}{'光模块':>9}{'半导体设备':>11}{'存储/算力':>11}{'残差仓位':>9}")
    for k in ORDER:
        e = factor_decomp(k, 16, 26)
        if e is None:
            print(f"{FUNDS[k]['name']:<16}   解不稳定")
            continue
        cash = 100 - sum(e)
        print(f"{FUNDS[k]['name']:<16}{e[0]:>9.1f}{e[1]:>11.1f}{e[2]:>11.1f}{cash:>9.1f}")

    print("\n" + "=" * 92)
    print("七只基金今日锚点：不同仓位假设下的涨跌")
    print("=" * 92)
    print(f"{'基金':<16}{'赛道':<12}{'满仓(β0.93)':>12}{'七成':>8}{'半仓':>8}{'三成':>8}")
    for k in ORDER:
        th = TH[MAP[k]][TODAY]
        print(f"{FUNDS[k]['name']:<16}{MAP[k]:<12}{0.93*th:>11.2f}%{0.70*th:>7.2f}%"
              f"{0.50*th:>7.2f}%{0.30*th:>7.2f}%")
