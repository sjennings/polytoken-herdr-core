"""Private local transport; only this process writes fixed OSC status reports."""
import hmac
import json
import os
from pathlib import Path
import secrets
import socket
import socketserver
import threading

from .status import Status

LIMIT = 8192
FIELDS = ("session", "event", "prompt_id", "interrogative_id")


def report(path, token, message):
    """Best-effort status observation, never an authorization decision."""
    try:
        payload = {key: message[key] for key in FIELDS if key in message}
        data = json.dumps({"token": token, "message": payload}).encode() + b"\n"
        if len(data) > LIMIT:
            return False
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(0.5)
            client.connect(str(path))
            client.sendall(data)
            return client.recv(16) == b"ok\n"
    except (OSError, ValueError, TypeError):
        return False


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(0.5)
        accepted = False
        try:
            raw = self.rfile.readline(LIMIT + 1)
            if len(raw) <= LIMIT and raw.endswith(b"\n"):
                data = json.loads(raw)
                if isinstance(data, dict) and isinstance(data.get("token"), str):
                    if hmac.compare_digest(data["token"], self.server.owner.token):
                        owner = self.server.owner
                        state = owner.status.apply(data.get("message"))
                        if state is not None:
                            owner.output.write(f"\x1b]7501;state={state}:app=polytoken\x1b\\".encode())
                            owner.output.flush()
                            accepted = True
        except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
            pass
        try:
            self.wfile.write(b"ok\n" if accepted else b"no\n")
        except OSError:
            pass


class RelayServer(socketserver.UnixStreamServer):
    request_queue_size = 64


class Relay:
    def __init__(self, path, output, clear_on_exit=False):
        self.clear_on_exit = clear_on_exit
        self.path = Path(path)
        self.output = output
        self.token = secrets.token_hex(32)
        self.status = Status()

    def __enter__(self):
        # Caller must create the containing directory privately. Refuse unsafe roots.
        parent = self.path.parent.stat()
        if parent.st_uid != os.getuid() or parent.st_mode & 0o077:
            raise ValueError("Relay directory must be owned by this user and mode 0700")
        self.server = RelayServer(str(self.path), Handler)
        self.server.owner = self
        os.chmod(self.path, 0o600)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.path.unlink(missing_ok=True)
        if self.clear_on_exit:
            try:
                self.output.write(b"\x1b]7501;state=clear\x1b\\")
                self.output.flush()
            except OSError:
                pass  # The hc terminal may already have hung up.
