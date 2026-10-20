import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from connector import request

class Handler(BaseHTTPRequestHandler):
    def respond(self):
        raw=json.dumps({'contentType':self.headers.get('Content-Type'),'method':self.command}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
    do_GET=respond
    do_POST=respond
    def log_message(self,*args):pass

class TransportTests(unittest.TestCase):
    def test_json_content_type_only_on_requests_with_json_body(self):
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url='http://127.0.0.1:'+str(server.server_port)
            self.assertIsNone(request(url)['contentType'])
            self.assertEqual(request(url,{'test':True})['contentType'],'application/json')
        finally:server.shutdown();server.server_close();thread.join()
