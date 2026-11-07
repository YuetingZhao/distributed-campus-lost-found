"""Dependency-free tests for the distributed core.

Execute from repository root: python -m unittest discover -s tests -v
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from campus.core import Store, ProjectError, dominates, heads_of, increment, merge_clocks


class PeerServer:
    """A tiny HTTP relay used only to test the real HTTP sync transport.

    Production uses Flask's /api/replicate endpoint with the same wire format.
    """
    def __init__(self, store):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != '/api/replicate':
                    self.send_error(404)
                    return
                if not store.network_connected():
                    payload, status = {'error': 'partitioned'}, 503
                else:
                    length = int(self.headers.get('Content-Length', '0'))
                    body = json.loads(self.rfile.read(length))
                    inserted = store.import_versions(body['versions'])
                    payload, status = {'inserted': inserted, 'versions': store.export_versions()}, 200
                raw = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.a = Store(str(Path(self.tmp.name) / 'a.sqlite3'), 'cesena', 'Cesena')
        self.b = Store(str(Path(self.tmp.name) / 'b.sqlite3'), 'forli', 'Forli')
        self.peer = PeerServer(self.b)

    def tearDown(self):
        self.peer.close()
        self.tmp.cleanup()

    def add(self, store=None, kind='LOST', title='Black MacBook charger', category='electronics'):
        return (store or self.a).create({'kind':kind, 'title':title, 'description':'At library', 'category':category})

    def test_vector_clocks(self):
        self.assertTrue(dominates({'a':2}, {'a':1}))
        self.assertTrue(dominates({'a':2,'b':1}, {'a':2}))
        self.assertFalse(dominates({'a':2}, {'a':1,'b':1}))
        self.assertFalse(dominates({'a':2}, {'a':2}))
        self.assertEqual(increment({'a':3}, 'b'), {'a':3,'b':1})
        self.assertEqual(merge_clocks([{'a':3},{'b':2,'a':1}]), {'a':3,'b':2})

    def test_local_crud_and_validation(self):
        report = self.add()
        self.assertEqual(report['status'], 'OPEN')
        self.assertEqual(report['campus'], 'Cesena')
        self.assertFalse(report['conflict'])
        self.assertEqual(report['vector_clock'], {'cesena':1})
        edited = self.a.edit(report['id'], {'status':'RESOLVED', 'description':'Found later'})
        self.assertEqual(edited['status'], 'RESOLVED')
        self.assertEqual(edited['vector_clock'], {'cesena':2})
        self.assertEqual(self.a.version_count(), 2)
        with self.assertRaises(ProjectError):
            self.a.create({'kind':'INVALID', 'title':'x'})
        with self.assertRaises(ProjectError):
            self.a.edit(report['id'], {'campus':'malicious'})
        with self.assertRaises(ProjectError):
            self.a.report('missing')
        with self.assertRaises(ProjectError):
            self.a.resolve(report['id'], 'not-a-version')

    def test_peer_replicates_both_directions_and_is_idempotent(self):
        report_a = self.add()
        report_b = self.add(self.b, 'FOUND', 'MacBook charger')
        first = self.a.sync(self.peer.url)
        self.assertEqual(first['new_local_versions'], 1)
        self.assertEqual(self.a.report(report_b['id'])['title'], 'MacBook charger')
        self.assertEqual(self.b.report(report_a['id'])['title'], 'Black MacBook charger')
        self.assertEqual(self.a.version_count(), 2)
        second = self.a.sync(self.peer.url)
        self.assertEqual(second['new_local_versions'], 0)
        self.assertEqual(self.a.export_versions(), self.b.export_versions())

    def test_disconnection_conflict_resolution_convergence(self):
        item = self.add()
        self.a.sync(self.peer.url)
        self.a.set_network(False)
        self.b.set_network(False)
        with self.assertRaises(ProjectError) as err:
            self.a.sync(self.peer.url)
        self.assertEqual(err.exception.status, 503)
        self.assertTrue(self.a.edit(item['id'], {'description':'Change at Cesena'}))
        self.b.edit(item['id'], {'description':'Change at Forli'})
        b_found = self.add(self.b, 'FOUND', 'MacBook charger')
        self.assertEqual(self.a.report(item['id'])['description'], 'Change at Cesena')
        self.assertEqual(self.b.report(item['id'])['description'], 'Change at Forli')
        self.a.set_network(True)
        with self.assertRaises(ProjectError) as err:
            self.a.sync(self.peer.url)
        self.assertEqual(err.exception.status, 503)
        self.b.set_network(True)
        self.a.sync(self.peer.url)
        conflicted_a = self.a.report(item['id'])
        conflicted_b = self.b.report(item['id'])
        self.assertTrue(conflicted_a['conflict'])
        self.assertEqual(len(conflicted_a['candidates']), 2)
        self.assertTrue(conflicted_b['conflict'])
        self.assertEqual(self.a.report(b_found['id'])['kind'], 'FOUND')
        with self.assertRaises(ProjectError) as err:
            self.a.edit(item['id'], {'status':'RESOLVED'})
        self.assertEqual(err.exception.status, 409)
        winner = next(c for c in conflicted_a['candidates'] if c['data']['description'] == 'Change at Cesena')
        resolution = self.a.resolve(item['id'], winner['version_id'])
        self.assertFalse(resolution['conflict'])
        self.assertEqual(resolution['description'], 'Change at Cesena')
        self.assertEqual(resolution['vector_clock'], {'cesena':3, 'forli':1})
        self.a.sync(self.peer.url)
        self.assertEqual(self.a.report(item['id']), self.b.report(item['id']))
        self.assertFalse(self.b.report(item['id'])['conflict'])
        self.assertEqual(len(self.a.possible_matches()), 1)
        self.assertEqual(self.a.version_count(), self.b.version_count())
        count = self.a.version_count()
        self.a.sync(self.peer.url)
        self.assertEqual(self.a.version_count(), count)

    def test_conflicts_are_different_from_possible_matches(self):
        lost = self.add()
        found = self.add(self.b, 'FOUND', 'MacBook charger')
        self.a.sync(self.peer.url)
        self.assertEqual(len(self.a.possible_matches()), 1)
        self.assertFalse(self.a.report(lost['id'])['conflict'])
        self.assertFalse(self.a.report(found['id'])['conflict'])
        self.a.edit(lost['id'], {'status':'RESOLVED'})
        self.assertEqual(len(self.a.possible_matches()), 0)

    def test_replication_rejects_invalid_versions_atomically(self):
        good = self.add()
        raw = self.a.export_versions()[0]
        invalid = json.loads(json.dumps(raw))
        invalid['version_id'] = 'evil'
        invalid['clock'] = {'cesena': -2}
        with self.assertRaises(ProjectError):
            self.b.import_versions([raw, invalid])
        self.assertEqual(self.b.version_count(), 0)

    def test_persistence_survives_store_reopening(self):
        item = self.add()
        again = Store(self.a.db_path, 'cesena', 'Cesena')
        self.assertEqual(again.report(item['id'])['title'], item['title'])
        again.set_network(False)
        self.assertFalse(Store(self.a.db_path, 'cesena', 'Cesena').network_connected())


if __name__ == '__main__':
    unittest.main()
