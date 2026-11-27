# -*- coding: utf-8 -*-
"""
周更流水线：把「实时取到的原始行情文件」折算成各区间业绩，再调用定稿版式出图。
=====================================================================
本脚本不自己联网，只负责解析 + 计算 + 渲染。取数由上层（Agent/MCP）完成，落到 --raw 目录：

  raw/fund_*.json   盈米 BatchGetFundNavHistory 的原始返回（可多份，自动合并）
                    结构：[{ "fundCode":"009993", "data":{ "data":[ {"navDate":"2025年11月25日",
                            "nav":1.2591, "dailyReturn":"2.49%"}, ... ] } }]
  raw/idx_<代码>.json  Wind get_index_kline 的原始返回，文件名里带代码，例如 idx_931160.CSI.json
                    结构：{ "data": { "rows": [ ["2026-11-20T00:00:00.000+08:00", 开, 收, 高, 低, ...], ... ] } }

用法：
  python3 周更.py --asof 2026-11-27 --raw ./raw --xlsx ../产业趋势基金池.xlsx
  python3 周更.py --asof 2026-11-27 --raw ./raw --allow-partial    # 覆盖率不足也照样出图（自测用）

约定：
  · 区间收益期初取起始日「前一交易日」，区间含首日；基金用日涨跌幅累乘（已含分红再投），指数用收盘点位比。
  · 取不到实时数据的标的，回落到工作簿缓存值，并在 stdout 的 WARN 里列出。
  · 基金实时覆盖 < 80% 时以 exit 1 退出，避免把旧数据当新数据发出去。
"""
import argparse, datetime as dt, glob, json, os, re, sys
import openpyxl
import importlib.util, pathlib

HERE = pathlib.Path(__file__).parent
_spec = importlib.util.spec_from_file_location("poster", HERE / "生成观察池海报.py")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

EVENT_922 = (9, 22)          # 「9.22至今」的事件起点，可按需改


# ───────────────────── 区间定义 ─────────────────────
def windows(asof: dt.date):
    mon_this = asof - dt.timedelta(days=asof.weekday())
    fri = mon_this - dt.timedelta(days=3)          # 上一个完整周的周五
    mon = fri - dt.timedelta(days=4)
    y = asof.year
    ev = dt.date(y, *EVENT_922)
    if ev > fri:                      # 年初运行时，事件起点算上一年
        ev = dt.date(y - 1, *EVENT_922)
    W = {
        "wk":    (mon, fri, "上周", ""),
        "mtd":   (dt.date(y, asof.month, 1), fri, "本月以来", ""),
        "ytd":   (dt.date(y, 1, 1), fri, f"{y}YTD", ""),
        "rally": (dt.date(y, 4, 1), dt.date(y, 6, 30), "4-6月冲顶", ""),
        "jul":   (dt.date(y, 6, 30), dt.date(y, 7, 30), "7月大跌", ""),
        "s922":  (ev, fri, f"{EVENT_922[0]}.{EVENT_922[1]}至今", ""),
    }
    for i in range(1, 4):
        yy = y - i
        W[f"y{i}"] = (dt.date(yy, 1, 1), dt.date(yy, 12, 31), f"{yy}年", "全年")
    return W


EXCEL_COLS = {"wk": "H", "mtd": "I", "ytd": "J", "rally": "K", "jul": "L",
              "s922": "M", "y1": "S", "y2": "T", "y3": "U"}


def load_rows(xlsx):
    """只读元信息 + 9 个业绩列缓存值；列位置固定，与年份无关"""
    ws = openpyxl.load_workbook(xlsx, data_only=True)[base.SHEET]
    rows = {}
    for r in range(4, ws.max_row + 1):
        code = (ws[f"D{r}"].value or "").strip()
        if not code:
            continue
        code = code[:-3] if code.upper().endswith(".OF") else code
        rec = {"code": code, "name": (ws[f"E{r}"].value or "").strip(),
               "tag": (ws[f"G{r}"].value or "").strip().replace("--", "-") or None,
               "pmg": (ws[f"F{r}"].value or "").strip() or None,
               "tenure": ws[f"Z{r}"].value}
        for k, c in EXCEL_COLS.items():
            v = ws[f"{c}{r}"].value
            rec[k] = float(v) if isinstance(v, (int, float)) else None
        rows[code] = rec
    return rows


def as_cols(W):
    """转成 生成观察池海报.py 的 COLS 结构：(key, 占位列名, 起, 止, 表头, 副标题)"""
    return [(k, "", s.isoformat(), e.isoformat(), lab, sub) for k, (s, e, lab, sub) in W.items()]


# ───────────────────── 解析原始文件 ─────────────────────
def _load_json(path):
    txt = open(path, encoding="utf-8", errors="ignore").read().strip()
    try:
        return json.loads(txt)
    except Exception:
        pass
    i = min([p for p in (txt.find("["), txt.find("{")) if p >= 0], default=-1)
    if i < 0:
        return None
    return json.loads(txt[i:])


def _d(s):
    m = re.match(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", str(s))
    return dt.date(*map(int, m.groups())) if m else None


def parse_funds(raw_dir):
    """返回 {代码: {日期: 累计净值指数}}，按日涨跌幅累乘（分红再投口径）"""
    out = {}
    for f in sorted(glob.glob(os.path.join(raw_dir, "fund_*.json"))):
        data = _load_json(f)
        if not data:
            continue
        for item in (data if isinstance(data, list) else [data]):
            code = str(item.get("fundCode") or "").strip()
            rows = (((item.get("data") or {}).get("data")) or [])
            if not code or not rows:
                continue
            ser = {}
            for r in rows:
                d, ret = _d(r.get("navDate")), r.get("dailyReturn")
                if not d or ret is None:
                    continue
                try:
                    pct = float(str(ret).replace("%", ""))
                except Exception:
                    continue
                ser[d] = pct
            if not ser:
                continue
            cum, acc = {}, 1.0
            for d in sorted(ser):
                acc *= 1 + ser[d] / 100.0
                cum[d] = acc
            out[code] = cum
    return out


def parse_idx(raw_dir):
    out = {}
    for f in glob.glob(os.path.join(raw_dir, "idx_*.json")):
        code = os.path.basename(f)[4:-5]
        data = _load_json(f) or {}
        rows = (((data.get("data") or {}).get("rows")) or [])
        ser = {}
        for r in rows:
            d = _d(r[0])
            if not d:
                continue
            try:
                ser[d] = float(r[2])
            except Exception:
                continue
        if ser:
            out[code] = ser
    return out


def ret(ser, a, b):
    """期初取 a 之前最近一个交易日，期末取 b 之前最近一个交易日"""
    if not ser:
        return None
    ds = sorted(ser)
    prev = [x for x in ds if x < a]
    if not prev:
        return None
    upto = [x for x in ds if x <= b]
    if not upto:
        return None
    base_d, end_d = prev[-1], upto[-1]
    if base_d == end_d:
        return None
    v0 = ser[base_d]
    return (ser[end_d] / v0 - 1) * 100 if v0 else None


# ───────────────────── 主流程 ─────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=dt.date.today().isoformat())
    ap.add_argument("--raw", default=str(HERE / "raw"))
    ap.add_argument("--xlsx", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--allow-partial", action="store_true")
    a = ap.parse_args()

    asof = dt.date.fromisoformat(a.asof)
    W = windows(asof)
    base.COLS = as_cols(W)
    base.YTD_LABEL = W["ytd"][2]

    xlsx = a.xlsx
    if not xlsx:
        cand = sorted(HERE.glob("元数据_*.xlsx"))
        xlsx = str(cand[-1]) if cand else base.SRC
    print("META", xlsx)
    rows = load_rows(xlsx)
    used = {c for _, _, subs in base.STRUCT for _, fs, ix in subs for c in list(fs) + list(ix)}
    rows = {c: r for c, r in rows.items() if c in used}
    funds = parse_funds(a.raw)
    idxs = parse_idx(a.raw)

    fresh_f, fresh_i, warn = 0, 0, []
    for code, rec in rows.items():
        is_index = not code.isdigit()
        ser = idxs.get(code) if is_index else funds.get(code)
        ok = False
        for k, (s, e, lab, sub) in W.items():
            v = ret(ser, s, e) if ser else None
            if v is not None:
                rec[k] = round(v, 2)
                ok = True
            elif ser is None:
                pass          # 保留工作簿缓存值
        if ser is None:
            warn.append(f"{code} {rec['name']} 无实时数据，沿用工作簿值")
        elif ok:
            fresh_i += is_index
            fresh_f += (not is_index)

    n_f = sum(1 for c in rows if c.isdigit())
    n_i = len(rows) - n_f
    cov_f = fresh_f / n_f if n_f else 0
    print(f"COVERAGE funds {fresh_f}/{n_f} ({cov_f:.0%})  indices {fresh_i}/{n_i}")
    for w in warn[:12]:
        print("WARN", w)
    if cov_f < 0.8 and not a.allow_partial:
        print("ERROR 基金实时覆盖率不足 80%，已中止，避免发出旧数据。")
        return 1

    groups, stats, meta = base.build(rows)
    s, e = W["wk"][0], W["wk"][1]
    span = f"{s:%y%m%d} – {e:%y%m%d}"
    out_name = a.out or f"产业趋势基金观察池_{s:%y%m%d}-{e:%y%m%d}"
    dst = out_name if os.path.isabs(out_name) else str(pathlib.Path(base.ROOT) / os.path.splitext(out_name)[0])

    p = base.render(groups, stats, meta, dst, span, f"{e:%Y.%m.%d}")
    print("saved:", p)
    for k in ("all", "hold", "科技组", "医药组", "制造组"):
        v = stats[k]["wk"][0]
        print(f"STAT {k} wk={v:+.2f}%")
    print("STAT up_ratio=%.1f%%" % (meta["n_up"] / meta["n_all"] * 100))
    return 0


if __name__ == "__main__":
    sys.exit(main())
