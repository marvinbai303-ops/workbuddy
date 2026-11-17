# -*- coding: utf-8 -*-
"""生成独立的 HTML 版今日净值对照页（可直接在预览面板或浏览器打开）"""
import json
import os

DATA = "今日三列对照.json"
OUT = "产业趋势组合2号_今日净值对照.html"

NAMES = {"017612": "宏利复兴伟业C", "016371": "信澳业绩驱动C", "013841": "银华集成电路C",
         "162214": "宏利领先中小盘", "017489": "嘉实信息产业C", "009993": "嘉实前沿创新",
         "017745": "嘉实绿色主题C"}
THEME = {"017612": "CPO", "016371": "CPO", "017489": "CPO", "013841": "半导体材料设备",
         "162214": "半导体材料设备", "009993": "半导体+光模块", "017745": "存储芯片"}
ORDER = ["017612", "016371", "013841", "162214", "017489", "009993", "017745"]
INDEX = [("CPO 886033.TI", "−6.40%", "#E6F1FB", "#0C447C"),
         ("半导体材料设备 931743.CSI", "−5.11%", "#E1F5EE", "#085041"),
         ("存储芯片 886042.TI", "−5.81%", "#FAEEDA", "#854F0B")]


def bar(v, color, scale=11.0):
    if v is None:
        return '<div style="height:4px;"></div>'
    w = min(abs(v) / scale * 100, 100)
    return ('<div style="height:4px;background:#F1EFE8;border-radius:2px;margin-top:5px;">'
            f'<div style="width:{w:.0f}%;height:4px;background:{color};border-radius:2px;"></div></div>')


def build(rows, date="2026-11-16"):
    chips = "".join(
        f'<span style="background:{bg};color:{fg};font-size:12px;padding:5px 10px;'
        f'border-radius:6px;">{n}　{v}</span>' for n, v, bg, fg in INDEX)

    trs = []
    for r in rows:
        real_cell = ('<div style="color:#888780;font-size:14px;">待公布</div>' + bar(None, "#D85A30")
                     if r["real"] is None else
                     f'<div style="color:#993C1D;font-size:15px;font-weight:500;'
                     f'font-variant-numeric:tabular-nums;">{r["real"]:+.2f}%</div>'
                     + bar(r["real"], "#D85A30"))
        trs.append(
            '<tr>'
            f'<td style="padding:13px 10px 13px 0;border-bottom:1px solid #EDECE7;">'
            f'<div style="font-size:14px;color:#2C2C2A;font-weight:500;">{r["name"]}</div></td>'
            f'<td style="padding:13px 10px;border-bottom:1px solid #EDECE7;color:#5F5E5A;'
            f'font-size:13px;">{r["th"]}</td>'
            f'<td style="padding:13px 18px 13px 10px;border-bottom:1px solid #EDECE7;">'
            f'<div style="color:#0C447C;font-size:15px;font-variant-numeric:tabular-nums;">'
            f'{r["a2"]:+.2f}%</div>' + bar(r["a2"], "#B5D4F4") + '</td>'
            f'<td style="padding:13px 0 13px 10px;border-bottom:1px solid #EDECE7;width:23%;">'
            f'{real_cell}</td>'
            '</tr>')

    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>今日重点基金净值对照（{date}）</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{background:#F7F6F3;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",
    "Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased;padding:36px 20px;}}
  .wrap{{max-width:820px;margin:0 auto;background:#fff;border-radius:14px;
    border:0.5px solid rgba(0,0,0,0.08);padding:28px 30px 18px;}}
  table{{width:100%;border-collapse:collapse;table-layout:fixed;}}
  th{{text-align:left;font-weight:400;font-size:11.5px;color:#888780;
    padding:0 10px 10px 0;border-bottom:1px solid #D3D1C7;}}
</style></head>
<body><div class="wrap">
  <div style="font-size:20px;color:#1F3864;font-weight:500;">今日重点基金净值对照（{date}）</div>
  <div style="font-size:12.5px;color:#888780;margin-top:6px;">口径：三季报持仓+价格漂移+未披露持仓用赛道补全</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 4px;">{chips}</div>
  <table style="margin-top:14px;">
    <colgroup><col style="width:31%"><col style="width:22%"><col style="width:24%"><col style="width:23%"></colgroup>
    <thead><tr>
      <th>基金</th><th>对照赛道</th>
      <th style="color:#0C447C;">三季报持仓补全预计涨跌幅</th>
      <th style="color:#993C1D;">今日实际</th>
    </tr></thead>
    <tbody>{"".join(trs)}</tbody>
  </table>
</div></body></html>'''


def main():
    data = json.load(open(DATA, encoding="utf-8"))
    rows = []
    for k in ORDER:
        d = data.get(k, {})
        rows.append(dict(name=NAMES[k], th=THEME[k], a2=d.get("a2", 0.0), real=d.get("real")))
    open(OUT, "w", encoding="utf-8").write(build(rows))
    return os.path.abspath(OUT)


if __name__ == "__main__":
    print(main())
