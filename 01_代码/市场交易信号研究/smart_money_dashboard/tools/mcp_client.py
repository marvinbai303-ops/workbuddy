"""通用 MCP 直连客户端（streamable HTTP），按 mcp.json 里的服务名取配置。

用法：
    python3 tools/mcp_client.py <server_name> list
    python3 tools/mcp_client.py <server_name> call <tool> '<json args>'
"""
import json
import os
import sys

import requests

CFG = json.load(open(os.path.expanduser('~/.workbuddy/mcp.json')))


class Client:
    def __init__(self, server):
        self.server = server
        srv = CFG['mcpServers'][server]
        self.url = srv['url']
        self.hdr = dict(srv.get('headers') or {})
        self.hdr.update({'Content-Type': 'application/json',
                         'Accept': 'application/json, text/event-stream'})
        self.s = requests.Session()
        self.s.headers.update(self.hdr)
        self.sid = None
        self.n = 0
        self.handshake()

    def _post(self, payload, timeout=90):
        h = dict(self.s.headers)
        if self.sid:
            h['mcp-session-id'] = self.sid
        r = self.s.post(self.url, json=payload, headers=h, timeout=timeout)
        if 'mcp-session-id' in r.headers:
            self.sid = r.headers['mcp-session-id']
        if r.status_code >= 400:
            raise RuntimeError(f'HTTP {r.status_code}: {r.text[:400]}')
        text = r.text.strip()
        if not text:
            return None
        if text.startswith('event:') or text.startswith('data:'):
            for line in text.splitlines():
                if line.startswith('data:'):
                    return json.loads(line[5:].strip())
            raise RuntimeError('SSE 无 data 行: ' + text[:300])
        return json.loads(text)

    def handshake(self):
        self.sid = None
        self.n += 1
        r = self._post({'jsonrpc': '2.0', 'id': self.n, 'method': 'initialize',
                        'params': {'protocolVersion': '2024-11-05', 'capabilities': {},
                                   'clientInfo': {'name': 'smd', 'version': '1.0'}}})
        assert r and 'result' in r, r
        self._post({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        return r['result']

    def list_tools(self):
        self.n += 1
        r = self._post({'jsonrpc': '2.0', 'id': self.n, 'method': 'tools/list', 'params': {}})
        return r['result']['tools']

    def call(self, tool, args, timeout=90):
        self.n += 1
        r = self._post({'jsonrpc': '2.0', 'id': self.n, 'method': 'tools/call',
                        'params': {'name': tool, 'arguments': args}}, timeout=timeout)
        if not r or ('result' in r and r['result'].get('isError')):
            raise RuntimeError('tool error: ' + json.dumps(r, ensure_ascii=False)[:500])
        try:
            import mcp_ledger
            mcp_ledger.log(self.server, tool)
        except Exception:
            pass
        content = r['result']['content'][0]
        txt = content['text'] if isinstance(content, dict) else content
        try:
            return json.loads(txt)
        except Exception:
            return {'text': txt}


if __name__ == '__main__':
    srv, cmd = sys.argv[1], sys.argv[2]
    c = Client(srv)
    if cmd == 'list':
        for t in c.list_tools():
            print('-', t['name'], '|', (t.get('description') or '')[:110].replace('\n', ' '))
    else:
        tool = sys.argv[3]
        args = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
        print(json.dumps(c.call(tool, args), ensure_ascii=False)[:3000])
