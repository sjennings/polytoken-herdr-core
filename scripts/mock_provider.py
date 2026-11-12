#!/usr/bin/env python3
"""Local mock provider for isolated integration probes; never calls a real provider."""
# pattern: Imperative Shell
import json
from http.server import BaseHTTPRequestHandler


class Provider(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.reply({"object": "list", "data": [{"id": "local-probe", "object": "model", "owned_by": "local"}]})

    def reply(self, value):
        data = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        print("provider POST", self.path, "stream=", payload.get("stream"), flush=True)
        chunk = {"id": "probe", "object": "chat.completion.chunk", "created": 1,
                 "model": "local-probe", "choices": [{"index": 0,
                 "delta": {"role": "assistant", "tool_calls": [{"index": 0,
                     "id": "probe-completion", "type": "function", "function": {
                         "name": "exec_structured_output",
                         "arguments": json.dumps({"output": "OK"})}}]},
                 "finish_reason": "tool_calls"}]}
        tools = [tool.get("function", {}).get("name") for tool in payload.get("tools", [])]
        if "exec_structured_output" not in tools:
            chunk["choices"][0].update(delta={"role": "assistant", "content": "OK"}, finish_reason="stop")
        if getattr(self.server, "ask_question", False):
            self.server.ask_question = False
            arguments = {"questions": [{"id": "probe", "context": "Isolated test. You may leave this question pending and detach the hc viewer with Ctrl+\\, or submit an answer to receive OK. Empty submission does not dismiss the question.",
                                       "question": "Test human input", "mode": "text", "allow_free_text": True}]}
            chunk["choices"][0].update(delta={"role": "assistant", "tool_calls": [{"index": 0,
                "id": "probe-question", "type": "function", "function": {"name": "ask_user_question",
                "arguments": json.dumps(arguments)}}]}, finish_reason="tool_calls")
        data = ("data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
