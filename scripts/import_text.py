from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from personality_jelly.api import create_app
from personality_jelly.application import create_database_resources
from personality_jelly.core import Settings


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    source_path = args.source.resolve()
    if not source_path.is_file():
        print(f"error: source file does not exist: {source_path}", file=sys.stderr)
        return 2

    try:
        content = source_path.read_text(encoding=args.encoding)
    except UnicodeDecodeError as exc:
        print(f"error: cannot decode source as {args.encoding}: {exc}", file=sys.stderr)
        return 2

    database_url = args.database_url or Settings().database_url
    if database_url == "sqlite:///:memory:":
        print(
            "error: this script uses the API adapter and requires a file-backed database; "
            "use sqlite:///tmp/import-text.db instead of sqlite:///:memory:",
            file=sys.stderr,
        )
        return 2
    title = args.title or source_path.stem
    source_type = args.source_type or _source_type_from_path(source_path)
    body = _request_body(
        args=args,
        title=title,
        source_type=source_type,
        content=content,
    )
    idempotency_key = args.idempotency_key or _default_idempotency_key(body)
    request_id = args.request_id or f"req_import_{idempotency_key.rsplit('-', 1)[-1]}"

    resources = create_database_resources(database_url)
    app = create_app(settings=Settings(), database_resources=resources)
    with TestClient(app) as client:
        response = client.post(
            "/source-works",
            headers={
                "X-Request-ID": request_id,
                "Idempotency-Key": idempotency_key,
            },
            json=body,
        )

    payload = _json_response(response)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(
                {"status_code": response.status_code, "body": payload},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    if response.status_code >= 400:
        print(f"status_code={response.status_code}")
        print(f"error_code={payload.get('error', {}).get('code', 'unknown')}")
        print(f"message={payload.get('error', {}).get('message', response.text)}")
        return 1

    result = payload["result"]
    ids = payload["ids"]
    print(f"status_code={response.status_code}")
    print(f"database_url={database_url}")
    print(f"request_id={payload['request_id']}")
    print(f"workflow_id={payload['workflow_id']}")
    print(f"source_work_id={ids['source_work_id']}")
    print(f"title={result['source_work']['title']}")
    print(f"source_type={result['source_work']['source_type']}")
    print(f"chunk_count={result['chunk_count']}")
    print(f"first_chunk_id={result['first_chunk_id'] or 'none'}")
    print(f"last_chunk_id={result['last_chunk_id'] or 'none'}")
    print(f"chunk_ids={','.join(result['chunk_ids'])}")
    print(f"audit_event_id={ids.get('audit_event_id') or 'none'}")
    print(f"text_redacted={str(result['text_redacted']).lower()}")
    if args.output_json is not None:
        print(f"output_json={args.output_json}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Import a local UTF-8 text/markdown file through POST /source-works. "
            "Use a file-backed database URL."
        ),
    )
    parser.add_argument("source", type=Path, help="Path to a .md or .txt source file.")
    parser.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    parser.add_argument("--source-work-id", default=None, help="Optional explicit source_work id.")
    parser.add_argument("--title", default=None, help="Source title. Defaults to file stem.")
    parser.add_argument("--author", default=None, help="Optional source author.")
    parser.add_argument("--language", default="zh-CN", help="Source language label.")
    parser.add_argument(
        "--source-type",
        choices=("markdown", "txt"),
        default=None,
        help="Source type. Defaults to markdown for .md/.markdown, otherwise txt.",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="Local file encoding used for reading. Defaults to utf-8-sig.",
    )
    parser.add_argument("--request-id", default=None, help="Optional X-Request-ID.")
    parser.add_argument("--idempotency-key", default=None, help="Optional Idempotency-Key.")
    parser.add_argument("--actor-id", default="api-local:import-text")
    parser.add_argument("--actor-label", default="Local import text script")
    parser.add_argument("--actor-user-id", default="user_001")
    parser.add_argument(
        "--operation-reason",
        default="import source text from local script",
    )
    parser.add_argument("--max-paragraph-chars", type=int, default=500)
    parser.add_argument("--min-paragraph-chars", type=int, default=1)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional path to save the full API response JSON.",
    )
    return parser


def _request_body(
    *,
    args: argparse.Namespace,
    title: str,
    source_type: str,
    content: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": title,
        "author": args.author,
        "language": args.language,
        "source_type": source_type,
        "content": content,
        "content_encoding": "utf-8",
        "chunking": {
            "max_paragraph_chars": args.max_paragraph_chars,
            "min_paragraph_chars": args.min_paragraph_chars,
        },
        "actor": {
            "actor_id": args.actor_id,
            "actor_label": args.actor_label,
            "user_id": args.actor_user_id,
            "operation_reason": args.operation_reason,
            "metadata": {"entrypoint": "scripts/import_text.py"},
        },
        "metadata": {"source_path_name": Path(args.source).name},
    }
    if args.source_work_id is not None:
        body["source_work_id"] = args.source_work_id
    return body


def _source_type_from_path(path: Path) -> str:
    return "markdown" if path.suffix.lower() in {".md", ".markdown"} else "txt"


def _default_idempotency_key(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return f"import-text-{digest}"


def _json_response(response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {"error": {"code": "non_json_response", "message": response.text}}
    if not isinstance(payload, dict):
        return {"error": {"code": "unexpected_response", "message": repr(payload)}}
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
