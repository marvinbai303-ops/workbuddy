"""午盘全市场快照：iFinD 逐股小时K → data/inbox/noon_YYYY-MM-DD.csv

口径（与 2026-11-17 已验收脚本一致）：
  * 池：沪深A股，非 ST/*ST，非北交所
  * 只取当日 10:30 与 11:30 两根已完成小时柱
  * 前收 = 10:30 柱收盘价 − 该柱涨跌（交易所当日参考昨收，含除权调整）
  * 涨跌幅 = 100 × (11:30 收盘 / 前收 − 1)
  * 成交额/成交量/换手率 = 两根柱求和
  * 全天停牌或无成交（无柱或额为零）剔除，不记为平盘
"""
import csv, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'tools'))
import ifind_mcp as M

BASE = Path(__file__).resolve().parent
import smd_paths as P

# ---- 额度护栏：逐股小时频接口单次运行约 500 次调用（iFinD 按次计费）
if __name__ == '__main__' and '--allow-heavy' not in sys.argv:
    sys.exit('[BUDGET] 本脚本走逐股小时频接口，单次约 500 次调用，已默认禁用。\n'
             '         确认要跑请追加 --allow-heavy；日常更新用 update.py + 日更序列脚本。')

# 只认第一个非选项参数作为日期；否则 '--allow-heavy' 会被当成日期目录名
DATE = next((a for a in sys.argv[1:] if not a.startswith('-')), time.strftime('%Y-%m-%d'))
RAW = P.DATA / 'raw_noon' / DATE
RAW.mkdir(parents=True, exist_ok=True)
CONC = 3
IND = '收盘价,成交量,成交额,涨跌,换手率'

_lock = __import__('threading').Lock()
_last = [0.0]
MIN_GAP = 0.35          # 全局最小请求间隔（秒），iFinD 轻量级账号有独立限流池


def _throttle():
    with _lock:
        wait = MIN_GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()


def parse_table(ans):
    ans = ans.replace('\\n', '\n')
    lines = [l for l in ans.splitlines() if l.strip().startswith('|')]
    if not lines:
        return [], []
    tab = [[v.strip() for v in l.strip().strip('|').split('|')] for l in lines]
    head = tab[0]
    body = [r for r in tab[2:] if len(r) == len(head)]
    return head, body


def _rows_from(p, tag):
    """把一次选股回执变成行列表：内联表格优先，被截断则下载 csv（上限 1000 行）。"""
    import re
    from urllib.request import urlopen
    total = p['selectedSecuritiesCount']
    head, body = parse_table(p['answer'])
    ci = head.index('股票代码')
    ni = head.index('股票简称') if '股票简称' in head else None
    rows = [{'code': r[ci], 'name': r[ni] if ni is not None else ''} for r in body]
    if len(rows) == total:
        return rows
    urls = re.findall(r'https?://o\.thsi\.cn/[^\s\)"\\<>]+\.csv', p['answer'])
    if not urls:
        raise RuntimeError(f'{tag}: 截断且无下载链接')
    raw_bytes = urlopen(urls[0], timeout=120).read()
    (RAW / f'universe_{tag}.csv').write_bytes(raw_bytes)
    for enc in ('utf-8-sig', 'gb18030'):
        try:
            txt = raw_bytes.decode(enc); break
        except UnicodeDecodeError:
            continue
    else:
        raise RuntimeError(f'{tag}: 编码无法识别')
    rd = list(csv.DictReader(txt.splitlines()))
    rows = [{'code': (r.get('股票代码') or '').strip(),
             'name': (r.get('股票简称') or '').strip()} for r in rd]
    assert len(rows) == total, f'{tag}: csv {len(rows)} ≠ 声明 {total}（超过 1000 行上限）'
    return rows


def universe():
    q = '沪深A股，非ST，非*ST，非北交所。显示股票代码、股票简称。'
    d = M.call('search_stocks', {'query': q}, timeout=180)
    (RAW / 'universe.json').write_text(json.dumps({'query': q, 'data': d}, ensure_ascii=False))
    total = d['data']['selectedSecuritiesCount']
    print(f'  声明 {total} 只，按代码前缀分页')

    out, got = {}, 0
    for pre in '000 001 002 003 300 301 302 600 601 603 605 688 689'.split():
        qq = f'沪深A股，非ST，非*ST，非北交所，股票代码以{pre}开头。显示股票代码、股票简称。'
        dd = M.call('search_stocks', {'query': qq}, timeout=180)
        (RAW / f'universe_{pre}.json').write_text(json.dumps({'query': qq, 'data': dd}, ensure_ascii=False))
        rs = _rows_from(dd['data'], pre)
        assert all(r['code'].startswith(pre) for r in rs), pre
        for r in rs:
            if r['code'].endswith(('.SH', '.SZ')):
                out[r['code']] = r['name']
        got += len(rs)
        print(f'  {pre}: {len(rs)}')
        time.sleep(0.4)
    assert len(out) == got == total, f'分页合计 {len(out)}/{got} ≠ 声明 {total}'
    return [{'code': k, 'name': v} for k, v in out.items()]


def fetch_batch(args):
    name, codes = args
    fp = RAW / f'{name}.json'
    if fp.exists():
        try:
            d = json.loads(fp.read_text())
            payload = d.get('data', {})
            # 兼容早期落盘的 envelope 结构（多包一层 data）
            if 'tables' not in payload and isinstance(payload.get('data'), dict):
                payload = payload['data']
            if payload.get('tables'):
                return name, payload
        except Exception:
            pass
    last = None
    for attempt in range(6):
        _throttle()
        try:
            d = M.call('stock_highfreq_quotes',
                       {'symbols': ','.join(codes), 'indicators': IND,
                        'data_mode': 'highfreq', 'interval': 60}, timeout=120)
            if d.get('code') != 1:
                raise RuntimeError(f'code={d.get("code")} msg={d.get("msg")}')
            payload = d['data']
            fp.write_text(json.dumps({'retrieved_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
                                      'symbols': codes, 'data': payload}, ensure_ascii=False))
            return name, payload
        except Exception as e:
            last = e
            rate = '429' in str(e) or '过于频繁' in str(e)
            time.sleep((6 if rate else 1.5) * (attempt + 1))
    raise RuntimeError(f'{name} 失败: {last}')


def build_recs(byc, codes, names, expect=('10:30', '11:30')):
    """逐股核算。前收取自首根柱（收盘−涨跌），量额对全部柱求和。
    午盘：expect=('10:30','11:30')；日终：expect=('10:30','11:30','14:00','15:00')。"""
    recs, excluded, warn = [], [], []
    for c in codes:
        bars = sorted(byc.get(c, []), key=lambda x: x['time'])
        if not bars:
            excluded.append((c, names.get(c, ''), '无当日行情（全天停牌或未上市）'))
            continue
        times = [b['time'][-5:] for b in bars]
        if times != list(expect):
            excluded.append((c, names.get(c, ''), f'柱不完整 {times}'))
            continue
        b0, b1 = bars[0], bars[-1]
        close, ref = float(b1['收盘价']), float(b0['收盘价']) - float(b0['涨跌'])
        amt = sum(float(b['成交额']) for b in bars)
        vol = sum(float(b['成交量']) for b in bars)
        turn = sum(float(b['换手率']) for b in bars)
        chg_sum = sum(float(b['涨跌']) for b in bars)
        if amt <= 0 or vol <= 0:
            excluded.append((c, names.get(c, ''), '午盘零成交'))
            continue
        if ref <= 0 or close <= 0:
            excluded.append((c, names.get(c, ''), f'价格异常 close={close} ref={ref}'))
            continue
        if abs((close - ref) - chg_sum) > 0.021:
            warn.append((c, round((close - ref) - chg_sum, 4)))
        recs.append({'date': DATE, 'code': c, 'name': names.get(c, ''),
                     'close_unadjusted': f'{close:.4f}',
                     'return_pct': f'{100*(close/ref-1):.10f}',
                     'amount_yuan': f'{amt:.2f}', 'volume_shares': f'{vol:.0f}',
                     'turnover_pct': f'{turn:.8f}'})
    return recs, excluded, warn


def collect(results, batches, codes, cutoff='11:30'):
    """把各批 tables 按证券聚合成 {code: [bar, ...]}，只保留 <= cutoff 的柱。"""
    byc = {}
    for name, _ in batches:
        tab = results[name]['tables']
        head, body = tab[0], tab[1:]
        for r in body:
            rec = dict(zip(head, r))
            t = rec['time']
            if not t.startswith(DATE) or t > f'{DATE} {cutoff}':
                continue
            byc.setdefault(rec['证券代码'], []).append(rec)
    return byc


def main():
    print('[1/4] 取股票池')
    uni = universe()
    codes = sorted({r['code'] for r in uni if r['code'].endswith(('.SH', '.SZ'))})
    names = {r['code']: r['name'] for r in uni}
    print(f'  沪深A股 非ST {len(codes)} 只')

    print('[2/4] 逐股小时K')
    batches = [(f'noon_{i//10:04d}', codes[i:i + 10]) for i in range(0, len(codes), 10)]
    results = {}
    with ThreadPoolExecutor(max_workers=CONC) as ex:
        for k, (name, d) in enumerate(ex.map(fetch_batch, batches), 1):
            results[name] = d
            if k % 50 == 0 or k == len(batches):
                print(f'  {k}/{len(batches)}')

    print('[3/4] 逐股核算')
    byc = collect(results, batches, codes)
    recs, excluded, warn = build_recs(byc, codes, names)

    recs.sort(key=lambda r: r['code'])
    out = P.DATA / 'inbox' / f'noon_{DATE}.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['date', 'code', 'name', 'close_unadjusted',
                                          'return_pct', 'amount_yuan',
                                          'volume_shares', 'turnover_pct'])
        w.writeheader()
        w.writerows(recs)
    (RAW / 'excluded.csv').write_text(
        'code,name,reason\n' + '\n'.join(f'{c},"{n}",{r}' for c, n, r in excluded))

    A = sum(1 for r in recs if float(r['return_pct']) > 0)
    D = sum(1 for r in recs if float(r['return_pct']) < 0)
    U = len(recs) - A - D
    Ep = sum(float(r['amount_yuan']) for r in recs if float(r['return_pct']) > 0)
    En = sum(float(r['amount_yuan']) for r in recs if float(r['return_pct']) < 0)
    print(f'[4/4] 写入 {out}')
    print(f'  样本 {len(recs)}（池 {len(codes)}，剔除 {len(excluded)}）'
          f' A/D/U={A}/{D}/{U}  上/下额 {Ep/1e8:.1f}/{En/1e8:.1f} 亿')
    print(f'  p={100*A/(A+D):.4f}%  q={100*Ep/(Ep+En):.4f}%  '
          f'G={100*Ep/(Ep+En)-100*A/(A+D):+.4f}pp  TRIN={(A/D)/(Ep/En):.4f}')
    if warn:
        print(f'  涨跌链条差异 {len(warn)} 只（>0.021元）：{warn[:8]}')
    print('  剔除样例:', excluded[:6])


if __name__ == '__main__':
    main()
