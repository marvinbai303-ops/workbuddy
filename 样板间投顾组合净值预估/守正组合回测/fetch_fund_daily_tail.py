# -*- coding: utf-8 -*-
"""补拉 5 只晚成立基金最后一段（2026-09）日净值，并入 fund_daily.json"""
import subprocess, json, time, re, os

PY = "/Users/yangguang/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
QUERY = "/Users/yangguang/.workbuddy/plugins/cache/cb_teams_marketplace/finance-data/1.7.0/skills/neodata-financial-search/scripts/query.py"
OUT = os.path.dirname(os.path.abspath(__file__))

TARGETS = {
    "017954.OF": "汇添富中证1000指数增强C",
    "019924.OF": "华泰柏瑞中证2000指数增强C",
    "019919.OF": "招商中证2000指数增强C",
    "022746.OF": "博道中证A500指数增强C",
    "023820.OF": "天弘中证A500指数增强C",
}


def q(query):
    for i in range(3):
        try:
            r = subprocess.run([PY, QUERY, "--query", query, "--data-type", "api"],
                               capture_output=True, text=True, timeout=60)
            d = json.loads(r.stdout.strip())
            if d.get("code") == "200":
                return d
            time.sleep(1.0)
        except Exception:
            time.sleep(1.0)
    return None


def parse_fund(content):
    out = []
    mlist = list(re.finditer(r'基金代码：(\d{6}\.OF)', content))
    for i, m in enumerate(mlist):
        seg = content[m.end(): (mlist[i + 1].start() if i + 1 < len(mlist) else len(content))]
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
    fd = json.load(open(os.path.join(OUT, "fund_daily.json"), encoding="utf-8"))
    for code, name in TARGETS.items():
        d = q(f"{name}({code}) 2026年9月1日到2026年9月30日的单位累计净值")
        added = 0
        if d:
            for r in d["data"]["apiData"]["apiRecall"]:
                if "净值" in r.get("type", ""):
                    for dt, val in parse_fund(r["content"]):
                        if dt not in fd[code]:
                            added += 1
                        fd[code][dt] = val
        print(f"{code}: 新增 {added} 天，总 {len(fd[code])} 天，末日期 {max(fd[code].keys())}", flush=True)
        time.sleep(0.3)
    json.dump(fd, open(os.path.join(OUT, "fund_daily.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
