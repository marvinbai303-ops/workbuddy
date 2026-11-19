# -*- coding: utf-8 -*-
"""
守正组合回测 —— 指数日频「收盘点位」拉取（NeoData，统一行情查询）
注意：「统一行情查询」仅返回约最近 9 个日历日，故按约 8 天日历分段滚动，去重。
输出：index_daily.json  {code: {date: close}}
"""
import subprocess, json, time, re, os
from datetime import date, timedelta

PY = "/Users/yangguang/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
QUERY = "/Users/yangguang/.workbuddy/plugins/cache/cb_teams_marketplace/finance-data/1.7.0/skills/neodata-financial-search/scripts/query.py"
OUT = os.path.dirname(os.path.abspath(__file__))

INDICES = [
    ("沪深300(000300.SH)", "000300.SH", "2019-12-25", "2020-03-01"),
    ("中证1000(000852.SH)", "000852.SH", "2019-12-25", "2023-07-01"),
    ("中证2000(932000.CS)", "932000.CSI", "2019-12-25", "2024-03-01"),
    ("中证A500(000510.SH)", "000510.CSI", "2019-12-25", "2025-11-01"),
]


def q(query):
    for i in range(3):
        try:
            r = subprocess.run([PY, QUERY, "--query", query, "--data-type", "api"],
                               capture_output=True, text=True, timeout=60)
            d = json.loads(r.stdout.strip())
            if d.get("code") == "200":
                return d
            time.sleep(1.0 + i)
        except Exception:
            time.sleep(1.0 + i)
    return None


def parse_idx(content):
    out = []
    for line in content.split('\n'):
        line = line.strip().strip('|')
        cells = [c.strip() for c in line.split('|')]
        if len(cells) >= 5 and re.match(r'^\d{4}-\d{2}-\d{2}$', cells[0]):
            v = cells[4].replace(',', '')
            if re.match(r'^[\d.]+$', v):
                try:
                    out.append((cells[0], float(v)))
                except ValueError:
                    pass
    return out


def main():
    index_daily = {code: {} for _, code, _, _ in INDICES}
    for qname, code, start, end in INDICES:
        d0 = date.fromisoformat(start)
        d1 = date.fromisoformat(end)
        cur = d0 + timedelta(days=8)
        n = 0
        while cur <= d1:
            qq = f"{qname}指数 {d0.year}年{d0.month}月{d0.day}日到{cur.year}年{cur.month}月{cur.day}日的收盘价"
            d = q(qq)
            if d:
                for r in d["data"]["apiData"]["apiRecall"]:
                    for dt, val in parse_idx(r["content"]):
                        index_daily[code][dt] = val
            n += 1
            cur += timedelta(days=8)
        print(f"{code} done: {len(index_daily[code])} 天（{n} 次查询）", flush=True)
        time.sleep(0.15)

    json.dump(index_daily, open(os.path.join(OUT, "index_daily.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
