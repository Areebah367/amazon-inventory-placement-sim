import itertools
import json
from pathlib import Path
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import HTTPServer
from inventory_model import default_scenario, solve, simulate, validate
from server import Handler


class ModelTests(unittest.TestCase):
    def compare(self, a, b):
        if isinstance(a, dict):
            self.assertEqual(a.keys(), b.keys())
            for k in a:
                self.compare(a[k], b[k])
        elif isinstance(a, list):
            self.assertEqual(len(a), len(b))
            for x, y in zip(a, b):
                self.compare(x, y)
        elif type(a) in (int, float) and type(b) in (int, float):
            self.assertAlmostEqual(a, b, places=9)
        else:
            self.assertEqual(a, b)

    def test_website_parity(self):
        cases = json.loads((Path(__file__).parent / 'website_reference.json').read_text())
        for case in cases:
            with self.subTest(case=case['name']):
                self.compare(solve(case['scenario']), case['result'])
                if case['simulation']:
                    self.compare(simulate(case['scenario']), case['simulation'])

    def test_default_totals(self):
        r = solve(default_scenario())
        self.assertEqual(r['totals']['demand'], 9850)
        self.assertEqual(r['totals']['stock'], 7545)
        self.assertEqual(r['totals']['baseline'], 5116)

    def test_floor_and_constraints(self):
        s = default_scenario()
        s['floor'] = .2
        r = solve(s)
        self.assertTrue(r['feasible'])
        for site in r['sites']:
            self.assertLessEqual(site['used'], site['cap'] + 1e-9)
            self.assertLessEqual(site['units'], site['limit'])
            for q, d in zip(site['q'], site['d']):
                self.assertGreaterEqual(q, d * .2)
                self.assertLessEqual(q, d)

    def test_invalid_and_malformed(self):
        for key, value in [('cv', float('nan')), ('floor', 2), ('multiplier', True)]:
            s = default_scenario()
            s[key] = value
            with self.assertRaises(ValueError):
                validate(s)
        for change in [lambda s: s['sites'].__setitem__(0, []), lambda s: s['categories'][0].__setitem__(1, 0)]:
            s = default_scenario()
            change(s)
            with self.assertRaises(ValueError):
                solve(s)

    def test_small_exhaustive_optimum(self):
        for cap in (.001, .003, .006):
            s = default_scenario()
            s['demand'] = [[0] * 7 for _ in range(8)]
            for i in range(3):
                s['demand'][i][0] = 3
            s['sites'][0][1] = cap
            s['sites'][0][3] = 5
            vols = [s['categories'][i][1] / 1000 for i in range(3)]
            best = max(sum(q) for q in itertools.product(range(4), repeat=3)
                       if sum(q) <= 5 and sum(x * v for x, v in zip(q, vols)) <= cap + 1e-10)
            self.assertEqual(solve(s)['sites'][0]['units'], best)

    def test_simulation_validation(self):
        s = default_scenario()
        self.assertEqual(simulate(s, 10), simulate(s, 10))
        for n in (0, 10001, True, 1.5):
            with self.assertRaises(ValueError):
                simulate(s, n)
        s['floor'] = 1
        with self.assertRaises(ValueError):
            simulate(s)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, body=None):
        request = Request(self.url + path, data=json.dumps(body).encode() if body is not None else None,
                          headers={'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_endpoints(self):
        self.assertEqual(self.request('/health'), (200, {'status': 'ok'}))
        code, s = self.request('/api/defaults')
        self.assertEqual(code, 200)
        code, r = self.request('/api/allocate', s)
        self.assertEqual((code, r['totals']['stock']), (200, 7545))
        code, r = self.request('/api/simulate', {'scenario': s, 'n': 10})
        self.assertEqual((code, r['n']), (200, 10))
        s['floor'] = 1
        code, r = self.request('/api/allocate', s)
        self.assertEqual((code, r['feasible']), (422, False))
        self.assertEqual(self.request('/api/allocate', {})[0], 400)
        self.assertEqual(self.request('/missing')[0], 404)
        self.assertEqual(self.request('/api/simulate', [])[0], 400)

    def test_index_page(self):
        with urlopen(self.url + '/', timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertIn('text/html', response.headers['Content-Type'])
            page = response.read().decode()
        for endpoint in ('/health', '/api/defaults', '/api/allocate', '/api/simulate'):
            self.assertIn(endpoint, page)
