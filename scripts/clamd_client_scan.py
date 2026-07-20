#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import socket
import struct
import sys
from pathlib import Path


class ClamdError(RuntimeError):
    pass


def scan_path(path: Path, *, host: str, port: int, timeout: float, chunk_size: int = 1024 * 1024) -> str:
    if not path.is_file():
        raise ClamdError(f"file not found: {path}")
    with socket.create_connection((host, port), timeout=timeout) as connection:
        connection.settimeout(timeout)
        connection.sendall(b"zINSTREAM\0")
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                connection.sendall(struct.pack("!I", len(chunk)))
                connection.sendall(chunk)
        connection.sendall(struct.pack("!I", 0))
        response = bytearray()
        while len(response) < 8192:
            part = connection.recv(4096)
            if not part:
                break
            response.extend(part)
            if b"\0" in part or b"\n" in part:
                break
    text = bytes(response).replace(b"\0", b"").decode("utf-8", errors="replace").strip()
    if not text:
        raise ClamdError("empty response from ClamAV daemon")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan one file through a ClamAV clamd TCP daemon")
    parser.add_argument("--no-summary", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    host = os.getenv("THISTINTI_CLAMD_HOST", "clamav")
    port = int(os.getenv("THISTINTI_CLAMD_PORT", "3310"))
    timeout = float(os.getenv("THISTINTI_CLAMD_TIMEOUT_SECONDS", "60"))
    try:
        response = scan_path(args.path, host=host, port=port, timeout=timeout)
    except (OSError, ValueError, ClamdError) as exc:
        print(f"ClamAV ERROR: {exc}", file=sys.stderr)
        return 2
    print(response)
    if "FOUND" in response:
        return 1
    if response.endswith("OK"):
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
