"""Serveur HTTP minimal pour prototype UI Narratech.

Fonctionnalités:
- sert l'UI statique (assets/ui_prototype/index.html)
- proxy local vers API backend (mode API)
- fallback historique JSONL local (mode fichier)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "assets" / "ui_prototype"
EXCHANGE_DIR = ROOT / "outputs" / "ui_exchange"
GENERATION_FILE = EXCHANGE_DIR / "generation_requests.jsonl"
FEEDBACK_FILE = EXCHANGE_DIR / "post_watch_feedback.jsonl"

API_MODE = os.getenv("NARRATECH_UI_API_MODE", "0") == "1"
API_BASE_URL = os.getenv("NARRATECH_API_BASE_URL", "http://127.0.0.1:8000")


class UIRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/projects/") and API_MODE:
            self._proxy_api_get(self.path.removeprefix("/api"))
            return
        if self.path in {"/", "/index.html"}:
            self.path = "/assets/ui_prototype/index.html"
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/generation-request":
            if API_MODE:
                self._proxy_generation_request()
            else:
                self._write_record(GENERATION_FILE, kind="generation_request")
            return
        if self.path == "/api/feedback":
            self._write_record(FEEDBACK_FILE, kind="feedback")
            return
        if self.path.startswith("/api/projects/") and self.path.endswith("/replay") and API_MODE:
            self._proxy_api_post(self.path.removeprefix("/api"))
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint non supporté")

    def _proxy_generation_request(self) -> None:
        try:
            payload = self._read_json_payload()
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        target = f"{API_BASE_URL}/v1/generations"
        req = urllib.request.Request(
            target,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            self._send_json(HTTPStatus.OK, {"ok": True, **body, "backend": target})
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8")
            self._send_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": detail})
        except urllib.error.URLError as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(exc.reason)})

    def _proxy_api_get(self, api_path: str) -> None:
        target = f"{API_BASE_URL}{api_path}"
        try:
            with urllib.request.urlopen(target, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            self._send_json(HTTPStatus.OK, body)
        except urllib.error.HTTPError as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": exc.read().decode("utf-8")})

    def _proxy_api_post(self, api_path: str) -> None:
        target = f"{API_BASE_URL}{api_path}"
        req = urllib.request.Request(target, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            self._send_json(HTTPStatus.OK, body)
        except urllib.error.HTTPError as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": exc.read().decode("utf-8")})

    def _read_json_payload(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_payload = self.rfile.read(content_length) if content_length else b"{}"
        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("Corps JSON invalide") from None
        if not isinstance(payload, dict):
            raise ValueError("Le payload doit être un objet JSON")
        return payload

    def _write_record(self, target_file: Path, *, kind: str) -> None:
        try:
            payload = self._read_json_payload()
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        EXCHANGE_DIR.mkdir(parents=True, exist_ok=True)
        record_id = uuid4().hex
        record = {
            "record_id": record_id,
            "event": kind,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        with target_file.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._send_json(HTTPStatus.OK, {"ok": True, "record_id": record_id, "exchange_file": str(target_file.relative_to(ROOT))})

    def _send_json(self, status: HTTPStatus, body: dict[str, Any]) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    if not UI_DIR.exists():
        raise FileNotFoundError(f"UI introuvable: {UI_DIR}")
    server = ThreadingHTTPServer((host, port), UIRequestHandler)
    print(f"UI prototype disponible sur http://{host}:{port}")
    print(f"Mode API: {'ON' if API_MODE else 'OFF'} (base={API_BASE_URL})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
