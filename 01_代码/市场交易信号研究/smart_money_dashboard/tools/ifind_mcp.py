"""iFinD MCP 直连客户端：把全市场逐股午盘快照写到本地 CSV。

来源：本地 ~/.workbuddy/mcp.json 中已配置的 hexin-ifind-ds-stock-mcp 端点，
方法与 2026-11-17 的 noon_jobs 一致（stock_highfreq_quotes，10 只/批，interval=60），
区别是数据不再经对话上下文，而是直接落盘。
"""
import csv, json, os, sys, time
from pathlib import Path

import requests

CFG = json.load(open(os.path.expanduser('~/.workbuddy/mcp.json')))
SRV = CFG['mcpServers']['hexin-ifind-ds-stock-mcp']
URL = SRV['url']
HDR = dict(SRV['headers'])
HDR.update({'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream'})

S = requests.Session()
S.headers.update(HDR)
SID = None


def _post(payload, timeout=90):
    global SID
    h = dict(S.headers)
    if SID:
        h['mcp-session-id'] = SID
    r = S.post(URL, json=payload, headers=h, timeout=timeout)
    if 'mcp-session-id' in r.headers:
        SID = r.headers['mcp-session-id']
    if r.status_code >= 400:
        raise RuntimeError(f'HTTP {r.status_code}: {r.text[:400]}')
    text = r.text.strip()
    if not text:
        return None
    # streamable http 可能返回 SSE
    if text.startswith('event:') or text.startswith('data:'):
        for line in text.splitlines():
            if line.startswith('data:'):
                return json.loads(line[5:].strip())
        raise RuntimeError('SSE 无 data 行: ' + text[:300])
    return json.loads(text)


def handshake():
    global SID
    SID = None
    r = _post({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
               'params': {'protocolVersion': '2024-11-05', 'capabilities': {},
                          'clientInfo': {'name': 'smd-noon', 'version': '1.0'}}})
    assert r and 'result' in r, r
    _post({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    return r['result']


def call(tool, args, timeout=90):
    r = _post({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
               'params': {'name': tool, 'arguments': args}}, timeout=timeout)
    try:
        import mcp_ledger
        mcp_ledger.log('hexin-ifind-ds-stock-mcp', tool)
    except Exception:
        pass
    if not r or 'result' in r and r['result'].get('isError'):
        raise RuntimeError('tool error: ' + json.dumps(r, ensure_ascii=False)[:500])
    content = r['result']['content'][0]
    txt = content['text'] if isinstance(content, dict) else content
    return json.loads(txt)


if __name__ == '__main__':
    print(json.dumps(handshake(), ensure_ascii=False)[:300])
    d = call('stock_highfreq_quotes',
             {'symbols': '000001.SZ,000002.SZ,600519.SH',
              'indicators': '收盘价,成交量,成交额,涨跌,换手率',
              'data_mode': 'highfreq', 'interval': 60})
    print(json.dumps(d, ensure_ascii=False)[:800])
