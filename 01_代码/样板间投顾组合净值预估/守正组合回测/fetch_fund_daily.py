# -*- coding: utf-8 -*-
"""
守正组合回测 —— 基金日频「单位累计净值」拉取（NeoData）
NeoData 单次硬限制约 10 行，按约 14 天日历分段滚动拉取，按日期去重。
输出：fund_daily.json  {code: {date: cum_nav}}
"""
import subprocess, json, time, re, os
from datetime import date, timedelta

PY = "/Users/yangguang/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
QUERY = "/Users/yangguang/.workbuddy/plugins/cache/cb_teams_marketplace/finance-data/1.7.0/skills/neodata-financial-search/scripts/query.py"
OUT = os.path.dirname(os.path.abspath(__file__))

# code -> (名称, 起始日期)
FUNDS = {
    "007045.OF": ("博道沪深300指数增强C", "2020-01-01"),
    "008593.OF": ("天弘沪深300指数增强发起式C", "2020-01-01"),
    "006594.OF": ("博道中证500指数增强C", "2020-01-01"),
    "001557.OF": ("天弘中证500指数增强C", "2020-01-01"),
    "014202.OF": ("天弘中证1000指数增强C", "2021-12-15"),
    "017954.OF": ("汇添富中证1000指数增强C", "2023-05-01"),
    "019924.OF": ("华泰柏瑞中证2000指数增强C", "2023-12-15"),
    "019919.OF": ("招商中证2000指数增强C", "2023-12-15"),
    "022746.OF": ("博道中证A500指数增强C", "2024-12-15"),
    "023820.OF": ("天弘中证A500指数增强C", "2025-09-01"),
}
END = date(2026, 9, 30)


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


def parse_fund(content):
    """返回 [(date, cum_nav), ...]"""
    out = []
    mlist = list(re.finditer(r'基金代码：(\d{6}\.OF)', content))
    for i, m in enumerate(mlist):
        seg = content[m.end(): (mlist[i+1].start() if i+1 < len(mlist) else len(content))]
        for line in seg.split('\n'):
            line = line.strip().strip('|')
            cells = [c.strip() for c in line.split('|')]
            if len(cells) >= 3 and re.match(r'^\d{4}-\d{2}-\d{2}$', cells[0]):
                try:
                    out.append((cells[0], float(cells[2])))
                except ValueError:
                    pass
    return out


def main():
    fund_daily = {c: {} for c in FUNDS}
    for code, (name, start) in FUNDS.items():
        d0 = date.fromisoformat(start)
        end = d0 + timedelta(days=14)
        step = timedelta(days=14)
        n = 0
        while end <= END:
            qq = f"{name}({code}) {d0.year}年{d0.month}月{d0.day}日到{end.year}年{end.month}月{end.day}日的单位累计净值"
            d = q(qq)
            if d:
                for r in d["data"]["apiData"]["apiRecall"]:
                    if "净值" in r.get("type", ""):
                        for dt, val in parse_fund(r["content"]):
                            fund_daily[code][dt] = val
            n += 1
            end += step
        print(f"{code} done: {len(fund_daily[code])} 天（{n} 次查询）", flush=True)
        time.sleep(0.15)

    json.dump(fund_daily, open(os.path.join(OUT, "fund_daily.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
