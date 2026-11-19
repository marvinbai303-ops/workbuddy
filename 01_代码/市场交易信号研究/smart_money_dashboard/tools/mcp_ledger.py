"""MCP 调用计数。

每发出一次 tools/call 就追加一行到 data/store/mcp_usage.csv，
用于按日核算额度消耗（iFinD 按“调用次数”计费，与返回行数无关）。

同时提供日预算守卫：batch_budget(n) 在单脚本超过当日上限时直接退出，
避免某个脚本失控把额度刷空。
"""
import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import smd_paths as P
    STORE = str(P.DATA / 'store')
except Exception:                      # 旧布局或独立运行
    STORE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'store')

PATH = os.path.join(STORE, 'mcp_usage.csv')
FIELDS = ['ts', 'date', 'script', 'server', 'tool']


def log(server, tool, script=None):
    """记录一次调用。写失败不影响主流程。"""
    try:
        os.makedirs(STORE, exist_ok=True)
        new = not os.path.exists(PATH)
        now = datetime.now()
        with open(PATH, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if new:
                w.writerow(FIELDS)
            w.writerow([now.strftime('%Y-%m-%d %H:%M:%S'), now.strftime('%Y-%m-%d'),
                        script or os.path.basename(sys.argv[0]), server, tool])
    except Exception:
        pass


def count_today(script=None, server=None, day=None):
    """今日已用次数，可按脚本/服务过滤。"""
    day = day or datetime.now().strftime('%Y-%m-%d')
    if not os.path.exists(PATH):
        return 0
    n = 0
    with open(PATH, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['date'] != day:
                continue
            if script and r['script'] != script:
                continue
            if server and r['server'] != server:
                continue
            n += 1
    return n


def summary(day=None):
    """按脚本汇总今日调用，供 update.py status 展示。"""
    day = day or datetime.now().strftime('%Y-%m-%d')
    if not os.path.exists(PATH):
        return {}
    out = {}
    with open(PATH, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['date'] == day:
                out[r['script']] = out.get(r['script'], 0) + 1
    return out


def guard(limit, script=None):
    """超预算直接终止：宁可这一项不更新，也不要把额度打穿。"""
    used = count_today(script)
    if used >= limit:
        sys.exit(f'[BUDGET] {script or sys.argv[0]} 今日已用 {used} 次，达到上限 {limit}，终止。')
