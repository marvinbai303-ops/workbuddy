# -*- coding: utf-8 -*-
"""补拉中证A500指数月频收盘（代码 000510.SH，NeoData 返回 .SH 而非 .CSI）"""
import subprocess, json, time, re, os
from datetime import date

PY = "/Users/yangguang/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
QUERY = "/Users/yangguang/.workbuddy/plugins/cache/cb_teams_marketplace/finance-data/1.7.0/skills/neodata-financial-search/scripts/query.py"
OUT = os.path.dirname(os.path.abspath(__file__))


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


def months_between(y0, m0, y1, m1):
    res = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        res.append((y, m))
        m += 1
        if m > 12:
            m = 1; y += 1
    return res


def main():
    res = {}
    for (y, m) in months_between(2020, 1, 2026, 9):
        mstart = date(y, m, 1)
        mend = date(y, m+1, 1) if m < 12 else date(y, 12, 31)
        if m < 12:
            mend = mend.fromordinal(mend.toordinal() - 1)
        rng = f"{mstart.year}年{mstart.month}月{mstart.day}日到{mend.year}年{mend.month}月{mend.day}日"
        d = q(f"中证A500(000510.SH) {rng}的收盘价")
        if d:
            try:
                for r in d["data"]["apiData"]["apiRecall"]:
                    content = r["content"]
                    # 找最后一行有数值的收盘价
                    rows = []
                    for line in content.split("\n"):
                        line = line.strip().strip("|")
                        cells = [c.strip() for c in line.split("|")]
                        if len(cells) >= 5 and re.match(r'^\d{4}-\d{2}-\d{2}$', cells[0]):
                            rows.append(cells)
                    for row in reversed(rows):
                        v = row[4].replace(",", "")
                        if re.match(r'^[\d.]+$', v):
                            res[row[0]] = v
                            break
            except Exception as e:
                print(f"err {y}-{m}: {e}")
        print(f"{y}-{m:02d} done", flush=True)
        time.sleep(0.3)

    # 合并到 index_month.json
    p = os.path.join(OUT, "index_month.json")
    data = json.load(open(p, encoding="utf-8"))
    data["000510.CSI"] = res
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("A500 merged, count =", len(res), flush=True)


if __name__ == "__main__":
    main()
