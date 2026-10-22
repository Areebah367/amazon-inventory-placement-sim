"""Dependency-free local reference API. Run: python3 server.py"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from inventory_model import default_scenario, solve, simulate

INDEX_HTML = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Forward Inventory API</title>
<style>
  :root { color-scheme: light dark; --bg: #fff; --fg: #1a1a1a; --muted: #666; --line: #e3e3e3; --ok: #1a7f37; }
  @media (prefers-color-scheme: dark) { :root { --bg: #111; --fg: #eee; --muted: #999; --line: #2a2a2a; --ok: #3fb950; } }
  body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, sans-serif; }
  main { max-width: 720px; margin: 0 auto; padding: 48px 16px; }
  h1 { font-size: 1.5rem; margin: 0 0 8px; }
  .status { color: var(--ok); font-weight: 600; }
  p { color: var(--muted); }
  table { width: 100%; border-collapse: collapse; margin-top: 24px; }
  th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { font-size: .85rem; color: var(--muted); font-weight: 500; }
  code { font: .9rem ui-monospace, monospace; white-space: nowrap; }
</style>
</head>
<body>
<main>
  <h1>Forward &mdash; UAE Inventory API</h1>
  <div class="status">&#9679; API is up</div>
  <p>Allocation and Monte Carlo simulation model. All inputs are illustrative; no Amazon systems are connected.</p>
  <table>
    <tr><th>Endpoint</th><th>Request</th><th>Response</th></tr>
    <tr><td><code><a href="/health">GET /health</a></code></td><td>none</td><td>Health status</td></tr>
    <tr><td><code><a href="/api/defaults">GET /api/defaults</a></code></td><td>none</td><td>Editable illustrative scenario</td></tr>
    <tr><td><code>POST /api/allocate</code></td><td>Scenario JSON</td><td>Site recommendations, baseline, cost and feasibility</td></tr>
    <tr><td><code>POST /api/simulate</code></td><td><code>{"scenario": {...}, "n": 1000}</code></td><td>Coverage mean and 5th&ndash;95th percentile range</td></tr>
  </table>
</main>
</body>
</html>
'''


class Handler(BaseHTTPRequestHandler):
    def reply_html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def reply(self, code, value):
        body = json.dumps(value, allow_nan=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/':
            self.reply_html(INDEX_HTML)
        elif self.path == '/health':
            self.reply(200, {'status': 'ok'})
        elif self.path == '/api/defaults':
            self.reply(200, default_scenario())
        else:
            self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        if self.path not in ('/api/allocate', '/api/simulate'):
            return self.reply(404, {'error': 'Not found'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 1_000_000:
                return self.reply(413, {'error': 'Provide a JSON body of up to 1 MB.'})
            def reject_constant(value):
                raise ValueError(f'Invalid JSON number: {value}')
            payload = json.loads(self.rfile.read(size), parse_constant=reject_constant)
            if self.path == '/api/allocate':
                result = solve(payload)
                self.reply(200 if result['feasible'] else 422, result)
            else:
                if not isinstance(payload, dict) or 'scenario' not in payload:
                    raise ValueError('Simulation expects {"scenario": ..., "n": 1000}.')
                self.reply(200, simulate(payload['scenario'], payload.get('n', 1000)))
        except (ValueError, TypeError, UnicodeDecodeError, OverflowError) as error:
            self.reply(400, {'error': str(error)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    print(f'Forward reference API: http://{args.host}:{args.port}', flush=True)
    HTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
