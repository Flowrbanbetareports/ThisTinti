from __future__ import annotations

import struct
from pathlib import Path

from scripts.clamd_client_scan import main, scan_path


class FakeSocket:
    def __init__(self, response: bytes):
        self.response = response
        self.sent = bytearray()
        self.timeout = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def settimeout(self, timeout):
        self.timeout = timeout

    def sendall(self, payload: bytes):
        self.sent.extend(payload)

    def recv(self, _size: int) -> bytes:
        response, self.response = self.response, b""
        return response


def test_clamd_stream_protocol(monkeypatch, tmp_path: Path):
    sample = tmp_path / "sample.txt"
    sample.write_bytes(b"safe payload")
    fake = FakeSocket(b"stream: OK\0")
    monkeypatch.setattr("socket.create_connection", lambda *_args, **_kwargs: fake)
    response = scan_path(sample, host="clamav", port=3310, timeout=2, chunk_size=4)
    assert response == "stream: OK"
    assert fake.sent.startswith(b"zINSTREAM\0")
    assert fake.sent.endswith(struct.pack("!I", 0))
    assert b"safe" in fake.sent


def test_clamd_cli_maps_found_to_exit_one(monkeypatch, tmp_path: Path):
    sample = tmp_path / "sample.txt"
    sample.write_text("payload", encoding="utf-8")
    monkeypatch.setattr(
        "scripts.clamd_client_scan.scan_path",
        lambda *_args, **_kwargs: "stream: Eicar-Test-Signature FOUND",
    )
    assert main(["--no-summary", str(sample)]) == 1
