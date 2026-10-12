# -*- coding: utf-8 -*-
"""
PCLI-Beta v3 计算 + 前瞻性回测
升级点：
  1. S3 有效供给改用「季度官方生猪出栏量 TTM 同比」（国家统计局，口径稳定）替代猪价
  2. S4 效率修正改用「出栏量TTM / 能繁母猪」的同比（官方口径）
  3. 能繁母猪历史延长到 2011 年，并处理 2020 年监测口径断点
  4. 与中证畜牧 930707（绝对）+ 相对沪深300（相对）做前瞻性拟合
"""
import json, csv

# ============ 数据 ============
# 能繁母猪存栏（万头，农业农村部，月度；2020 年监测口径调整，4/5/7/8/11 月停发）
sow = {
"2011-01":4740,"2011-02":4730,"2011-03":4710,"2011-04":4695,"2011-05":4710,"2011-06":4720,
"2011-07":4786,"2011-08":4815,"2011-09":4845,"2011-10":4880,"2011-11":4905,"2011-12":4928,
"2012-01":4950,"2012-02":4949,"2012-03":4954,"2012-04":4954,"2012-05":4949,"2012-06":4954,
"2012-07":4939,"2012-08":4959,"2012-09":5063,"2012-10":5078,"2012-11":5063,"2012-12":5068,
"2013-01":5068,"2013-02":5058,"2013-03":5033,"2013-04":5013,"2013-05":5013,"2013-06":5008,
"2013-07":4998,"2013-08":5013,"2013-09":5008,"2013-10":4998,"2013-11":4973,"2013-12":4938,
"2014-01":4908,"2014-02":4869,"2014-03":4791,"2014-04":4686,"2014-05":4639,"2014-06":4593,
"2014-07":4538,"2014-08":4502,"2014-09":4479,"2014-10":4421,"2014-11":4368,"2014-12":4289,
"2015-01":4190,"2015-02":4110,"2015-03":4040,"2015-04":3971,"2015-05":3923,"2015-06":3899,
"2015-07":3876,"2015-08":3860,"2015-09":3852,"2015-10":3848,"2015-11":3825,"2015-12":3798,
"2016-01":3783,"2016-02":3760,"2016-03":3760,"2016-04":3771,"2016-05":3760,"2016-06":3760,
"2016-07":3752,"2016-08":3729,"2016-09":3710,"2016-10":3703,"2016-11":3684,"2016-12":3666,
"2017-01":3651,"2017-02":3633,"2017-03":3633,"2017-04":3633,"2017-05":3604,"2017-06":3586,
"2017-07":3554,"2017-08":3522,"2017-09":3497,"2017-10":3487,"2017-11":3466,"2017-12":3424,
"2018-01":3414,"2018-02":3414,"2018-03":3417,"2018-04":3369,"2018-05":3285,"2018-06":3242,
"2018-07":3180,"2018-08":3145,"2018-09":3136,"2018-10":3098,"2018-11":3058,"2018-12":2988,
"2019-01":2882,"2019-02":2738,"2019-03":2675,"2019-04":2608,"2019-05":2501,"2019-06":2376,
"2019-07":2165,"2019-08":1968,"2019-09":1913,"2019-10":1924,"2019-11":2001,"2019-12":2045,
"2020-01":2070,"2020-02":2105,"2020-03":2164,"2020-06":3629,"2020-09":3822,"2020-10":3950,"2020-12":4161,
"2021-03":4318,"2021-06":4564,"2021-07":4541,"2021-08":4500,"2021-09":4459,"2021-10":4348,"2021-11":4296,"2021-12":4329,
"2022-01":4290,"2022-02":4268,"2022-03":4185,"2022-04":4177,"2022-05":4192,"2022-06":4277,
"2022-07":4298,"2022-08":4324,"2022-09":4362,"2022-10":4379,"2022-11":4388,"2022-12":4390,
"2023-01":4367,"2023-02":4343,"2023-03":4305,"2023-04":4284,"2023-05":4258,"2023-06":4296,
"2023-07":4271,"2023-08":4241,"2023-09":4240,"2023-10":4210,"2023-11":4158,"2023-12":4142,
"2024-01":4067,"2024-02":4042,"2024-03":3992,"2024-04":3986,"2024-05":3996,"2024-06":4038,
"2024-07":4041,"2024-08":4036,"2024-09":4062,"2024-10":4073,"2024-11":4080,"2024-12":4078,
"2025-01":4062,"2025-02":4066,"2025-03":4039,"2025-04":4038,"2025-05":4042,"2025-06":4043,
"2025-07":4042,"2025-08":4038,"2025-09":4035,"2025-10":3990,"2025-12":3961,
"2026-03":3904,"2026-06":3780,
}

# 季度生猪出栏量（当季值，万头，国家统计局，V4783066）
slaughter_q = {
"2012-03":19989,"2012-06":13848,"2012-09":15461,"2012-12":20330,
"2013-03":20489,"2013-06":13722,"2013-09":16048,"2013-12":21298,
"2014-03":21096,"2014-06":14126,"2014-09":16672,"2014-12":21616,
"2015-03":20311,"2015-06":13126,"2015-09":16317,"2015-12":21071,
"2016-03":19111,"2016-06":12848,"2016-09":15965,"2016-12":20578,
"2017-03":19149,"2017-06":13034,"2017-09":16041,"2017-12":20637,
"2018-03":19983,"2018-06":13439,"2018-09":16157,"2018-12":19803,
"2019-03":18842,"2019-06":12504,"2019-09":9632,"2019-12":13441,
"2020-03":13129,"2020-06":11974,"2020-09":11083,"2020-12":16518,
"2021-03":17143,"2021-06":16599,"2021-09":15451,"2021-12":17935,
"2022-03":19566,"2022-06":17021,"2022-09":15443,"2022-12":17965,
"2023-03":19899,"2023-06":17649,"2023-09":16175,"2023-12":18939,
"2024-03":19455,"2024-06":16940,"2024-09":15635,"2024-12":18226,
"2025-03":19476,"2025-06":17143,"2025-09":16373,"2025-12":18981,
"2026-03":20026,"2026-06":17220,
}

# 自繁自养利润（元/头，博亚和讯，月度，2021-08 起）
profit = {
"2021-10":-481.85,"2021-11":82.37,"2021-12":39.71,
"2022-01":-248.64,"2022-02":-405.41,"2022-03":-524.00,"2022-04":-424.22,"2022-05":-200.50,"2022-06":-57.89,
"2022-07":574.26,"2022-08":517.50,"2022-09":734.08,"2022-10":1093.91,"2022-11":853.16,"2022-12":249.76,
"2023-01":-258.51,"2023-02":-337.01,"2023-03":-226.60,"2023-04":-336.47,"2023-05":-327.36,"2023-06":-314.50,
"2023-07":-336.50,"2023-08":22.73,"2023-09":-22.92,"2023-10":-139.13,"2023-11":-232.94,"2023-12":-238.50,
"2024-01":-245.26,"2024-02":-119.17,"2024-03":-145.83,"2024-04":-36.34,"2024-05":30.87,"2024-06":376.17,
"2024-07":404.58,"2024-08":636.58,"2024-09":484.84,"2024-10":313.75,"2024-11":207.96,"2024-12":151.77,
"2025-01":165.76,"2025-02":70.17,"2025-03":39.48,"2025-04":69.44,"2025-05":61.69,"2025-06":24.21,
"2025-07":101.66,"2025-08":35.98,"2025-09":-7.26,"2025-10":-169.60,"2025-11":-120.69,"2025-12":-148.33,
"2026-01":7.33,"2026-02":-92.72,"2026-03":-290.77,"2026-04":-378.51,"2026-05":-338.23,"2026-06":-345.97,
"2026-07":-209.02,"2026-08":-195.14,"2026-09":-198.47,
}

# 中证畜牧 930707 月线收盘（2021-02 起，通达信）
csi = {
"2021-02":3792.08,"2021-03":3513.23,"2021-04":3482.39,"2021-05":3224.92,"2021-06":3086.84,
"2021-07":2638.25,"2021-08":2571.21,"2021-09":2854.12,"2021-10":2950.32,"2021-11":2934.88,"2021-12":3242.39,
"2022-01":3126.19,"2022-02":3076.50,"2022-03":3199.84,"2022-04":2698.30,"2022-05":2785.04,"2022-06":2981.24,
"2022-07":3140.66,"2022-08":3176.06,"2022-09":2835.71,"2022-10":2708.15,"2022-11":2842.87,"2022-12":2814.00,
"2023-01":2929.69,"2023-02":2956.75,"2023-03":2891.27,"2023-04":2715.09,"2023-05":2410.03,"2023-06":2465.78,
"2023-07":2615.37,"2023-08":2388.04,"2023-09":2351.75,"2023-10":2344.92,"2023-11":2401.56,"2023-12":2383.42,
"2024-01":2031.58,"2024-02":2163.86,"2024-03":2223.37,"2024-04":2221.13,"2024-05":2310.82,"2024-06":2044.41,
"2024-07":2029.43,"2024-08":1845.47,"2024-09":2175.35,"2024-10":2058.75,"2024-11":2076.95,"2024-12":2011.75,
"2025-01":1948.37,"2025-02":1939.72,"2025-03":1996.82,"2025-04":2069.15,"2025-05":2105.55,"2025-06":2088.08,
"2025-07":2179.83,"2025-08":2288.60,"2025-09":2288.57,"2025-10":2263.32,"2025-11":2236.91,"2025-12":2207.34,
"2026-01":2242.27,"2026-02":2236.73,"2026-03":2090.57,"2026-04":2156.69,"2026-05":1896.55,"2026-06":1702.08,
"2026-07":1854.03,"2026-08":1905.40,"2026-09":1843.60,
}

# 沪深300 月线收盘（2021-02 起，通达信）
hs300 = {
"2021-02":5336.76,"2021-03":5048.36,"2021-04":5123.49,"2021-05":5331.57,"2021-06":5224.04,
"2021-07":4811.17,"2021-08":4805.61,"2021-09":4866.38,"2021-10":4908.77,"2021-11":4832.03,"2021-12":4940.37,
"2022-01":4563.77,"2022-02":4581.65,"2022-03":4222.60,"2022-04":4016.24,"2022-05":4091.52,"2022-06":4485.01,
"2022-07":4170.10,"2022-08":4078.84,"2022-09":3804.89,"2022-10":3508.70,"2022-11":3853.04,"2022-12":3871.63,
"2023-01":4156.86,"2023-02":4069.46,"2023-03":4050.93,"2023-04":4029.09,"2023-05":3798.54,"2023-06":3842.45,
"2023-07":4014.63,"2023-08":3765.27,"2023-09":3689.52,"2023-10":3572.51,"2023-11":3496.20,"2023-12":3431.11,
"2024-01":3215.35,"2024-02":3516.08,"2024-03":3537.48,"2024-04":3604.39,"2024-05":3579.92,"2024-06":3461.66,
"2024-07":3442.08,"2024-08":3321.43,"2024-09":4017.85,"2024-10":3891.04,"2024-11":3916.58,"2024-12":3934.91,
"2025-01":3817.08,"2025-02":3890.05,"2025-03":3887.31,"2025-04":3770.57,"2025-05":3840.23,"2025-06":3936.08,
"2025-07":4075.59,"2025-08":4496.76,"2025-09":4640.69,"2025-10":4640.67,"2025-11":4526.66,"2025-12":4629.94,
"2026-01":4706.34,"2026-02":4710.65,"2026-03":4450.05,"2026-04":4807.31,"2026-05":4892.12,"2026-06":4979.43,
"2026-07":4588.20,"2026-08":4625.09,"2026-09":4357.62,
}

# ============ 工具函数 ============
def months_range(start, end):
    out = []
    y, m = map(int, start.split('-')); ey, em = map(int, end.split('-'))
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}"); m += 1
        if m == 13: m = 1; y += 1
    return out

def shift_month(m, k):
    y, mo = map(int, m.split('-'))
    idx = y * 12 + (mo - 1) + k
    return f"{idx//12:04d}-{idx%12+1:02d}"

def month_index(m):
    y, mo = map(int, m.split('-')); return y*12 + (mo-1)

def clip(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))

# 能繁母猪线性插值（补 2020 停发月 + 2025-11 + 2026-01/02 等缺口）
def fill_monthly(data):
    keys = sorted(data.keys()); full = months_range(keys[0], keys[-1])
    out = {}
    for m in full:
        if m in data: out[m] = data[m]
    for m in full:
        if m in out: continue
        prev_m = next((mm for mm in reversed(keys) if mm < m), None)
        next_m = next((mm for mm in keys if mm > m), None)
        if prev_m and next_m:
            d0 = month_index(m)-month_index(prev_m); d1 = month_index(next_m)-month_index(m)
            out[m] = out[prev_m] + (out[next_m]-out[prev_m])*d0/(d0+d1)
        elif prev_m: out[m] = out[prev_m]
        elif next_m: out[m] = out[next_m]
    return out

sow_f = fill_monthly(sow)

# 季度出栏量 -> 月度阶梯（每季度末值，向前填充到该季度三个月）
def quarter_to_monthly(qdata):
    out = {}
    for q, v in sorted(qdata.items()):
        y, m = map(int, q.split('-')); m -= 1
        for i in range(3):
            out[f"{y:04d}-{m+1:02d}"] = v  # 季度内三个月同值
            m += 1
    return out

# 季度出栏 TTM 同比：用季度序列直接算，再映射到月度
def quarter_ttm_yoy(qdata):
    """返回 {季度末月份: TTM同比%}，TTM=过去4季累计"""
    qs = sorted(qdata.keys())
    res = {}
    for i in range(7, len(qs)):
        cur = sum(qdata[qs[j]] for j in range(i-3, i+1))
        prev = sum(qdata[qs[j]] for j in range(i-7, i-3))
        res[qs[i]] = (cur/prev - 1) * 100
    return res

# ============ 参数 ============
W = [0.45, 0.25, 0.20, 0.10]
K_SOW, K_PIGLET, K_SLAUGHTER, K_EFF = 6.0, 6.0, 8.0, 5.0
BREAK = "2020-06"  # 能繁母猪口径断点（新口径起始）

q_ttm = quarter_ttm_yoy(slaughter_q)  # {季度末月: TTM同比%}

def quarter_month_series():
    """把季度 TTM 同比和效率比映射到月度（每季度末月更新）"""
    ttm_m = {}
    eff_m = {}
    qs = sorted(q_ttm.keys())
    for q in qs:
        y, m = map(int, q.split('-')); m -= 1
        # 该季度三个月用季度末值
        for i in range(3):
            mon = f"{y:04d}-{m+1:02d}"
            ttm_m[mon] = q_ttm[q]
            m += 1
    # 效率比 = 出栏TTM / 能繁母猪（季度末）
    # 出栏 TTM（万头）需要季度累计
    qs_all = sorted(slaughter_q.keys())
    for i in range(7, len(qs_all)):
        cur = sum(slaughter_q[qs_all[j]] for j in range(i-3, i+1))
        q = qs_all[i]
        y, m = map(int, q.split('-')); m -= 1
        for k in range(3):
            mon = f"{y:04d}-{m+1:02d}"
            if mon in sow_f:
                eff_m[mon] = cur / sow_f[mon]
            m += 1
    return ttm_m, eff_m

ttm_m, eff_m = quarter_month_series()

# 效率比同比（月度，季度阶梯）
eff_yoy_m = {}
for m in eff_m:
    m12 = shift_month(m, -12)
    if m12 in eff_m:
        eff_yoy_m[m] = (eff_m[m]/eff_m[m12] - 1) * 100

# ============ 计算 PCLI ============
def yoy_sow_safe(m):
    """能繁母猪同比，含口径断点保护"""
    m12 = shift_month(m, -12)
    if m not in sow_f or m12 not in sow_f:
        return None
    # 断点保护：t 与 t-12 跨口径（一个在新口径、一个在旧口径）则同比失真
    if (m < BREAK) != (m12 < BREAK):
        return None
    return (sow_f[m]/sow_f[m12] - 1) * 100

rows = []
pcli_range = months_range('2013-01', '2026-06')
for m in pcli_range:  # PCLI 完整历史（S3 出栏量从 2013 起可算）
    if m not in sow_f: continue
    row = {'month': m}
    # S1
    y1 = yoy_sow_safe(m)
    s1 = clip(50 - K_SOW*y1) if y1 is not None else None
    # S2: 能繁 lag4 同比（断点保护）
    ml4 = shift_month(m, -4)
    y2 = yoy_sow_safe(ml4) if ml4 in sow_f else None
    s2 = clip(50 - K_PIGLET*y2) if y2 is not None else None
    # S3: 出栏 TTM 同比
    y3 = ttm_m.get(m)
    s3 = clip(50 - K_SLAUGHTER*y3) if y3 is not None else None
    # S4: 效率比同比
    y4 = eff_yoy_m.get(m)
    s4 = clip(50 - K_EFF*y4) if y4 is not None else None
    # Stress
    pr = profit.get(m)
    stress = clip(50 - pr*0.1) if pr is not None else None

    row['sow'] = round(sow_f[m],1)
    row['yoy_sow'] = round(y1,2) if y1 is not None else None
    row['yoy_slaughter_ttm'] = round(y3,2) if y3 is not None else None
    row['yoy_eff'] = round(y4,2) if y4 is not None else None
    row['s1'] = round(s1,2) if s1 is not None else None
    row['s2'] = round(s2,2) if s2 is not None else None
    row['s3'] = round(s3,2) if s3 is not None else None
    row['s4'] = round(s4,2) if s4 is not None else None
    row['stress'] = round(stress,2) if stress is not None else None

    comps = [s1, s2, s3, s4]
    if all(c is not None for c in comps):
        row['pcli'] = round(sum(w*c for w,c in zip(W,comps)),2)
    else:
        row['pcli'] = None
    rows.append(row)

rows.sort(key=lambda r: r['month'])

# ============ 回测：PCLI 前瞻 vs 中证畜牧绝对/相对 ============
csi_keys = sorted(csi.keys())
def fwd_return(keys, values, i, n):
    """从 i 起未来 n 个月累计收益（用 i 月收盘到 i+n 月收盘）"""
    if i + n >= len(keys): return None
    return values[keys[i+n]]/values[keys[i]] - 1

# 相对沪深300：中证畜牧收益 - 沪深300收益
rel_ret = {}
for m in csi_keys:
    if m in hs300:
        rel_ret[m] = None  # 占位

# 逐月计算前瞻收益（绝对 & 相对）
def status(p):
    if p is None: return None
    if p < 55: return 'OFF'
    if p <= 70: return 'WATCH'
    return 'ON'

backtest = []
for i, m in enumerate(csi_keys):
    r = next((x for x in rows if x['month']==m), None)
    p = r['pcli'] if r else None
    st = status(p)
    for n in (3, 6, 12):
        fa = fwd_return(csi_keys, csi, i, n)
        # 相对收益：csi 未来收益 - hs300 未来收益
        fr = None
        if m in hs300 and i+n < len(csi_keys):
            fr = fwd_return(csi_keys, csi, i, n)
            fr300 = fwd_return(csi_keys, hs300, i, n)
            if fr300 is not None:
                fr = fr - fr300
        backtest.append({'month':m, 'pcli':p, 'status':st, 'n':n, 'fwd_abs':fa, 'fwd_rel':fr})

# 汇总统计
def summarize(bt, key, n):
    """按状态分组，统计前瞻收益"""
    stat = {}
    for rec in bt:
        if rec['n'] != n or rec['status'] is None: continue
        v = rec[key]
        if v is None: continue
        st = rec['status']
        stat.setdefault(st, []).append(v)
    out = {}
    for st, vals in stat.items():
        import statistics as stt
        win = sum(1 for v in vals if v > 0)/len(vals)*100
        out[st] = {'n':len(vals), 'mean':round(stt.mean(vals)*100,2), 'median':round(stt.median(vals)*100,2), 'win_rate':round(win,1)}
    return out

print("="*70)
print("PCLI-Beta v3 前瞻性回测（中证畜牧 930707，2021-02 ~ 2026-09）")
print("="*70)
print(f"\n【前瞻 6 个月 · 绝对收益】按 PCLI 状态分组：")
for st, v in summarize(backtest, 'fwd_abs', 6).items():
    print(f"  {st:6s}: 样本{v['n']:2d} 均值{v['mean']:+.1f}% 中位{v['median']:+.1f}% 上涨概率{v['win_rate']}%")
print(f"\n【前瞻 6 个月 · 相对沪深300超额】按 PCLI 状态分组：")
for st, v in summarize(backtest, 'fwd_rel', 6).items():
    print(f"  {st:6s}: 样本{v['n']:2d} 均值{v['mean']:+.1f}% 中位{v['median']:+.1f}% 跑赢概率{v['win_rate']}%")

print(f"\n【前瞻 3 个月 · 相对超额】按状态：")
for st, v in summarize(backtest, 'fwd_rel', 3).items():
    print(f"  {st:6s}: 样本{v['n']:2d} 均值{v['mean']:+.1f}% 跑赢概率{v['win_rate']}%")

# ============ ΔPCLI 边际变化检验 ============
# 原讨论核心：交易的是 PCLI 的「二阶变化」（边际走强），而非绝对水平
pcli_series = {r['month']: r['pcli'] for r in rows if r['pcli'] is not None}
delta_bt = []
for i, m in enumerate(csi_keys):
    if i == 0: continue
    prev_m = csi_keys[i-1]
    if m not in pcli_series or prev_m not in pcli_series: continue
    dpcli = pcli_series[m] - pcli_series[prev_m]
    for n in (3, 6):
        fa = fwd_return(csi_keys, csi, i, n)
        fr = None
        if m in hs300:
            fr300 = fwd_return(csi_keys, hs300, i, n)
            if fr300 is not None and fa is not None:
                fr = fa - fr300
        delta_bt.append({'month':m,'dpcli':dpcli,'n':n,'fwd_abs':fa,'fwd_rel':fr})

def summarize_delta(bt, key, n, sign):
    vals = [r[key] for r in bt if r['n']==n and r[key] is not None and ((r['dpcli']>0) if sign=='up' else (r['dpcli']<0))]
    if not vals: return None
    import statistics as stt
    win = sum(1 for v in vals if v>0)/len(vals)*100
    return {'n':len(vals),'mean':round(stt.mean(vals)*100,2),'win_rate':round(win,1)}

print(f"\n【前瞻 6 个月 · 相对超额】按 PCLI 月度变化（ΔPCLI）分组：")
for sign, lab in [('up','ΔPCLI>0 上升'),('down','ΔPCLI<0 下降')]:
    v = summarize_delta(delta_bt, 'fwd_rel', 6, sign)
    if v: print(f"  {lab:16s}: 样本{v['n']:2d} 均值{v['mean']:+.1f}% 跑赢概率{v['win_rate']}%")
print(f"\n【前瞻 6 个月 · 绝对收益】按 ΔPCLI 分组：")
for sign, lab in [('up','ΔPCLI>0 上升'),('down','ΔPCLI<0 下降')]:
    v = summarize_delta(delta_bt, 'fwd_abs', 6, sign)
    if v: print(f"  {lab:16s}: 样本{v['n']:2d} 均值{v['mean']:+.1f}% 上涨概率{v['win_rate']}%")

# 输出 JSON
out = {
    'rows': rows,
    'backtest': backtest,
    'summary': {
        'fwd6_abs': summarize(backtest, 'fwd_abs', 6),
        'fwd6_rel': summarize(backtest, 'fwd_rel', 6),
        'fwd3_rel': summarize(backtest, 'fwd_rel', 3),
        'fwd12_abs': summarize(backtest, 'fwd_abs', 12),
        'fwd12_rel': summarize(backtest, 'fwd_rel', 12),
        'delta6_rel_up': summarize_delta(delta_bt, 'fwd_rel', 6, 'up'),
        'delta6_rel_down': summarize_delta(delta_bt, 'fwd_rel', 6, 'down'),
        'delta6_abs_up': summarize_delta(delta_bt, 'fwd_abs', 6, 'up'),
        'delta6_abs_down': summarize_delta(delta_bt, 'fwd_abs', 6, 'down'),
    },
    'csi': csi, 'hs300': hs300,
    'meta': {
        'model': 'PCLI-Beta v3',
        'weights': {'S1母猪产能收缩':0.45,'S2仔猪管线收缩':0.25,'S3有效供给收缩':0.20,'S4效率反向修正':0.10},
        'k': {'sow':6,'piglet':6,'slaughter':8,'eff':5},
        'thresholds': {'off':55,'watch_hi':70},
    }
}
with open('PCLI_v3_result.json','w',encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

# 打印最新
latest = [r for r in rows if r['pcli'] is not None][-1]
print(f"\n最新 PCLI（{latest['month']}）= {latest['pcli']}（{status(latest['pcli'])}）")
print(f"  S1母猪={latest['s1']}(能繁YoY {latest['yoy_sow']}%)  S2仔猪={latest['s2']}  S3供给={latest['s3']}(出栏TTM YoY {latest['yoy_slaughter_ttm']}%)  S4效率={latest['s4']}  Stress={latest['stress']}")

# 关键拐点
print("\n关键拐点 PCLI：")
for ym in ['2019-09','2020-06','2021-06','2022-10','2023-06','2024-04','2025-06','2026-06']:
    r = next((x for x in rows if x['month']==ym), None)
    if r and r['pcli'] is not None:
        print(f"  {ym}: PCLI={r['pcli']:5.1f} S1={r['s1']:5.1f} S2={r['s2']:5.1f} S3={r['s3']:5.1f} S4={r['s4']:5.1f}")
