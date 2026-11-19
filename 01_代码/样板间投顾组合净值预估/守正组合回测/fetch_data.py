# -*- coding: utf-8 -*-
"""
守正组合回测 —— 数据拉取脚本 v2（NeoData）
修正：
  1) 基金解析：按「基金代码：XXX.OF）」切块，取每块第一行（月末最新交易日）
  2) 指数解析：取块内第一行有效收盘价（月末最新交易日）
  3) 指数代码：按名称解析（中证1000/2000/A500），归一化存储
"""
import subprocess, json, time, re, os, sys
from datetime import date

PY = "/Users/yangguang/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
QUERY = "/Users/yangguang/.workbuddy/plugins/cache/cb_teams_marketplace/finance-data/1.7.0/skills/neodata-financial-search/scripts/query.py"
OUT = os.path.dirname(os.path.abspath(__file__))

FUNDS = {
    "007045.OF": "博道沪深300指数增强C",
    "008593.OF": "天弘沪深300指数增强发起式C",
    "022746.OF": "博道中证A500指数增强C",
    "023820.OF": "天弘中证A500指数增强C",
    "006594.OF": "博道中证500指数增强C",
    "001557.OF": "天弘中证500指数增强C",
    "017954.OF": "汇添富中证1000指数增强C",
    "014202.OF": "天弘中证1000指数增强C",
    "019924.OF": "华泰柏瑞中证2000指数增强C",
    "019919.OF": "招商中证2000指数增强C",
    "000917.OF": "嘉实快线货币A",
}
# 指数（NeoData 查询用名 -> 规范化存储代码）
INDICES = [
    ("沪深300(000300.SH)", "000300.SH"),
    ("中证1000(000852.SH)", "000852.SH"),
    ("中证2000(932000.CS)", "932000.CSI"),
    ("中证A500(000510.SH)", "000510.CSI"),
]


def q(query, data_type="api", retries=3):
    for i in range(retries):
        try:
            r = subprocess.run([PY, QUERY, "--query", query, "--data-type", data_type],
                               capture_output=True, text=True, timeout=60)
            d = json.loads(r.stdout.strip())
            if d.get("code") == "200":
                return d
            time.sleep(1.0 + i)
        except Exception:
            time.sleep(1.0 + i)
    return None


def months_between(y0, m0, y1, m1):
    res = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        res.append((y, m))
        m += 1
        if m > 12:
            m = 1; y += 1
    return res


def parse_fund_content(content):
    """按基金代码切块，取每块第一行(月末最新交易日) -> {code: (date, cum_nav)}"""
    out = {}
    mlist = list(re.finditer(r'基金代码：(\d{6}\.OF)', content))
    for i, m in enumerate(mlist):
        code = m.group(1)
        start = m.end()
        end = mlist[i + 1].start() if i + 1 < len(mlist) else len(content)
        seg = content[start:end]
        for line in seg.split('\n'):
            line = line.strip().strip('|')
            cells = [c.strip() for c in line.split('|')]
            if len(cells) >= 3 and re.match(r'^\d{4}-\d{2}-\d{2}$', cells[0]):
                out[code] = (cells[0], cells[2])   # 日期, 单位累计净值
                break
    return out


def parse_index_content(content):
    """取第一个有效收盘价(月末最新交易日) -> (date, close)"""
    for line in content.split('\n'):
        line = line.strip().strip('|')
        cells = [c.strip() for c in line.split('|')]
        if len(cells) >= 5 and re.match(r'^\d{4}-\d{2}-\d{2}$', cells[0]):
            v = cells[4].replace(',', '')
            if re.match(r'^[\d.]+$', v):
                return (cells[0], v)
    return None


def main():
    months = months_between(2020, 1, 2026, 9)
    fund_month = {c: {} for c in FUNDS}
    index_month = {ikey: {} for _, ikey in INDICES}

    fund_names = "、".join(f"{n}({c})" for c, n in FUNDS.items())

    for (y, m) in months:
        mstart = date(y, m, 1)
        if m == 12:
            mend = date(y, 12, 31)
        else:
            mend = date(y, m + 1, 1).fromordinal(date(y, m + 1, 1).toordinal() - 1)
        rng = f"{mstart.year}年{mstart.month}月{mstart.day}日到{mend.year}年{mend.month}月{mend.day}日"

        # ---- 基金（一次查 11 只）----
        fd = q(f"{fund_names} {rng}的单位累计净值")
        if fd:
            for r in fd["data"]["apiData"]["apiRecall"]:
                if "净值" in r.get("type", ""):
                    parsed = parse_fund_content(r["content"])
                    for code, (dt, val) in parsed.items():
                        if code in fund_month:
                            fund_month[code][dt] = val

        # ---- 指数（逐个查，用明确代码）----
        for qname, ikey in INDICES:
            id_ = q(f"{qname}指数 {rng}的收盘价")
            if id_:
                for r in id_["data"]["apiData"]["apiRecall"]:
                    p = parse_index_content(r["content"])
                    if p:
                        index_month[ikey][p[0]] = p[1]

        print(f"{y}-{m:02d} done", flush=True)
        time.sleep(0.2)

    with open(os.path.join(OUT, "fund_month.json"), "w", encoding="utf-8") as f:
        json.dump(fund_month, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "index_month.json"), "w", encoding="utf-8") as f:
        json.dump(index_month, f, ensure_ascii=False, indent=1)
    # 打印统计
    for c, d in fund_month.items():
        print(f"fund {c}: {len(d)} 个月", flush=True)
    for c, d in index_month.items():
        print(f"index {c}: {len(d)} 个月", flush=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
