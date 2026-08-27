from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import container_entrypoint
from scripts.container_entrypoint import prepare_writable_directories, stage_secret_files


def test_stage_secret_files_rewrites_only_existing_thistinti_file_variables(tmp_path: Path, monkeypatch):
    source = tmp_path / "source-secret"
    source.write_text("sensitive-value\n", encoding="utf-8")
    monkeypatch.setenv("THISTINTI_SECRET_KEY_FILE", str(source))
    monkeypatch.setenv("THISTINTI_MISSING_FILE", str(tmp_path / "missing"))
    monkeypatch.setenv("OTHER_SECRET_FILE", str(source))

    target_root = tmp_path / "staged"
    rewritten = stage_secret_files(target_root, uid=os.getuid(), gid=os.getgid())

    assert set(rewritten) == {"THISTINTI_SECRET_KEY_FILE"}
    staged = Path(rewritten["THISTINTI_SECRET_KEY_FILE"])
    assert staged.read_text(encoding="utf-8") == "sensitive-value\n"
    assert staged.stat().st_mode & 0o777 == 0o400
    assert target_root.stat().st_mode & 0o777 == 0o700


def test_prepare_writable_directories_rejects_paths_outside_allow_list(tmp_path: Path):
    with pytest.raises(RuntimeError, match="not allow-listed"):
        prepare_writable_directories(str(tmp_path), uid=os.getuid(), gid=os.getgid())


def test_privileged_bootstrap_drops_identity_before_exec(tmp_path: Path, monkeypatch) -> None:
    events: list[str] = []
    account = SimpleNamespace(pw_name="thistinti", pw_uid=1234, pw_gid=1234)

    monkeypatch.setattr(container_entrypoint.os, "geteuid", lambda: 0)
    monkeypatch.setattr(container_entrypoint.pwd, "getpwnam", lambda _name: account)
    monkeypatch.setattr(container_entrypoint.tempfile, "mkdtemp", lambda **_kwargs: str(tmp_path / "secrets"))
    monkeypatch.setattr(container_entrypoint, "stage_secret_files", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(container_entrypoint, "prepare_writable_directories", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(container_entrypoint.os, "initgroups", lambda *_args: events.append("initgroups"))
    monkeypatch.setattr(container_entrypoint.os, "setgid", lambda *_args: events.append("setgid"))
    monkeypatch.setattr(container_entrypoint.os, "setuid", lambda *_args: events.append("setuid"))

    def fake_exec(*_args) -> None:
        events.append("exec")
        raise RuntimeError("exec intercepted")

    monkeypatch.setattr(container_entrypoint.os, "execvpe", fake_exec)

    with pytest.raises(RuntimeError, match="exec intercepted"):
        container_entrypoint.drop_privileges_and_exec(["python", "-V"])

    assert events == ["initgroups", "setgid", "setuid", "exec"]
