# -*- coding: utf-8 -*-
"""
产业趋势基金观察池 · 周报长图生成器（样式已定稿：深蓝）
=========================================================
用法：
    python3 生成观察池海报.py                          # 用 CONFIG 里的输入/输出
    python3 生成观察池海报.py 新的基金池.xlsx            # 换输入，输出名按区间自动生成
    python3 生成观察池海报.py 新的基金池.xlsx 输出名.png

依赖：openpyxl、Pillow、本机 Google Chrome（无头渲染）。
工作表约定：sheet 名「产业趋势池」，第 3 行表头，第 4 行起每个非空代码一行。
    D=代码  E=名称  F=基金经理/贝塔  G=季报方向(重仓方向)  H..Y=各区间收益  Z=任职日期
"""
import sys, os, json, subprocess, datetime, statistics, tempfile
import openpyxl
from PIL import Image

# ────────────────────────── 配置 ──────────────────────────
ROOT = "/Users/yangguang/Documents/Workbuddy/样板间投顾组合净值预估"
SRC = os.path.join(ROOT, "..", "..", "..", "Library/Containers/com.tencent.xinWeChat/Data/Documents/"
                   "xwechat_files/wxid_tutknq7waqea12_5d21/temp/RWTemp/2026-11/"
                   "fad6f8dca7fb9ac82fc39d4d641086f1/产业趋势基金池.xlsx")
SHEET = "产业趋势池"

# 列定义：key -> (Excel列, 起始日, 截止日, 表头名, 副标题(留空则按日期自动生成))
COLS = [
    ("wk",   "H", "2026-11-16", "2026-11-20", "上周",      ""),
    ("mtd",  "I", "2026-11-01", "2026-11-20", "本月以来",  ""),
    ("ytd",  "J", "2026-01-01", "2026-11-20", "2026YTD",   ""),
    ("rally","K", "2026-04-01", "2026-06-30", "4-6月冲顶", ""),
    ("jul",  "L", "2026-06-30", "2026-07-30", "7月大跌",   ""),
    ("s922", "M", "2026-09-22", "2026-11-20", "9.22至今",  ""),
    ("y2025","S", "2025-01-01", "2025-12-31", "2025年",    "全年"),
    ("y2024","T", "2024-01-01", "2024-12-31", "2024年",    "全年"),
    ("y2023","U", "2023-01-01", "2023-12-31", "2023年",    "全年"),
]
YTD_LABEL = "2026YTD"
TITLE = "产业趋势基金观察池"
SUBTITLE = "科技 · 医药 · 制造 ｜ 复权净值 ｜ <b>红字为持仓基金</b> ｜ 灰底 β 行为对照指数"

# 持仓基金（按 6 位代码）。不在此表内的一律不标红。
HOLD = {"009993", "017745", "162214", "013841", "016371", "017489", "017612"}

# 池子结构：组 -> [(细分赛道, [基金代码], [指数代码后置])]，组内先基金后指数
STRUCT = [
    ("科技组", "AI 算力 / 应用", [
        ("全球科技 β（海外映射）", [], ["932381.CSI", "SOX.GI", "KS11.GI", "NDX.GI"]),
        ("AI硬件-国产算力", ["009993", "014497", "017745", "017470", "019633", "019427",
                            "014193", "162214", "166109", "007343", "013841", "019438"],
         ["950162.SH", "932580.CSI", "931743.CSI"]),
        ("AI应用", ["001628", "004260", "012182", "018048", "012620", "017735"],
         ["980107.SZ", "987036.SZ", "930967.CSI"]),
        ("AI硬件-海外算力", ["016371", "013722", "017489", "011369", "007818", "017612",
                            "011126", "019018", "023452"],
         ["932666.CSI", "931160.CSI", "970083.SZ"]),
    ]),
    ("医药组", "创新药 / CXO", [
        ("CXO + 创新药", ["005303", "008923", "006228", "110023", "000960", "005805",
                          "000711", "015121", "015916", "020232", "019916"],
         ["931409.CSI", "931750.CSI"]),
    ]),
    ("制造组", "机器人 + 商业航天", [
        ("机器人", ["018125", "019458", "004233", "018241"], ["H30590.CSI"]),
        ("商业航天", ["015790", "025491", "002067", "013566"], ["CN5082.SZ"]),
    ]),
]

# 指数行的「贝塔」说明
IND_BETA = {
    "932381.CSI": "宽基β", "SOX.GI": "海外算力β", "KS11.GI": "存储/半导体β", "NDX.GI": "美股科技β",
    "950162.SH": "国产算力β", "932580.CSI": "国产存储β", "931743.CSI": "设备材料β",
    "980107.SZ": "AI应用β", "987036.SZ": "港股AI应用β", "930967.CSI": "港股AI硬件β",
    "932666.CSI": "PCBβ", "931160.CSI": "光模块/通信β", "970083.SZ": "算力宽基β",
    "931409.CSI": "创新药β", "931750.CSI": "CXOβ", "H30590.CSI": "机器人β",
    "CN5082.SZ": "商业航天β",
}

# ────────────────────────── 取数 ──────────────────────────
def load(src):
    wb = openpyxl.load_workbook(src, data_only=True)
    ws = wb[SHEET]
    rows = {}
    for r in range(4, ws.max_row + 1):
        code = (ws[f"D{r}"].value or "").strip()
        if not code:
            continue
        code = code[:-3] if code.upper().endswith(".OF") else code
        tag = (ws[f"G{r}"].value or "").strip().replace("--", "-") or None
        rec = {"code": code, "name": (ws[f"E{r}"].value or "").strip(),
               "tag": tag, "pmg": (ws[f"F{r}"].value or "").strip() or None,
               "tenure": ws[f"Z{r}"].value}
        for k, col, *_ in COLS:
            v = ws[f"{col}{r}"].value
            rec[k] = float(v) if isinstance(v, (int, float)) else None
        rows[code] = rec
    return rows

def covered(tenure, start):
    if not tenure:
        return True
    try:
        d = datetime.date.fromisoformat(str(tenure)[:10])
    except Exception:
        return True
    return d <= datetime.date.fromisoformat(start)

def build(rows):
    def rec(code, is_index):
        d = rows[code]
        out = {"code": code, "name": d["name"], "tag": d["tag"], "pmg": d["pmg"],
               "hold": code in HOLD, "index": is_index,
               "beta": IND_BETA.get(code) if is_index else None, "v": {}}
        for k, _, s, e, _, _ in COLS:
            v = d.get(k)
            if v is None or (not is_index and not covered(d["tenure"], s)):
                continue
            out["v"][k] = round(v, 2)
        return out

    groups, allf, holdf = [], [], []
    for gname, gdesc, subs in STRUCT:
        g = {"name": gname, "desc": gdesc, "subs": [], "funds": []}
        for sname, funds, idxs in subs:
            key = lambda x: (x["v"].get("wk") is None, -(x["v"].get("wk") or -999))
            fr = sorted([rec(c, False) for c in funds], key=key)
            ir = sorted([rec(c, True) for c in idxs], key=key)
            g["subs"].append({"name": sname, "funds": fr, "idx": ir})
            g["funds"] += fr
            allf += fr
            holdf += [x for x in fr if x["hold"]]
        groups.append(g)

    def eqw(items, k):
        vals = [i["v"][k] for i in items if k in i["v"]]
        return (sum(vals) / len(vals) if vals else None), len(vals)

    keys = [k for k, *_ in COLS]
    stats = {}
    for name, items in [("all", allf), ("hold", holdf)] + [(g["name"], g["funds"]) for g in groups]:
        stats[name] = {k: eqw(items, k) for k in keys}
    return groups, stats, {
        "n_all": len(allf), "n_hold": len(holdf),
        "n_up": sum(1 for f in allf if (f["v"].get("wk") or 0) > 0),
        "grp_n": {g["name"]: len(g["funds"]) for g in groups},
    }

# ────────────────────────── 渲染 ──────────────────────────
def sub_label(s, e):
    if s[5:7] == "01" and e[5:7] == "12":
        return "全年"
    return f"{s[5:7]}.{s[8:10]}–{e[5:7]}.{e[8:10]}"

def tagcls(t):
    if not t:
        return "x"
    if t.startswith("AI硬件-国产"):
        return "k1"
    if t.startswith("AI应用"):
        return "k2"
    if "海外" in t:
        return "k3"
    if "CXO" in t or "创新药" in t:
        return "k4"
    if t == "机器人":
        return "k5"
    if t == "商业航天":
        return "k6"
    return "x"

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{background:#DCE4ED;font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
 -webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
.poster{width:1080px;margin:0 auto;background:#FCFDFE;padding-bottom:26px}
.mast{position:relative;padding:32px 34px 22px;color:#fff;overflow:hidden;
 background:linear-gradient(118deg,#08182A 0%,#10304E 42%,#17496F 74%,#1E5B87 100%)}
.mast:after{content:"";position:absolute;right:-50px;bottom:-90px;width:320px;height:320px;border-radius:50%;
 background:radial-gradient(circle,rgba(120,190,235,.26),transparent 64%)}
.kick{font-size:10px;letter-spacing:3.4px;color:rgba(255,255,255,.55);margin-bottom:11px;position:relative;z-index:1}
.kick i{display:inline-block;width:20px;height:2px;background:#5FA8D8;vertical-align:3px;margin-right:8px}
h1{font-size:33px;font-weight:700;letter-spacing:-.2px;line-height:1.1;position:relative;z-index:1}
h1 span{font-size:20px;font-weight:400;color:rgba(255,255,255,.68);margin-left:13px;letter-spacing:.6px}
.sub{margin-top:11px;font-size:11.6px;color:rgba(255,255,255,.78);letter-spacing:.2px;position:relative;z-index:1}
.sub b{color:#8FCDEC;font-weight:600}
.stamp{position:absolute;right:34px;top:30px;text-align:right;font-size:9.4px;letter-spacing:1.8px;
 color:rgba(255,255,255,.55);z-index:1}
.stamp strong{display:block;font-size:19px;letter-spacing:.5px;color:#fff;font-weight:600;margin-top:6px}
.cards{display:flex;gap:9px;padding:18px 34px 6px}
.card{flex:1;background:#fff;border:1px solid #DCE6F0;border-top:2px solid #2E6F9E;padding:11px 12px 10px}
.cl{font-size:10.4px;color:#7D92A6;letter-spacing:.2px}
.cv{font-size:25px;font-weight:700;margin-top:6px;letter-spacing:-.6px;line-height:1;color:#122B42}
.cs{font-size:9.2px;color:#A3B4C4;margin-top:6px;letter-spacing:.1px}
.up{color:#C0272D} .dn{color:#0B7A57} .fl{color:#5A7188}
.note{margin:15px 34px 4px;background:#EEF4FA;border-left:3px solid #1F5C8B;padding:12px 15px 11px}
.note ul{list-style:none}
.note li{font-size:11.6px;color:#33506B;line-height:1.68;padding-left:15px;position:relative;margin-bottom:3px}
.note li:last-child{margin-bottom:0}
.note li:before{content:"";position:absolute;left:0;top:8px;width:6px;height:6px;background:#2E6F9E}
.note b{color:#0E2A44;font-weight:700}
.sec{padding:19px 34px 9px;display:flex;align-items:flex-end;justify-content:space-between}
.sec h2{font-size:16.5px;font-weight:700;color:#0E2A44;letter-spacing:.2px;position:relative;padding-left:12px}
.sec h2:before{content:"";position:absolute;left:0;top:2px;width:4px;height:15px;
 background:linear-gradient(180deg,#163F60,#2E6F9E)}
.sec .lg{font-size:9.4px;color:#8EA2B5;letter-spacing:.2px}
.sec .lg i{font-style:normal;color:#C0272D;font-weight:600}
.sec .lg s{text-decoration:none;display:inline-block;width:8px;height:8px;background:#EFF3F8;border:1px solid #D3DFEA;vertical-align:0;margin:0 3px 0 9px}
table{width:1012px;margin:0 34px 6px;border-collapse:collapse;table-layout:fixed}
thead tr{border-bottom:2px solid #1F5C8B}
th{background:#12304B;color:#fff;font-weight:600;padding:8px 5px 7px;text-align:right;font-size:11.4px}
th:first-child,th:nth-child(2),th:nth-child(3){text-align:left}
th .h1{display:block;font-size:11.4px}
th .h2{display:block;font-size:8.2px;color:rgba(255,255,255,.55);font-weight:400;margin-top:3px;letter-spacing:.1px}
td{font-size:12px;padding:0 5px;height:29px;border-bottom:1px solid #EDF2F7;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
td.nm{text-align:left;font-size:12.3px;color:#182A3C;font-weight:500}
td.tg{text-align:left;padding-left:3px}
td.pm{text-align:left;font-size:10.4px;color:#7D92A6}
.tag{display:inline-block;font-size:9.2px;line-height:15px;padding:0 5px;border-radius:2px;letter-spacing:0}
.k1{background:#E1EDF7;color:#1B5480}
.k2{background:#DFF0F3;color:#15687F}
.k3{background:#E6E9F6;color:#3C5390}
.k4{background:#F7E4EA;color:#96304F}
.k5{background:#FAEBD9;color:#8E5714}
.k6{background:#F5E4DC;color:#8A3C1E}
tr.hold td{background:#FDF2F1}
tr.hold td.nm{box-shadow:inset 3px 0 0 #C0272D}
tr.hold td.nm b{color:#B3272A;font-weight:700}
tr.hold td.nm .cd{color:#C1938F}
tr.idx td{background:#F1F5F9;color:#5E7488}
tr.idx td.nm{color:#4C6377;font-weight:400;font-size:11.9px}
tr.idx .beta{display:inline-block;width:13px;height:13px;line-height:13px;text-align:center;border-radius:50%;
 background:#DEE7F0;color:#3E5C77;font-size:9px;margin-right:5px;vertical-align:1px}
.cd{font-size:8.8px;color:#A3B4C4;margin-left:4px;letter-spacing:.1px}
tr.grp td{height:35px;border-bottom:1px solid #DCE7F1;
 background:linear-gradient(90deg,#DFEAF5 0%,#F6FAFD 65%,#FCFDFE 100%)}
tr.grp td:first-child{box-shadow:inset 4px 0 0 #1F5C8B}
tr.grp td.gn{text-align:left;font-size:15px;font-weight:700;color:#0E2A44}
tr.grp td.gn em{font-style:normal;font-size:10px;color:#1F5C8B;letter-spacing:1.4px;margin-right:8px;vertical-align:2px;font-weight:700}
tr.grp td.gn .gd{font-weight:400;font-size:10.4px;color:#7D92A6;margin-left:9px;letter-spacing:.2px}
tr.grp td.gmeta{font-size:9.6px;color:#7D92A6;letter-spacing:.2px;text-align:right;padding-right:4px}
tr.grp td.gval{font-size:12.2px;font-weight:700}
tr.sub td{background:#F7FAFD;border-bottom:1px solid #E6EEF6;height:24px;text-align:left;font-size:10.7px;
 color:#2C4B67;letter-spacing:.4px;padding-left:6px}
tr.sub i{display:inline-block;width:4px;height:4px;background:#2E6F9E;margin:0 7px 0 2px;vertical-align:2px}
tr.sub em{font-style:normal;color:#A3B4C4;font-size:9.2px;margin-left:8px}
.na{color:#C9D6E2}
.ft{margin:14px 34px 0;padding:14px 0 24px;border-top:1px solid #DCE7F1}
.ft p{font-size:10px;color:#7D92A6;line-height:1.78;letter-spacing:.1px}
.ft p b{color:#4C6377;font-weight:600}
"""

def render(groups, stats, meta, out_base, span_txt, asof):
    def f(v):
        if v is None:
            return '<span class="na">—</span>'
        c = "up" if v > 0 else ("dn" if v < 0 else "fl")
        return f'<span class="{c}">{v:+.2f}%</span>'
    def eq(k):  return f'{stats["all"][k][0]:+.2f}%'
    def eqh(k): return f'{stats["hold"][k][0]:+.2f}%'

    heads = "".join(
        f'<th><span class="h1">{lab}</span>'
        f'<span class="h2">{sub or sub_label(s, e)}</span></th>'
        for _, col, s, e, lab, sub in COLS)

    rows = []
    for gi, g in enumerate(groups, 1):
        gv = stats[g["name"]]["wk"][0]
        rows.append(
            f'<tr class="grp"><td class="gn"><em>{gi:02d}</em>{g["name"]}'
            f'<span class="gd">{g["desc"]}</span></td><td class="gmeta"></td><td></td>'
            f'<td class="n gval {"up" if gv > 0 else "dn"}">{gv:+.2f}%</td>'
            f'<td colspan="8"></td></tr>')
        for sb in g["subs"]:
            nf, ni = len(sb["funds"]), len(sb["idx"])
            meta_txt = f"{nf}只基金" if nf else f"{ni}条指数"
            rows.append(f'<tr class="sub"><td colspan="12"><i></i>{sb["name"]}'
                        f'<em>{meta_txt}</em></td></tr>')
            for it in sb["funds"]:
                cls = "hold" if it["hold"] else ""
                nm = f'<b>{it["name"]}</b>' if it["hold"] else it["name"]
                tag = f'<span class="tag {tagcls(it["tag"])}">{it["tag"]}</span>' if it["tag"] else ""
                cells = "".join(
                    f'<td class="n">{f(it["v"].get(k))}</td>' for k, *_ in COLS)
                rows.append(f'<tr class="{cls}"><td class="nm">{nm}'
                            f'<span class="cd">{it["code"]}</span></td>'
                            f'<td class="tg">{tag}</td><td class="pm">{it["pmg"] or "—"}</td>{cells}</tr>')
            for it in sb["idx"]:
                cells = "".join(
                    f'<td class="n">{f(it["v"].get(k))}</td>' for k, *_ in COLS)
                rows.append(f'<tr class="idx"><td class="nm"><span class="beta">β</span>{it["name"]}'
                            f'<span class="cd">{it["code"]}</span></td>'
                            f'<td class="tg"></td><td class="pm">{it["beta"]}</td>{cells}</tr>')

    def cc(v):
        return "up" if (v is not None and v > 0) else ("dn" if (v is not None and v < 0) else "fl")

    cards = [("本周基金池等权", f'{stats["all"]["wk"][0]:+.2f}%', f'{meta["n_all"]}只基金简单平均', stats["all"]["wk"][0]),
             ("上涨基金占比", f'{meta["n_up"]/meta["n_all"]*100:.1f}%', f'{meta["n_up"]} / {meta["n_all"]} 只上涨', None),
             ("持仓基金等权", f'{stats["hold"]["wk"][0]:+.2f}%', f'{meta["n_hold"]}只（红字标出）', stats["hold"]["wk"][0])]
    for g in groups:
        cards.append((f"{g['name']}等权", f'{stats[g["name"]]["wk"][0]:+.2f}%', f'{meta["grp_n"][g["name"]]}只', stats[g["name"]]["wk"][0]))
    cardhtml = "".join(
        f'<div class="card"><div class="cl">{t}</div><div class="cv {cc(v)}">{val}</div>'
        f'<div class="cs">{sub}</div></div>' for t, val, sub, v in cards)

    med = statistics.median([x["v"]["wk"] for g in groups for s in g["subs"] for x in s["funds"]])
    win_txt = "、".join(
        f"{lab.replace('年', '')} 全年" if sub == "全年"
        else f"{lab} {s[5:7]}/{s[8:10]}–{e[5:7]}/{e[8:10]}"
        for _, _, s, e, lab, sub in COLS)
    d_hold = stats["hold"]["wk"][0] - stats["all"]["wk"][0]
    d_ytd = stats["hold"]["ytd"][0] - stats["all"]["ytd"][0]
    notes = (f'<li><b>全池无一只上涨。</b>{meta["n_all"]}只基金上周全部收跌，等权 {eq("wk")}，'
             f'中位数 {med:+.2f}%；制造组（机器人＋商业航天）跌幅最深 {stats["制造组"]["wk"][0]:+.2f}%，'
             f'科技组 {stats["科技组"]["wk"][0]:+.2f}%，医药组相对抗跌 {stats["医药组"]["wk"][0]:+.2f}%。</li>'
             f'<li><b>持仓组合占优。</b>{meta["n_hold"]}只持仓等权 {eqh("wk")}，跑赢全池 {d_hold:+.1f}pp；'
             f'{YTD_LABEL} 持仓 {eqh("ytd")} vs 全池 {eq("ytd")}，超额 {d_ytd:+.1f}pp，'
             f'主要来自 4–6 月冲顶段（持仓 {eqh("rally")} vs 全池 {eq("rally")}）。</li>')

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><style>{CSS}</style></head>
<body><div class="poster">
<div class="mast">
  <div class="kick"><i></i>WEEKLY · 产业趋势观察池</div>
  <h1>{TITLE}<span>{span_txt}</span></h1>
  <div class="sub">{SUBTITLE}</div>
  <div class="stamp">数据截止<strong>{asof}</strong></div>
</div>
<div class="cards">{cardhtml}</div>
<div class="note"><ul>{notes}</ul></div>
<div class="sec"><h2>产品明细 ｜ 组内按上周收益降序</h2>
  <div class="lg"><i>红字</i>=持仓基金<s></s>灰底 β = 细分赛道指数</div></div>
<table>
<thead><tr><th style="width:216px">基金 / 指数</th><th style="width:88px">季报方向</th>
<th style="width:80px">经理 / 贝塔</th>{heads}</tr></thead>
<tbody>{"".join(rows)}</tbody></table>
</div></body></html>"""

    html_path = out_base + ".html"
    open(html_path, "w").write(html)

    png_raw = out_base + "_raw.png"
    prof = tempfile.mkdtemp()
    subprocess.run(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                    f"--user-data-dir={prof}", "--force-device-scale-factor=2",
                    "--window-size=1080,7600", f"--screenshot={png_raw}",
                    "file://" + html_path], capture_output=True)
    im = Image.open(png_raw)
    w, h = im.size
    px = im.convert("RGB").load()
    bg = px[5, h - 5]
    last = 0
    for y in range(h - 1, -1, -1):
        if px[w // 2, y] != bg:
            last = y
            break
    im.crop((0, 0, w, last + 1)).save(out_base + ".png")
    os.remove(png_raw)
    return out_base + ".png"

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else SRC
    rows = load(src)
    groups, stats, meta = build(rows)
    s, e = COLS[0][2], COLS[0][3]
    span = f"{s[2:4]}{s[5:7]}{s[8:10]} – {e[2:4]}{e[5:7]}{e[8:10]}"
    asof = f"{e[0:4]}.{e[5:7]}.{e[8:10]}"
    name = sys.argv[2] if len(sys.argv) > 2 else f"产业趋势基金观察池_{s[2:4]}{s[5:7]}{s[8:10]}-{e[2:4]}{e[5:7]}{e[8:10]}.png"
    out = os.path.join(ROOT, os.path.splitext(name)[0])
    p = render(groups, stats, meta, out, span, asof)
    print("saved:", p)
    print("funds=%d hold=%d up=%d" % (meta["n_all"], meta["n_hold"], meta["n_up"]))
    print({k: round(v[0], 2) for k, v in stats["hold"].items()})

if __name__ == "__main__":
    main()
