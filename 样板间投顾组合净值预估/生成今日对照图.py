# -*- coding: utf-8 -*-
"""生成手机端可读的今日净值对照图（750px 宽，2 倍像素密度）"""
import json
import subprocess
import sys
import os

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DATA = "今日三列对照.json"


def html(rows, date="2026-11-16", title="产业趋势组合2号 · 今日净值对照"):
    def cell(v):
        if v is None:
            return '<td style="text-align:center;color:#B4B2A9;font-size:15px;">待公布</td>'
        col = "#A32D2D"
        return (f'<td style="text-align:right;color:{col};font-size:17.5px;font-weight:500;'
                f'font-variant-numeric:tabular-nums;padding-left:4px;">{v:+.2f}%</td>')

    body = []
    for r in rows:
        body.append(
            '<tr>'
            f'<td style="padding:13px 0;border-bottom:1px solid #EDECE7;">'
            f'<div style="font-size:15px;color:#2C2C2A;font-weight:500;">{r["name"]}</div>'
            f'<div style="font-size:11.5px;color:#888780;margin-top:2px;">{r["th"]}</div></td>'
            f'<td style="padding:13px 16px 13px 8px;text-align:right;color:#185FA5;font-size:17.5px;'
            f'font-weight:500;font-variant-numeric:tabular-nums;border-bottom:1px solid #EDECE7;">'
            f'{r["a2"]:+.2f}%</td>'
            + cell(r["real"]).replace("<td ", '<td style="border-bottom:1px solid #EDECE7;" ')
            + '</tr>')

    return f'''<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{width:750px;background:#fff;font-family:-apple-system,"PingFang SC","Helvetica Neue",sans-serif;
-webkit-font-smoothing:antialiased;padding:34px 30px 26px;}}
</style></head><body>
<div style="font-size:23px;color:#1F3864;font-weight:500;letter-spacing:-0.2px;">{title}</div>
<div style="font-size:14px;color:#888780;margin-top:6px;">{date}　口径：三季报持仓 + 价格漂移 + 未披露仓位补全</div>
<div style="display:flex;gap:8px;margin:18px 0 6px;flex-wrap:wrap;">
<span style="background:#E6F1FB;color:#0C447C;font-size:12.5px;padding:6px 11px;border-radius:7px;">CPO −6.40%</span>
<span style="background:#E1F5EE;color:#085041;font-size:12.5px;padding:6px 11px;border-radius:7px;">半导体材料设备 −5.11%</span>
<span style="background:#FAEEDA;color:#854F0B;font-size:12.5px;padding:6px 11px;border-radius:7px;">存储芯片 −5.81%</span>
</div>
<table style="width:100%;border-collapse:collapse;table-layout:fixed;">
<colgroup><col style="width:42%"><col style="width:34%"><col style="width:24%"></colgroup>
<thead><tr>
<th style="text-align:left;font-size:12px;color:#888780;font-weight:400;padding:14px 0 9px;border-bottom:1px solid #D3D1C7;">基金</th>
<th style="text-align:right;font-size:12px;color:#888780;font-weight:400;padding:14px 16px 9px 8px;border-bottom:1px solid #D3D1C7;">持仓补全预计涨跌幅</th>
<th style="text-align:right;font-size:12px;color:#888780;font-weight:400;padding:14px 0 9px;border-bottom:1px solid #D3D1C7;">今日实际</th>
</tr></thead><tbody>{''.join(body)}</tbody></table>
<div style="margin-top:16px;font-size:11.5px;color:#888780;line-height:1.7;">
预估为 9 月 30 日季报持仓叠加个股价格漂移后的结果，未反映管理人调仓；<br>
差距即为调仓幅度。数据源：Wind 净值、iFinD 指数。
</div>
</body></html>'''


def render(out_html="今日对照_手机版.html", out_png="产业趋势2号_今日净值对照.png"):
    data = json.load(open(DATA, encoding="utf-8"))
    order = ["017612", "016371", "013841", "162214", "017489", "009993", "017745"]
    names = {"017612": "宏利复兴伟业C", "016371": "信澳业绩驱动C", "013841": "银华集成电路C",
             "162214": "宏利领先中小盘", "017489": "嘉实信息产业C", "009993": "嘉实前沿创新",
             "017745": "嘉实绿色主题C"}
    theme = {"017612": "CPO", "016371": "CPO", "017489": "CPO", "013841": "半导体材料设备",
             "162214": "半导体材料设备", "009993": "半导体+光模块", "017745": "存储芯片"}
    rows = []
    for k in order:
        d = data.get(k, {})
        rows.append(dict(name=names[k], th=theme[k],
                         a2=d.get("a2") if d.get("a2") is not None else 0.0,
                         real=d.get("real")))
    open(out_html, "w", encoding="utf-8").write(html(rows))
    path = os.path.abspath(out_html)
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--force-device-scale-factor=2", "--default-background-color=FFFFFFFF",
           f"--screenshot={os.path.abspath(out_png)}", "--window-size=750,1000", f"file://{path}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-800:])
    from PIL import Image
    im = Image.open(out_png).convert("RGB")
    w, h = im.size
    px = im.load()
    bottom = h - 1
    while bottom > 0:
        row = [px[x, bottom] for x in range(0, w, 7)]
        if any(v < 250 for c in row for v in c):
            break
        bottom -= 1
    im.crop((0, 0, w, min(h, bottom + 40))).save(out_png)
    return os.path.abspath(out_png)


if __name__ == "__main__":
    print(render())
