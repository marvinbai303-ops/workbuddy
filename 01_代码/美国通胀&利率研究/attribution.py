# -*- coding: utf-8 -*-
"""
美债利率上行风险跟踪 — 归因拆解 + 三拍传导状态机 + 历史回测校准

数据源：FRED（DGS2/5/10 名义、DFII5/10 实际、T5YIE/T10YIE 通胀预期、DFF 联邦基金利率）
         ACM 期限溢价（iFinD，维度三单独监控）

────────────────────────────────────────────────────────────────────
归因恒等式（严格成立、零模型误差）：
    Δ(名义) = Δ(实际利率) + Δ(通胀预期)
    DGS5  = DFII5 + T5YIE        （5Y 口径，主归因）
    DGS10 = DFII10 + T10YIE      （10Y 口径，交叉验证）

────────────────────────────────────────────────────────────────────
三拍传导状态机（严格对应君君视频原话）

  君君原话："这俩东西一块上——对于通胀这个预期再上，对于这个政策性利率
            这部分它也在上。两部分一起上的时候，就是美债加速上行的时候。"

  因此判定用「政策信号 × 通胀信号」的方向组合，而非占比：
    第一拍(绿)：Δ政策>0 且 Δ通胀≤0  → 纯政策驱动，正常回摆（君君：8:2）
    第二拍(黄)：Δ通胀>0（转正）但未达强度阈值 → 通胀预期启动，转入监控（5:5）
    第三拍(红)：Δ政策>0 且 Δ通胀>阈值 且 Δ名义加速>阈值 → 两者同推，美债加速上行

  说明：不使用「通胀贡献率=Δ通胀/Δ名义」作为主指标，因名义变动接近0时
        该比值数值不稳定（回测中出现过 -15、+16 等无意义值），
        且分布过于分散（44%季度>50%），不具备阈值可用性。
────────────────────────────────────────────────────────────────────
"""

import os
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

# 历史加息周期（FFR 上行区间）——用户确认的回测范围
CYCLES = {
    "1994-95": ("1994-02-01", "1995-02-01"),
    "2004-06": ("2004-06-01", "2006-06-30"),
    "2015-18": ("2015-12-01", "2018-12-31"),
    "2022-23": ("2022-03-01", "2023-07-31"),
}


def load_fred(series):
    df = pd.read_csv(os.path.join(DATA, f"fred_{series}.csv"))
    df.columns = ["date", series]
    df["date"] = pd.to_datetime(df["date"])
    df[series] = pd.to_numeric(df[series], errors="coerce")
    return df.set_index("date")[[series]]


def build_panel():
    parts = [load_fred(s) for s in ["DGS2", "DGS5", "DGS10", "DFII5", "DFII10",
                                    "T5YIE", "T10YIE", "DFF"]]
    df = pd.concat(parts, axis=1, sort=True).sort_index()
    df = df.dropna(subset=["DGS5", "DFII5", "T5YIE"])
    # 3个月（63交易日）滚动变动，单位 bp
    w = 63
    df["dN5"] = (df["DGS5"] - df["DGS5"].shift(w)) * 100
    df["dR5"] = (df["DFII5"] - df["DFII5"].shift(w)) * 100
    df["dI5"] = (df["T5YIE"] - df["T5YIE"].shift(w)) * 100
    df["dN10"] = (df["DGS10"] - df["DGS10"].shift(w)) * 100
    df["dI10"] = (df["T10YIE"] - df["T10YIE"].shift(w)) * 100
    df["dN2"] = (df["DGS2"] - df["DGS2"].shift(w)) * 100
    return df


def calibrate(df):
    """用历史分布校准阈值：通胀信号强度、名义加速强度"""
    d = df.dropna(subset=["dN5", "dI5"])
    return {
        "通胀ΔI_P50": d["dI5"].quantile(0.50),
        "通胀ΔI_P75": d["dI5"].quantile(0.75),
        "通胀ΔI_P90": d["dI5"].quantile(0.90),
        "名义ΔN_P50": d["dN5"].quantile(0.50),
        "名义ΔN_P75": d["dN5"].quantile(0.75),
        "名义ΔN_P90": d["dN5"].quantile(0.90),
    }


def state(dR, dI, dN, th_i, th_n):
    """三拍状态判定"""
    if dR is None or pd.isna(dI) or pd.isna(dN):
        return "数据不足"
    if dR > 0 and dI > th_i and dN > th_n:
        return "第三拍(红)"
    if dI > 0:
        return "第二拍(黄)"
    if dR > 0:
        return "第一拍(绿)"
    return "政策未上行"


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    pd.set_option("display.unicode.east_asian_width", True)
    df = build_panel()
    print(f"面板: {df.index[0].date()} ~ {df.index[-1].date()}  样本 {len(df)} 天")
    print("归因口径: Δ名义 = Δ实际利率(政策因素) + Δ通胀预期(通胀因素)  [5Y主 / 10Y校验]\n")

    print("=" * 104)
    print("一、阈值校准（3个月滚动变动，bp；2003年至今全样本分位）")
    print("=" * 104)
    th = calibrate(df)
    for k, v in th.items():
        print(f"  {k:16s}: {v:8.1f} bp")
    TH_I = th["通胀ΔI_P75"]
    TH_N = th["名义ΔN_P75"]
    print(f"\n  → 采用阈值: 通胀信号 ΔI > {TH_I:.0f}bp (P75) ；名义加速 ΔN > {TH_N:.0f}bp (P75)")

    print("\n" + "=" * 104)
    print("二、历史加息周期归因拆解（区间起止，5Y口径）")
    print("=" * 104)
    rows = []
    for name, (s, e) in CYCLES.items():
        seg = df.loc[(df.index >= s) & (df.index <= e)]
        if seg.empty:
            rows.append({"区间": name, "说明": "通胀预期数据自2003年起，该周期无法归因"})
            continue
        f0, f1 = seg.iloc[0], seg.iloc[-1]
        dN = (f1["DGS5"] - f0["DGS5"]) * 100
        dR = (f1["DFII5"] - f0["DFII5"]) * 100
        dI = (f1["T5YIE"] - f0["T5YIE"]) * 100
        rows.append({
            "区间": name,
            "起": f0.name.strftime("%Y-%m-%d"), "止": f1.name.strftime("%Y-%m-%d"),
            "Δ名义5Y": round(dN, 1), "Δ政策(实际)": round(dR, 1), "Δ通胀预期": round(dI, 1),
            "政策:通胀(绝对值)": f"{abs(dR)/(abs(dR)+abs(dI)):.2f}:{abs(dI)/(abs(dR)+abs(dI)):.2f}" if (abs(dR)+abs(dI)) > 0 else "-",
            "通胀是否推升": "是" if dI > 0 else "否",
        })
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n" + "=" * 104)
    print("三、历史周期内的三拍状态分布（回测验证状态机是否可识别传导）")
    print("=" * 104)
    for name, (s, e) in CYCLES.items():
        seg = df.loc[(df.index >= s) & (df.index <= e)]
        if seg.empty:
            continue
        seg = seg.dropna(subset=["dR5", "dI5", "dN5"])
        cnt = seg.apply(lambda r: state(r["dR5"], r["dI5"], r["dN5"], TH_I, TH_N), axis=1).value_counts()
        pct = (cnt / len(seg) * 100).round(1)
        print(f"\n  【{name}】样本 {len(seg)} 天")
        for k in cnt.index:
            print(f"    {k:12s}: {cnt[k]:5d} 天 ({pct[k]:5.1f}%)")

    print("\n" + "=" * 104)
    print("四、当前状态判定（最新读数 + 三拍状态）")
    print("=" * 104)
    last = df.iloc[-1]
    print(f"  数据日期        : {last.name.strftime('%Y-%m-%d')}")
    print(f"  2Y名义 / 10Y名义: {last['DGS2']:.2f}% / {last['DGS10']:.2f}%   (10Y-2Y 利差 {(last['DGS10']-last['DGS2'])*100:.0f}bp)")
    print(f"  5Y名义          : {last['DGS5']:.2f}%  = 实际 {last['DFII5']:.2f}% + 通胀预期 {last['T5YIE']:.2f}%")
    print(f"  10Y名义         : {last['DGS10']:.2f}% = 实际 {last['DFII10']:.2f}% + 通胀预期 {last['T10YIE']:.2f}%")
    print(f"  联邦基金利率 FFR: {last['DFF']:.2f}%")
    print(f"\n  近3个月变动(bp) : Δ名义5Y {last['dN5']:.0f} = Δ政策 {last['dR5']:.0f} + Δ通胀 {last['dI5']:.0f}")
    print(f"  近3个月2Y变动   : {last['dN2']:.0f}bp     近3个月10Y通胀预期: {last['dI10']:.0f}bp")
    st = state(last["dR5"], last["dI5"], last["dN5"], TH_I, TH_N)
    print(f"\n  >>> 三拍状态: 【{st}】")
    print(f"      判定依据: Δ政策={last['dR5']:.0f}bp(>0为政策上行)  "
          f"Δ通胀={last['dI5']:.0f}bp(阈值{TH_I:.0f}bp)  "
          f"Δ名义={last['dN5']:.0f}bp(阈值{TH_N:.0f}bp)")

    print("\n" + "=" * 104)
    print("五、近24个月状态演变（每月末采样）")
    print("=" * 104)
    m = df.resample("ME").last().dropna(subset=["dR5", "dI5", "dN5"]).tail(24)
    ev = pd.DataFrame({
        "2Y": m["DGS2"].round(2), "10Y": m["DGS10"].round(2), "FFR": m["DFF"].round(2),
        "Δ名义5Y": m["dN5"].round(0), "Δ政策": m["dR5"].round(0), "Δ通胀": m["dI5"].round(0),
        "状态": m.apply(lambda r: state(r["dR5"], r["dI5"], r["dN5"], TH_I, TH_N), axis=1),
    })
    print(ev.to_string())
