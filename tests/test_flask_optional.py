"""Flask route tests. Run automatically when Flask is installed."""
import tempfile
from pathlib import Path
import unittest

try:
    from campus.server import create_app
except ModuleNotFoundError:
    create_app = None


@unittest.skipIf(create_app is None, 'Flask not installed in this environment')
class FlaskAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({
            'TESTING': True, 'NODE_ID': 'test', 'CAMPUS':'Test Campus',
            'DB_PATH': str(Path(self.tmp.name) / 'test.db'),
            'PEER_URL': 'http://127.0.0.1:65530'
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_list_modify_and_health(self):
        created = self.client.post('/api/items', json={'kind':'LOST','title':'Red backpack','category':'bags'})
        self.assertEqual(created.status_code, 201)
        item_id = created.json['id']
        self.assertEqual(self.client.get('/api/health').json['node'], 'test')
        self.assertEqual(len(self.client.get('/api/items').json['items']), 1)
        edited = self.client.patch('/api/items/' + item_id, json={'status':'RESOLVED'})
        self.assertEqual(edited.json['status'], 'RESOLVED')
        self.assertEqual(self.client.get('/api/items/' + item_id).json['vector_clock'], {'test':2})
        self.assertEqual(self.client.get('/api/items/missing').status_code, 404)

    def test_partition_blocks_sync_but_not_local_write(self):
        result = self.client.put('/api/admin/network', json={'connected':False})
        self.assertEqual(result.json['connected'], False)
        self.assertEqual(self.client.post('/api/sync').status_code, 503)
        self.assertEqual(self.client.post('/api/replicate', json={'versions':[]}).status_code, 503)
        self.assertEqual(self.client.post('/api/items', json={'kind':'FOUND', 'title':'Keys'}).status_code, 201)
        self.client.put('/api/admin/network', json={'connected':True})
        self.assertEqual(self.client.post('/api/replicate', json={'versions':[]}).status_code, 200)
        self.assertEqual(self.client.post('/api/items', json={'kind':'WRONG','title':'broken'}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
