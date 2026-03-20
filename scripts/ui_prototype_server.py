"""Serveur HTTP minimal pour prototype UI Narratech.

Fonctionnalités:
- sert l'UI statique (assets/ui_prototype/index.html)
- expose une API locale POST /api/generation-request
- expose une API locale POST /api/feedback
- écrit les échanges au format JSONL standardisé dans outputs/ui_exchange/
"""

from __future__ import annotations

import json
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


class UIRequestHandler(SimpleHTTPRequestHandler):
    """Handler HTTP pour UI + API locale."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/index.html"}:
            self.path = "/assets/ui_prototype/index.html"
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/generation-request":
            self._write_record(GENERATION_FILE, kind="generation_request")
            return
        if self.path == "/api/feedback":
            self._write_record(FEEDBACK_FILE, kind="feedback")
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint non supporté")

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
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": str(exc)},
            )
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

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "record_id": record_id,
                "exchange_file": str(target_file.relative_to(ROOT)),
            },
        )

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
    print("Ctrl+C pour arrêter.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
