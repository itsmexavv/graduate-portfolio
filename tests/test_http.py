"""Integration tests across the actual HTTP boundary."""
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from run import allowed_addresses, create_server


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        with patch.dict('os.environ', {'CODESPACES':'true', 'CODESPACE_NAME':'demo-space-123', 'GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN':'app.github.dev'}):
            cls.server=create_server(0,cls.temp.name)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self,path,method='GET',data=None,headers=None):
        raw = None if data is None else json.dumps(data).encode()
        req=Request(self.base+path,raw,{'Content-Type':'application/json',**(headers or {})},method=method)
        try:
            response=urlopen(req,timeout=5)
        except HTTPError as exc:
            response=exc
        with response:
            content=response.read()
            parsed=json.loads(content) if response.headers.get('Content-Type','').startswith('application/json') else content
            return response.status,parsed,response.headers

    def test_home_and_static_assets(self):
        for path in ['/','/app.js','/style.css','/icon.svg']:
            status,_,headers=self.request(path)
            self.assertEqual(status,200)
            self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])

    def test_all_five_apis(self):
        for path in ['/api/smartfind/products','/api/attendance/students','/api/peso/summary','/api/accesspath/map']:
            self.assertEqual(self.request(path)[0],200)
        status,result,_=self.request('/api/minilang/run','POST',{'source':'print 2+2;'})
        self.assertEqual((status,result['output']),(201,['4']))

    def test_duplicate_and_bad_input_have_http_errors(self):
        data={'student_id':1,'event_id':1}
        self.assertEqual(self.request('/api/attendance/check-in','POST',data)[0],201)
        self.assertEqual(self.request('/api/attendance/check-in','POST',data)[0],409)
        self.assertEqual(self.request('/api/minilang/run','POST',{'source':'print 1/0;'})[0],422)
        self.assertEqual(self.request('/api/peso/transactions','POST',[])[0],400)

    def test_cross_origin_write_and_foreign_host_rejected(self):
        self.assertEqual(self.request('/api/minilang/run','POST',{'source':'print 1;'}, {'Origin':'https://example.com'})[0],403)
        self.assertEqual(self.request('/',headers={'Host':'evil.example'})[0],403)

    def test_codespace_host_and_origin_support_get_and_write(self):
        host=f'demo-space-123-{self.server.server_port}.app.github.dev'
        self.assertEqual(self.request('/',headers={'Host':host})[0],200)
        status,result,_=self.request('/api/minilang/run','POST',{'source':'print 7;'}, {'Host':host,'Origin':'https://'+host})
        self.assertEqual((status,result['output']),(201,['7']))
        other=f'other-space-{self.server.server_port}.app.github.dev'
        self.assertEqual(self.request('/',headers={'Host':other})[0],403)
        self.assertEqual(self.request('/api/minilang/run','POST',{'source':'print 1;'}, {'Host':host,'Origin':'https://'+other})[0],403)

    def test_codespace_detection_requires_valid_environment(self):
        base={'CODESPACES':'true','CODESPACE_NAME':'demo-space-123','GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN':'app.github.dev'}
        for changes in ({'CODESPACES':'false'}, {'CODESPACE_NAME':'invalid/name'}, {'GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN':'app.github.dev/evil'}):
            hosts,origins=allowed_addresses(8000,{**base,**changes})
            self.assertEqual(hosts,{'localhost:8000','127.0.0.1:8000'})
            self.assertEqual(origins,{'http://localhost:8000','http://127.0.0.1:8000'})

    def test_private_files_and_unknown_routes_not_served(self):
        for path in ['/../run.py','/data/smartfind.db','/api/unknown/x','/missing']:
            self.assertEqual(self.request(path)[0],404)

    def test_csv_export_has_correct_content_type(self):
        status,body,headers=self.request('/api/attendance/export?event_id=1')
        self.assertEqual(status,200)
        self.assertTrue(headers['Content-Type'].startswith('text/csv'))
        self.assertIn(b'student_no,name,course',body)


if __name__=='__main__':
    unittest.main()
