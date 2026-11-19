#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一路径解析：代码、数据、报告分处三棵目录。

2026-11-18 工作区重整后的布局：
    01_代码/市场交易信号研究/smart_money_dashboard/        ← 本文件所在（*.py + tools/）
    03_数据源/市场交易信号研究/smart_money_dashboard/data/  ← 数据仓、快照、raw_*
    03_数据源/市场交易信号研究/smart_money_dashboard/out/   ← 中间产物 dashboard_data.json
    06_报告与图表/市场交易信号研究/smart_money_dashboard/out/ ← 成品 聪明钱温度计.html

若三棵目录被移动，可用环境变量覆盖：
    SMD_DATA_ROOT   指向 03_数据源/<项目>   （其下应有 data/ 与 out/）
    SMD_REPORT_DIR  指向 06_报告与图表/<项目>/out

兼容旧布局：若同目录下存在 data/（代码与数据未拆分），自动回退到本地布局。
"""
import os
from pathlib import Path

CODE = Path(__file__).resolve().parent
REL = f'{CODE.parent.name}/{CODE.name}'          # 市场交易信号研究/smart_money_dashboard
ROOT = CODE.parents[2]                            # …/Documents/Workbuddy

_data_root = os.environ.get('SMD_DATA_ROOT')
_report_dir = os.environ.get('SMD_REPORT_DIR')

if _data_root:
    DATA_ROOT = Path(_data_root)
elif (ROOT / '03_数据源' / REL / 'data').exists():
    DATA_ROOT = ROOT / '03_数据源' / REL
elif (CODE / 'data').exists():                    # 旧布局：代码与数据同目录
    DATA_ROOT = CODE
else:                                             # 首次运行，按新布局创建
    DATA_ROOT = ROOT / '03_数据源' / REL

if _report_dir:
    REPORT_DIR = Path(_report_dir)
elif (ROOT / '06_报告与图表' / REL / 'out').exists():
    REPORT_DIR = ROOT / '06_报告与图表' / REL / 'out'
elif (CODE / 'out').exists() and (CODE / 'data').exists():
    REPORT_DIR = CODE / 'out'
else:
    REPORT_DIR = ROOT / '06_报告与图表' / REL / 'out'

DATA = DATA_ROOT / 'data'
MID = DATA_ROOT / 'out'            # 中间产物（dashboard_data.json、失败日志）
REPORT = REPORT_DIR                # 成品 HTML
TOOLS = CODE / 'tools'


def ensure():
    """写入前建目录；返回 (DATA, MID, REPORT)"""
    for p in (DATA, MID, REPORT):
        Path(p).mkdir(parents=True, exist_ok=True)
    return DATA, MID, REPORT


if __name__ == '__main__':
    print(f'CODE   = {CODE}')
    print(f'DATA   = {DATA}   exists={DATA.exists()}')
    print(f'MID    = {MID}    exists={MID.exists()}')
    print(f'REPORT = {REPORT} exists={REPORT.exists()}')
