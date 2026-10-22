"""Deploy contract: env-only config, demo mode with no keys, /healthz, a non-root image with no secrets or raw pages."""
import json
import re

from owin import config, server
from owin.datause import observations, pack

ROOT = config.ROOT


def test_healthz_reports_mode_and_never_a_key(monkeypatch):
    monkeypatch.delenv("TOKEN_FACTORY_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    code, ctype, body = server.handle("/healthz", {})
    h = json.loads(body)
    assert code == 200 and h["ok"] is True and h["mode"] == "demo"
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-SECRET-VALUE")
    body = server.handle("/healthz", {})[2]
    assert json.loads(body)["mode"] == "live" and "SECRET" not in body


def test_every_judge_route_works_with_no_keys(monkeypatch):
    for k in ("TOKEN_FACTORY_API_KEY", "TAVILY_API_KEY", "OWIN_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OWIN_ENV_FILE", "/nonexistent")
    for path in ("/", "/judge", "/api/selective", "/api/pack", "/pack/print", "/api/catalog", "/api/watch", "/healthz"):
        assert server.handle(path, {})[0] == 200, path


def test_state_dir_takes_writes_and_falls_back_to_committed(tmp_path, monkeypatch):
    committed = (ROOT / "data/datause/observations.json").read_bytes()
    monkeypatch.setenv("OWIN_STATE_DIR", str(tmp_path))
    assert config.read_path("data/datause/observations.json") == ROOT / "data/datause/observations.json"
    before = pack.brief(pack.build())
    observations.record()  # no network: re-records from the captures on disk, into the state dir
    assert (tmp_path / "data/datause/observations.json").exists()
    assert (ROOT / "data/datause/observations.json").read_bytes() == committed
    assert config.read_path("data/datause/observations.json") == tmp_path / "data/datause/observations.json"
    assert pack.brief(pack.build())["badges"] == before["badges"]


def test_dockerfile_is_non_root_env_only_and_binds_port():
    df = (ROOT / "Dockerfile").read_text()
    assert re.search(r"^USER owin$", df, re.M) and "useradd" in df
    assert "python:3.12-slim" in df and "poetry install --only main" in df
    assert '${PORT:-8080}' in df and "0.0.0.0" in df and "/healthz" in df
    for k in ("TOKEN_FACTORY_API_KEY", "TAVILY_API_KEY"):
        assert not re.search(rf"^(ENV|ARG).*{k}", df, re.M), k
    ign = (ROOT / ".dockerignore").read_text().splitlines()
    assert ign[ign.index("*")] == "*"  # allowlist
    assert "fixtures/raw" in ign and "**/.env" in ign and "!tests/" not in ign
    assert not any(l.startswith("!fixtures/raw") or l.startswith("!.env") for l in ign)


def test_smoke_script_covers_the_judge_routes():
    sh = (ROOT / "scripts/smoke.sh").read_text()
    for path in ("/healthz", "/", "/judge", "/api/selective", "/api/pack", "/pack/print"):
        assert f"check {path} " in sh
    assert "url_effective" in sh and "login" in sh
