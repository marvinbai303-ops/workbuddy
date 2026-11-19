# -*- coding: utf-8 -*-
"""样板间投顾组合净值预估 · 统一路径
工作区结构：
  Workbuddy/01_代码/<项目>/        脚本
  Workbuddy/03_数据源/<项目>/      数据（xlsx/json/pkl）
  Workbuddy/06_报告与图表/<项目>/  交付物（html/pptx）
  Workbuddy/07_中间产物/<项目>/    临时文件（png等）
"""
import importlib.util
import sys
from pathlib import Path

PROJ = "样板间投顾组合净值预估"
ROOT = Path(__file__).resolve().parents[2]      # .../Documents/Workbuddy
CODE = ROOT / "01_代码" / PROJ
DATA = ROOT / "03_数据源" / PROJ
REPORT = ROOT / "06_报告与图表" / PROJ
TMP = ROOT / "07_中间产物" / PROJ

TRIPLE = DATA / "今日三列对照.json"
PAGE = REPORT / "产业趋势组合2号_今日净值对照.html"


def load_base():
    """加载 持仓回归验证_组合2号.py（含 Q3 持仓与个股日涨跌数据）"""
    p = CODE / "持仓回归验证_组合2号.py"
    spec = importlib.util.spec_from_file_location("base", str(p))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["base"] = mod
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":
    for n in ("CODE", "DATA", "REPORT", "TMP"):
        v = globals()[n]
        print(f"{n:<7}{v}  {'存在' if v.exists() else '缺失'}")
    print("data json:", TRIPLE.exists(), " page:", PAGE.exists())
