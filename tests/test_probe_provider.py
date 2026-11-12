import json
from pathlib import Path
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mock_provider import Provider


class ProviderTests(unittest.TestCase):
    def test_answered_question_does_not_request_another_question(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
        server.ask_question = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def request(messages):
                body = json.dumps({'stream': True, 'messages': messages}).encode()
                req = Request(f'http://127.0.0.1:{server.server_port}/v1/chat/completions',
                              data=body, headers={'Content-Type': 'application/json'})
                with urlopen(req, timeout=3) as response:
                    line = response.read().decode().splitlines()[0]
                return json.loads(line.removeprefix('data: '))['choices'][0]

            first = request([{'role': 'user', 'content': 'Ask the test question'}])
            self.assertEqual(first['delta']['tool_calls'][0]['function']['name'], 'ask_user_question')
            second = request([{'role': 'tool', 'tool_call_id': 'probe-question', 'content': 'answered'}])
            self.assertEqual(second['finish_reason'], 'stop')
            self.assertEqual(second['delta']['content'], 'OK')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
