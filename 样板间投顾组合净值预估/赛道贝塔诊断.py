# -*- coding: utf-8 -*-
"""
单只基金 · 赛道 β 诊断
用现有个股池构造 3 条赛道指数（等权），回归基金净值，判断 降仓 / 换股 / 换赛道
"""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("base", "持仓回归验证_组合2号.py")
base = importlib.util.module_from_spec(spec)
sys.modules["base"] = base
spec.loader.exec_module(base)

DATES, STK, FUNDS = base.DATES, base.STK, base.FUNDS
series_for, ols, metrics = base.series_for, base.ols, base.metrics
implied, seg_beta = base.implied, base.seg_beta

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


def theme_ret(name):
    codes = THEME[name]
    allr = [series_for(c) for c in codes]
    return [sum(r[t] for r in allr) / len(allr) for t in range(len(DATES))]


def fit(act, x, lo, hi):
    a = act[lo:hi]
    b = x[lo:hi]
    alpha, beta, r2 = ols(b, a)
    return alpha, beta, r2


def main():
    idx = {k: theme_ret(k) for k in THEME}
    print("=" * 104)
    print("赛道 β 诊断｜2026-10-09 ~ 2026-11-13｜赛道指数 = 该赛道成员股等权，日收益")
    print("=" * 104)
    rows = []
    for key in ORDER:
        f = FUNDS[key]
        act = f["nav"]
        th = MAP[key]
        x = idx[th]
        a_all, b_all, r_all = fit(act, x, 0, 26)
        a_o, b_o, r_o = fit(act, x, 0, 16)
        a_n, b_n, r_n = fit(act, x, 16, 26)
        imp, _ = implied(key)
        m_nm = metrics(act, imp[:26])
        # 若分类有疑问，同时给出对另一条赛道的拟合
        alt = {t: fit(act, idx[t], 0, 26)[2] for t in idx if t != th}
        rows.append(dict(key=key, name=f["name"], th=th, b=b_all, r2=r_all,
                         bo=b_o, r_o=r_o, bn=b_n, r_n=r_n,
                         mae=m_nm["mae"], r2nm=m_nm["r2"], alt=alt))

    print(f"{'代码':<8}{'基金':<15}{'赛道':<10}{'β全期':>8}{'R²':>7}{'β10月':>8}{'β11月':>8}"
          f"{'β比':>7}{'R²10月':>8}{'R²11月':>8}{'换手后ρ':>9}")
    print("-" * 104)
    for r in rows:
        ratio = r["bn"] / r["bo"] if r["bo"] else float("nan")
        print(f"{r['key']:<8}{r['name']:<15}{r['th']:<10}{r['b']:>8.2f}{r['r2']:>7.3f}"
              f"{r['bo']:>8.2f}{r['bn']:>8.2f}{ratio:>7.2f}{r['r_o']:>8.3f}{r['r_n']:>8.3f}{r['r2nm']:>9.3f}")

    print("\n" + "=" * 104)
    print("诊断（判定规则：β比 = β11月/β10月，用于识别降仓；R²对比用于识别换股）")
    print("=" * 104)
    for r in rows:
        ratio = r["bn"] / r["bo"]
        if ratio < 0.80:
            verdict = f"降仓 —— 11 月有效暴露降至 10 月的 {ratio:.0%}"
        elif r["r_n"] >= 0.90 and r["r2nm"] < r["r_n"] - 0.15:
            verdict = "同赛道换股 —— 赛道拟合优于个股拟合"
        elif ratio > 1.20:
            verdict = f"加仓 —— 11 月暴露升至 10 月的 {ratio:.0%}"
        else:
            verdict = "无异常 —— 持仓仍具代表性"
        alt_txt = "；".join(f"{t} R²={v:.3f}" for t, v in r["alt"].items())
        print(f"\n{r['key']} {r['name']}（{r['th']}）")
        print(f"  个股法：R²={r['r2nm']:.3f}  MAE={r['mae']:.0f}bp")
        print(f"  赛道法：β={r['b']:.2f}  R²={r['r2']:.3f} ｜ 10月 β={r['bo']:.2f} R²={r['r_o']:.3f}"
              f" ｜ 11月 β={r['bn']:.2f} R²={r['r_n']:.3f}")
        print(f"  对照：{alt_txt}")
        print(f"  结论：{verdict}")
    return rows, idx


if __name__ == "__main__":
    main()
