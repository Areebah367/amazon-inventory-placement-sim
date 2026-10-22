"""Dependency-free local reference API. Run: python3 server.py"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from inventory_model import default_scenario, solve, simulate


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, value):
        body = json.dumps(value, allow_nan=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/health':
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
