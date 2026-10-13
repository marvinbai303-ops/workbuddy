# -*- coding: utf-8 -*-
"""拉取回测基日(2020-01-02)的基金净值与指数收盘，供首月收益计算"""
import subprocess, json, re, os

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
INDICES = [
    ("沪深300(000300.SH)", "000300.SH"),
    ("中证1000(000852.SH)", "000852.SH"),
    ("中证2000(932000.CS)", "932000.CSI"),
    ("中证A500(000510.SH)", "000510.CSI"),
]


def q(query):
    for i in range(3):
        try:
            r = subprocess.run([PY, QUERY, "--query", query, "--data-type", "api"],
                               capture_output=True, text=True, timeout=60)
            d = json.loads(r.stdout.strip())
            if d.get("code") == "200":
                return d
        except Exception:
            pass
    return None


def parse_fund(content):
    out = {}
    mlist = list(re.finditer(r'基金代码：(\d{6}\.OF)', content))
    for i, m in enumerate(mlist):
        code = m.group(1)
        seg = content[m.end(): (mlist[i+1].start() if i+1 < len(mlist) else len(content))]
        for line in seg.split('\n'):
            line = line.strip().strip('|')
            cells = [c.strip() for c in line.split('|')]
            if len(cells) >= 3 and re.match(r'^\d{4}-\d{2}-\d{2}$', cells[0]):
                out[code] = cells[2]
                break
    return out


def parse_idx(content):
    for line in content.split('\n'):
        line = line.strip().strip('|')
        cells = [c.strip() for c in line.split('|')]
        if len(cells) >= 5 and re.match(r'^\d{4}-\d{2}-\d{2}$', cells[0]):
            v = cells[4].replace(',', '')
            if re.match(r'^[\d.]+$', v):
                return v
    return None


def main():
    base_fund = {}
    base_idx = {}

    names = "、".join(f"{n}({c})" for c, n in FUNDS.items())
    d = q(f"{names} 2020年1月2日的单位累计净值")
    if d:
        for r in d["data"]["apiData"]["apiRecall"]:
            if "净值" in r.get("type", ""):
                base_fund.update(parse_fund(r["content"]))

    for qname, ikey in INDICES:
        d = q(f"{qname}指数 2020年1月2日的收盘价")
        if d:
            for r in d["data"]["apiData"]["apiRecall"]:
                v = parse_idx(r["content"])
                if v:
                    base_idx[ikey] = v

    base = {"fund": base_fund, "index": base_idx}
    json.dump(base, open(os.path.join(OUT, "base.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("base fund:", base_fund, flush=True)
    print("base index:", base_idx, flush=True)


if __name__ == "__main__":
    main()
