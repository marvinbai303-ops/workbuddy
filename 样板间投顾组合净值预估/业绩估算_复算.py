# -*- coding: utf-8 -*-
"""用 iFinD 接口取到的净值（估值日 2026-10-08）复算 5 张业绩估算表，并渲染成带水印的图片。"""
import json, datetime
from openpyxl import load_workbook
from PIL import Image, ImageDraw, ImageFont

XLSX = "样板间投顾组合监控模板-精简版-0917更新.xlsx"
NAVJSON = "iFinD接口净值_估值日20261008.json"
OUT = "业绩估算表_20261008"
WATERMARK = "内部参考 · 请勿外发"

NAV = json.load(open(NAVJSON, encoding="utf-8"))
LATEST = "2026-10-08"          # 估值基准净值日（昨天）
PREV = "2026-09-30"            # 上一交易日（国庆假期 10/1-10/7 休市）
WEEK = "2026-09-30"            # 上周最后一个交易日

wb = load_workbook(XLSX, data_only=True)
cfgws, stgws = wb["实盘持仓配置"], wb["分期持仓明细"]


def w_of_cfg(row):
    return {c: (cfgws.cell(row, 1 + c).value or 0) for c in range(1, 38)}


def w_of_stg(row):
    return {c: (stgws.cell(row, 1 + c).value or 0) for c in range(1, 38)}


codes = [wb["实盘净值数据(iFinD公式)"].cell(3, c).value for c in range(2, 39)]


def sp(w, d_num, d_den, cols):
    s = 0.0
    for c in cols:
        if not w.get(c, 0):
            continue
        code = codes[c - 1]
        s += w[c] * NAV[d_num][code] / NAV[d_den][code]
    return s


C24, C26, C37 = list(range(1, 25)), list(range(1, 27)), list(range(1, 38))
FEE = {"产业趋势": 0.015, "产业趋势基石": 0.012, "产业趋势2号": 0.015, "10-90": 0.008,
       "10-90基石": 0.005, "30-70": 0.012, "20-80": 0.008}
START = {"产业趋势": "2026-06-22", "产业趋势基石": "2026-06-18", "产业趋势2号": "2026-06-23",
         "10-90": "2026-06-24", "10-90基石": "2026-06-18", "30-70": "2026-06-24", "20-80": "2026-09-17"}
# 每组合：(权重行来源, 行号, 列范围, 段基准日) 列表；结转因子在各段处连乘
SEG = {
 "产业趋势": [("cfg", 4, C24[:23], "2026-06-22"), ("stg", 17, C24, "2026-07-10")],
 "产业趋势基石": [("cfg", 5, C24[:23], "2026-06-18"), ("stg", 18, C24, "2026-07-10")],
 "产业趋势2号": [("cfg", 6, C24[:23], "2026-06-23"), ("stg", 19, C24, "2026-07-10")],
 "10-90": [("cfg", 7, C24[:23], "2026-06-24"), ("stg", 9, C24, "2026-07-01"),
           ("stg", 14, C24, "2026-07-07"), ("stg", 20, C24, "2026-07-17"), ("stg", 23, C26, "2026-09-11")],
 "10-90基石": [("cfg", 8, C24[:23], "2026-06-18"), ("stg", 11, C24, "2026-07-01"),
              ("stg", 15, C24, "2026-07-07"), ("stg", 21, C24, "2026-07-17"), ("stg", 24, C26, "2026-09-11")],
 "30-70": [("cfg", 9, C24[:23], "2026-06-24"), ("stg", 13, C24, "2026-07-01"),
           ("stg", 16, C24, "2026-07-07"), ("stg", 22, C24, "2026-07-17"), ("stg", 25, C26, "2026-09-11")],
 "20-80": [("stg", 26, C37, "2026-09-17")],
}
W = {"cfg": w_of_cfg, "stg": w_of_stg}


def net(name, d):
    segs = SEG[name]
    F = 1.0
    for k, (src, row, cols, base) in enumerate(segs):
        if k > 0:
            F *= sp(W[segs[k - 1][0]](segs[k - 1][1]), d_num=base, d_den=segs[k - 1][3], cols=segs[k - 1][2])
        last = (src, row, cols, base)
    w = W[last[0]](last[1])
    v = F * sp(w, d, last[3], last[2])
    days = (datetime.date.fromisoformat(d) - datetime.date.fromisoformat(START[name])).days
    return v * (1 - FEE[name]) ** (days / 365.0)


P = ["10-90基石", "10-90", "20-80", "30-70", "产业趋势基石", "产业趋势", "产业趋势2号"]
DISP = {"10-90基石": "10/90基石", "10-90": "10/90", "20-80": "20/80", "30-70": "30/70",
        "产业趋势基石": "产业趋势基石", "产业趋势": "产业趋势", "产业趋势2号": "产业趋势2号"}
UPLINE = {"10-90基石": "2026/6/18", "10-90": "2026/6/24", "20-80": "2026/9/17", "30-70": "2026/6/24",
          "产业趋势基石": "2026/6/18", "产业趋势": "2026/6/22", "产业趋势2号": "2026/6/24"}
FEE_D = {"10-90基石": "0.5%", "10-90": "0.8%", "20-80": "0.8%", "30-70": "1.2%",
         "产业趋势基石": "1.2%", "产业趋势": "1.5%", "产业趋势2号": "1.5%"}

overview = {}
for k in P:
    n8, nprev = net(k, LATEST), net(k, PREV)
    overview[k] = dict(day=n8 / nprev - 1, week=n8 / net(k, WEEK) - 1, cum=n8 - 1)

# ---------------- 持仓明细 ----------------
HOLD = {
 "1090a": ("10/90基石", "2026-06-22", [
    ("007044.OF", "博道沪深300指数增强A", 0.0125), ("015453.OF", "中欧中证500指数增强A", 0.0125),
    ("014201.OF", "天弘中证1000指数增强A", 0.0125), ("019923.OF", "华泰柏瑞中证2000指数增强A", 0.0125),
    ("001170.OF", "宏利复兴伟业混合A", 0.01), ("013840.OF", "银华集成电路混合A", 0.01),
    ("016370.OF", "信澳业绩驱动混合A", 0.01), ("017488.OF", "嘉实信息产业股票发起式A", 0.01),
    ("162214.OF", "宏利领先中小盘混合", 0.01), ("008015.OF", "嘉实中债3-5年国开行债券指数A", 0.15),
    ("003376.OF", "广发中债7-10年期国开行债券指数A", 0.15), ("161119.OF", "易方达中债新综合债券指数发起式(LOF)A", 0.5),
    ("000216.OF", "华安易富黄金ETF联接A", 0.05), ("000917.OF", "嘉实快线货币A", 0.05)]),
 "1090b": ("10/90", "2026-06-25", [
    ("007045.OF", "博道沪深300指数增强C", 0.0125), ("015454.OF", "中欧中证500指数增强C", 0.0125),
    ("014202.OF", "天弘中证1000指数增强C", 0.0125), ("019924.OF", "华泰柏瑞中证2000指数增强C", 0.0125),
    ("017612.OF", "宏利复兴伟业混合C", 0.0125), ("017489.OF", "嘉实信息产业股票发起式C", 0.0125),
    ("009993.OF", "嘉实前沿创新混合", 0.01), ("013841.OF", "银华集成电路混合C", 0.0075),
    ("162214.OF", "宏利领先中小盘混合", 0.0075), ("008015.OF", "嘉实中债3-5年国开行债券指数A", 0.15),
    ("003376.OF", "广发中债7-10年期国开行债券指数A", 0.15), ("161119.OF", "易方达中债新综合债券指数发起式(LOF)A", 0.5),
    ("000216.OF", "华安易富黄金ETF联接A", 0.05), ("000917.OF", "嘉实快线货币A", 0.05)]),
 "2080": ("20/80", "2026-09-18", [
    ("007045.OF", "博道沪深300指数增强C", 0.025), ("008779.OF", "嘉实中证500指数增强C", 0.0125),
    ("006594.OF", "博道中证500指数增强C", 0.0125), ("017954.OF", "汇添富中证1000指数增强C", 0.0125),
    ("014202.OF", "天弘中证1000指数增强C", 0.0125), ("019924.OF", "华泰柏瑞中证2000指数增强C", 0.0125),
    ("019919.OF", "招商中证2000指数增强C", 0.0125), ("070019.OF", "嘉实价值优势混合A", 0.005),
    ("000884.OF", "民生加银优选股票", 0.005), ("090013.OF", "大成竞争优势混合A", 0.005),
    ("121010.OF", "国投瑞银瑞源混合A", 0.005), ("007466.OF", "华泰柏瑞中证红利低波动ETF联接A", 0.06),
    ("008114.OF", "天弘中证红利低波动100ETF联接A", 0.02), ("008015.OF", "嘉实中债3-5年国开行债券指数A", 0.2),
    ("003376.OF", "广发中债7-10年期国开行债券指数A", 0.2), ("161119.OF", "易方达中债新综合债券指数发起式(LOF)A", 0.3),
    ("016581.OF", "嘉实上海金ETF发起式联接A", 0.05), ("000917.OF", "嘉实快线货币A", 0.05)]),
 "3070": ("30/70", "2026-06-25", [
    ("007045.OF", "博道沪深300指数增强C", 0.0375), ("015454.OF", "中欧中证500指数增强C", 0.0375),
    ("014202.OF", "天弘中证1000指数增强C", 0.0375), ("019924.OF", "华泰柏瑞中证2000指数增强C", 0.0375),
    ("017612.OF", "宏利复兴伟业混合C", 0.035), ("017489.OF", "嘉实信息产业股票发起式C", 0.035),
    ("009993.OF", "嘉实前沿创新混合", 0.03), ("013841.OF", "银华集成电路混合C", 0.025),
    ("162214.OF", "宏利领先中小盘混合", 0.025), ("008015.OF", "嘉实中债3-5年国开行债券指数A", 0.1),
    ("003376.OF", "广发中债7-10年期国开行债券指数A", 0.1), ("161119.OF", "易方达中债新综合债券指数发起式(LOF)A", 0.3),
    ("000216.OF", "华安易富黄金ETF联接A", 0.1), ("000917.OF", "嘉实快线货币A", 0.1)]),
 "trenda": ("产业趋势基石/产业趋势", "2026-06-22", [
    ("001170.OF", "宏利复兴混合A", 0.166095), ("017488.OF", "嘉实信息产业A", 0.173431),
    ("016370.OF", "信澳业绩驱动A", 0.163849), ("013840.OF", "银华集成电路混合A", 0.245429),
    ("162214.OF", "宏利领先中小盘", 0.07), ("019632.OF", "国泰半导体设备ETF联接A", 0.135904),
    ("000917.OF", "嘉实快线货币A", 0.045292)]),
 "trendb": ("产业趋势2号", "2026-06-25", [
    ("017612.OF", "宏利复兴混合C", 0.164034), ("017489.OF", "嘉实信息产业C", 0.168764),
    ("009993.OF", "嘉实前沿创新", 0.189913), ("013841.OF", "银华集成电路混合C", 0.234328),
    ("162214.OF", "宏利领先中小盘", 0.07), ("019633.OF", "国泰半导体设备ETF联接C", 0.129189),
    ("000917.OF", "嘉实快线货币A", 0.043772)]),
}


def hold_rows(key):
    _, base, lst = HOLD[key]
    out = []
    for code, name, ratio in lst:
        r = dict(code=code, name=name,
                 day=NAV[LATEST][code] / NAV[PREV][code] - 1,
                 week=NAV[LATEST][code] / NAV[WEEK][code] - 1,
                 since=NAV[LATEST][code] / NAV[base][code] - 1,
                 ratio=ratio)
        out.append(r)
    return out

# ================= 渲染 =================
FM = "/System/Library/Fonts/STHeiti Medium.ttc"
FL = "/System/Library/Fonts/STHeiti Light.ttc"
FT = lambda s: ImageFont.truetype(FM, s)
FR = lambda s: ImageFont.truetype(FL, s)
f_title, f_sub = FT(27), FR(14)
f_sec = FT(18)
f_hd, f_tx = FT(15), FR(15)
f_code = FR(14)
f_foot = FR(12)
f_wm = FT(30)

BG, HEAD_BG, LINE = "#FFFFFF", "#F1EFE8", "#D9D7CF"
TXT, SUB = "#2C2C2A", "#6E6D66"
UP, DOWN, FLAT = "#C0392B", "#1E8449", "#3A3936"
PAD, WIDTH = 46, 940


def color_of(v):
    if v > 5e-7:
        return UP
    if v < -5e-7:
        return DOWN
    return FLAT


def pct(v, nd=2):
    return f"{v*100:.{nd}f}%"


def draw_table(d, x0, y0, cols, rows, rowh=32, hh=36):
    total = sum(c[1] for c in cols)
    d.rectangle([x0, y0, x0 + total, y0 + hh], fill=HEAD_BG)
    cx = x0
    for (t, w, al) in cols:
        ax = cx + w / 2 if al == "c" else (cx + 10 if al == "l" else cx + w - 12)
        d.text((ax, y0 + hh / 2), t, font=f_hd, fill=TXT,
               anchor="mm" if al == "c" else ("lm" if al == "l" else "rm"))
        cx += w
    y = y0 + hh
    for r in rows:
        if isinstance(r, tuple) and r[0] == "GROUP":
            d.rectangle([x0, y, x0 + total, y + rowh], fill="#F7F6F1")
            d.text((x0 + 12, y + rowh / 2), r[1], font=FT(14), fill=SUB, anchor="lm")
            y += rowh
            continue
        cx = x0
        for i, (t, w, al) in enumerate(cols):
            col, val = None, r[i]
            if isinstance(val, tuple):
                val, col = val
            f = f_code if w < 130 else f_tx
            ax = cx + w / 2 if al == "c" else (cx + 10 if al == "l" else cx + w - 12)
            d.text((ax, y + rowh / 2), str(val), font=f, fill=col or TXT,
                   anchor="mm" if al == "c" else ("lm" if al == "l" else "rm"))
            cx += w
        y += rowh
    cx = x0
    d.line([x0, y0, x0 + total, y0], fill=LINE)
    for (t, w, al) in cols:
        d.line([cx, y0, cx, y], fill=LINE)
        cx += w
    d.line([cx, y0, cx, y], fill=LINE)
    for yy in [y0 + hh] + [y0 + hh + rowh * (i + 1) for i in range(len(rows))]:
        d.line([x0, yy, x0 + total, yy], fill=LINE)
    return y


COLS_OV = [("组合名称", 190, "l"), ("日涨跌", 128, "r"), ("本周以来", 128, "r"),
           ("上线以来", 128, "r"), ("上线日期", 140, "c"), ("年费率", 110, "c")]
COLS_HD = [("基金代码", 112, "l"), ("基金名称", 296, "l"), ("今日涨跌", 104, "r"),
           ("本周以来", 104, "r"), ("上线以来", 104, "r"), ("比例", 92, "r")]


def wm(img, text):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    tmp = Image.new("RGBA", (760, 64), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((10, 32), text, font=f_wm, fill=(118, 116, 108, 44), anchor="lm")
    tmp = tmp.rotate(22, expand=True, resample=Image.BICUBIC)
    W, H = img.size
    for y in range(-80, H + 140, 200):
        for x in range(-160, W + 240, 860):
            layer.alpha_composite(tmp, (x, y))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def build(fname, title, ov_rows, blocks):
    im = Image.new("RGB", (WIDTH, 3000), BG)
    d = ImageDraw.Draw(im)
    y = PAD
    d.text((PAD, y), title, font=f_title, fill=TXT, anchor="lm")
    d.text((WIDTH - PAD, y), f"更新日期：{LATEST}", font=f_sub, fill=SUB, anchor="rm")
    y += 42
    d.text((PAD, y), "注：收益率数据根据相关组合的持仓、费率估算，仅供内部参考，请勿外发",
           font=f_sub, fill=SUB, anchor="lm")
    y += 44
    d.text((PAD, y), "一、组合总览", font=f_sec, fill=TXT, anchor="lm")
    y += 30
    y = draw_table(d, PAD, y, COLS_OV, ov_rows, rowh=34) + 36
    if blocks:
        d.text((PAD, y), "二、持仓基金表现", font=f_sec, fill=TXT, anchor="lm")
        y += 30
        for label, key in blocks:
            d.text((PAD, y), label, font=FT(15), fill=SUB, anchor="lm")
            y += 26
            cols = [COLS_HD[0], (label, 296, "l")] + COLS_HD[2:]
            rows = []
            for r in hold_rows(key):
                rows.append([r["code"], r["name"], (pct(r["day"]), color_of(r["day"])),
                             (pct(r["week"]), color_of(r["week"])),
                             (pct(r["since"]), color_of(r["since"])), pct(r["ratio"])])
            y = draw_table(d, PAD, y, cols, rows) + 30
    d.text((PAD, y + 4), "数据来源：同花顺 iFinD（复权单位净值）· 估值基准净值日 2026-10-08 · 上一交易日 2026-09-30（国庆假期 10/1-10/7 休市）",
           font=f_foot, fill="#9A998F", anchor="lm")
    y += 36
    im = im.crop((0, 0, WIDTH, y + PAD))
    im = wm(im, f"{WATERMARK}      {LATEST}")
    import os
    os.makedirs(OUT, exist_ok=True)
    im.save(f"{OUT}/{fname}")
    return f"{OUT}/{fname}"


def ovrow(k):
    o = overview[k]
    return [DISP[k], (pct(o["day"]), color_of(o["day"])), (pct(o["week"]), color_of(o["week"])),
            (pct(o["cum"]), color_of(o["cum"])), UPLINE[k], FEE_D[k]]


files = [
    build("1_每日组合.png", "样板间投顾组合业绩预估",
          [("GROUP", "10/90策略"), ovrow("10-90基石"), ovrow("10-90"),
           ("GROUP", "20/80策略"), ovrow("20-80"),
           ("GROUP", "30/70策略"), ovrow("30-70"),
           ("GROUP", "产业趋势策略"), ovrow("产业趋势基石"), ovrow("产业趋势"), ovrow("产业趋势2号")], []),
    build("2_每日1090.png", "10/90投顾组合业绩预估",
          [ovrow("10-90基石"), ovrow("10-90")],
          [("10/90基石", "1090a"), ("10/90", "1090b")]),
    build("3_每日2080.png", "20/80投顾组合业绩预估", [ovrow("20-80")], [("20/80", "2080")]),
    build("4_每日3070.png", "30/70投顾组合业绩预估", [ovrow("30-70")], [("30/70", "3070")]),
    build("5_每日产业趋势.png", "产业趋势投顾组合业绩预估",
          [ovrow("产业趋势基石"), ovrow("产业趋势"), ovrow("产业趋势2号")],
          [("产业趋势基石/产业趋势", "trenda"), ("产业趋势2号", "trendb")]),
]
for f in files:
    print("生成:", f)
