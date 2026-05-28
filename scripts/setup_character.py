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
    database_url = args.database_url or Settings().database_url
    if database_url == "sqlite:///:memory:":
        print(
            "error: this script uses the API adapter and requires a file-backed database; "
            "use sqlite:///tmp/single-character-mvp.db instead of sqlite:///:memory:",
            file=sys.stderr,
        )
        return 2

    character_body = _character_body(args)
    character_key = args.character_idempotency_key or _default_idempotency_key(
        "character",
        character_body,
    )
    setup_body = _setup_body(args, character_id=args.character_id)
    setup_key = args.setup_idempotency_key or _default_idempotency_key("persona-setup", setup_body)

    resources = create_database_resources(database_url)
    app = create_app(settings=Settings(), database_resources=resources)
    with TestClient(app) as client:
        character_response = client.post(
            "/characters",
            headers={
                "X-Request-ID": args.character_request_id
                or _default_request_id("character", character_key),
                "Idempotency-Key": character_key,
            },
            json=character_body,
        )
        character_payload = _json_response(character_response)
        if character_response.status_code >= 400:
            _print_error("character_create", character_response.status_code, character_payload)
            return 1

        character_id = character_payload["ids"]["character_id"]
        setup_body = _setup_body(args, character_id=character_id)
        setup_key = args.setup_idempotency_key or _default_idempotency_key(
            "persona-setup",
            setup_body,
        )
        setup_response = client.post(
            f"/characters/{character_id}/persona-setup-runs",
            headers={
                "X-Request-ID": args.setup_request_id
                or _default_request_id("setup", setup_key),
                "Idempotency-Key": setup_key,
            },
            json=setup_body,
        )
        setup_payload = _json_response(setup_response)
        if setup_response.status_code >= 400:
            output_dir = _output_dir(args, character_id=character_id)
            _save_json(output_dir / "01-character-create.json", character_response.status_code, character_payload)
            _save_json(output_dir / "02-persona-setup-error.json", setup_response.status_code, setup_payload)
            _print_error("persona_setup", setup_response.status_code, setup_payload)
            print(f"output_dir={output_dir}")
            return 1

        character_detail_response = client.get(f"/characters/{character_id}")
        claims_response = client.get("/claims", params={"character_id": character_id})
        workflow_response = client.get(f"/workflow-runs/{setup_payload['workflow_id']}")
        audit_event_id = setup_payload["ids"].get("audit_event_id")
        audit_response = (
            client.get(f"/audit-events/{audit_event_id}") if audit_event_id else None
        )
        traces_response = client.get("/llm-traces", params={"limit": args.trace_limit})

    output_dir = _output_dir(args, character_id=character_id)
    _save_json(output_dir / "01-character-create.json", character_response.status_code, character_payload)
    _save_json(output_dir / "02-persona-setup.json", setup_response.status_code, setup_payload)
    _save_response(output_dir / "03-character-detail.json", character_detail_response)
    _save_response(output_dir / "04-claims.json", claims_response)
    _save_response(output_dir / "05-workflow-persona-setup.json", workflow_response)
    if audit_response is not None:
        _save_response(output_dir / "06-audit-persona-setup.json", audit_response)
    _save_response(output_dir / "07-llm-traces.json", traces_response)

    detail_payload = _json_response(character_detail_response)
    claims_payload = _json_response(claims_response)
    result = setup_payload["result"]
    counts = result["counts"]
    print(f"status_code={setup_response.status_code}")
    print(f"database_url={database_url}")
    print(f"source_work_id={args.source_work_id}")
    print(f"character_id={character_id}")
    print(f"canonical_name={detail_payload.get('canonical_name', args.character_name)}")
    print(f"persona_version_id={setup_payload['ids'].get('persona_version_id')}")
    print(f"candidate_claim_count={counts['candidate_claims']}")
    print(f"verified_claim_count={counts['verified_claims']}")
    print(f"evidence_ref_count={counts['evidence_refs']}")
    print(f"conflict_count={counts['conflicts']}")
    print(f"llm_trace_count={counts['llm_traces']}")
    print(f"claim_count={detail_payload.get('claim_count', 0)}")
    print(f"claims_list_count={len(claims_payload.get('items', []))}")
    print(f"provider={args.provider}")
    print(f"max_chunks={args.max_chunks if args.max_chunks is not None else 'all'}")
    print(f"output_dir={output_dir}")
    print(f"character_detail_json={output_dir / '03-character-detail.json'}")
    print(f"claims_json={output_dir / '04-claims.json'}")
    print(f"persona_setup_json={output_dir / '02-persona-setup.json'}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a character for an imported source work and run "
            "POST /characters/{character_id}/persona-setup-runs."
        ),
    )
    parser.add_argument("source_work_id", help="Imported source_work_id from import_text.py.")
    parser.add_argument("character_name", help="Canonical character name to extract.")
    parser.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    parser.add_argument("--character-id", default=None, help="Optional explicit character id.")
    parser.add_argument("--alias", action="append", default=[], help="Character alias; may repeat.")
    parser.add_argument(
        "--provider",
        choices=("stub", "env"),
        default="stub",
        help="stub validates the flow; env uses configured real provider.",
    )
    parser.add_argument("--model", default=None, help="Optional model label for all setup roles.")
    parser.add_argument("--reader-model", default=None, help="Optional reader model label.")
    parser.add_argument("--verifier-model", default=None, help="Optional verifier model label.")
    parser.add_argument("--compiler-model", default=None, help="Optional persona compiler model label.")
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=20,
        help="Maximum source chunks used for extraction. Defaults to 20; pass 0 for all chunks.",
    )
    parser.add_argument("--actor-id", default="api-local:setup-character")
    parser.add_argument("--actor-label", default="Local setup character script")
    parser.add_argument("--actor-user-id", default="user_001")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--trace-limit", type=int, default=50)
    parser.add_argument("--character-request-id", default=None)
    parser.add_argument("--setup-request-id", default=None)
    parser.add_argument("--character-idempotency-key", default=None)
    parser.add_argument("--setup-idempotency-key", default=None)
    return parser


def _character_body(args: argparse.Namespace) -> dict[str, Any]:
    body: dict[str, Any] = {
        "source_work_id": args.source_work_id,
        "canonical_name": args.character_name,
        "aliases": args.alias,
        "actor": _actor(
            args,
            operation_reason="create character from imported source",
            entrypoint="scripts/setup_character.py",
        ),
        "metadata": {"entrypoint": "scripts/setup_character.py"},
    }
    if args.character_id is not None:
        body["character_id"] = args.character_id
    return body


def _setup_body(args: argparse.Namespace, *, character_id: str | None) -> dict[str, Any]:
    max_chunks = None if args.max_chunks == 0 else args.max_chunks
    return {
        "source_work_id": args.source_work_id,
        "character_id": character_id,
        "provider": {
            "source": args.provider,
            "model": args.model,
            "roles": {
                "reader": {"model": args.reader_model},
                "verifier": {"model": args.verifier_model},
                "persona_compiler": {"model": args.compiler_model},
            },
        },
        "workflow_options": {"max_chunks": max_chunks},
        "actor": _actor(
            args,
            operation_reason="extract persona from imported source",
            entrypoint="scripts/setup_character.py",
        ),
        "metadata": {"entrypoint": "scripts/setup_character.py"},
    }


def _actor(
    args: argparse.Namespace,
    *,
    operation_reason: str,
    entrypoint: str,
) -> dict[str, Any]:
    return {
        "actor_id": args.actor_id,
        "actor_label": args.actor_label,
        "user_id": args.actor_user_id,
        "operation_reason": operation_reason,
        "metadata": {"entrypoint": entrypoint},
    }


def _output_dir(args: argparse.Namespace, *, character_id: str) -> Path:
    if args.output_dir is not None:
        output_dir = args.output_dir
    else:
        output_dir = Path("tmp") / "character-setup" / character_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _save_response(path: Path, response) -> None:
    _save_json(path, response.status_code, _json_response(response))


def _save_json(path: Path, status_code: int, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"status_code": status_code, "body": payload}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _default_idempotency_key(prefix: str, body: dict[str, Any]) -> str:
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}-{digest}"


def _default_request_id(prefix: str, idempotency_key: str) -> str:
    return f"req_{prefix}_{idempotency_key.rsplit('-', 1)[-1]}"


def _json_response(response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {"error": {"code": "non_json_response", "message": response.text}}
    if not isinstance(payload, dict):
        return {"error": {"code": "unexpected_response", "message": repr(payload)}}
    return payload


def _print_error(step: str, status_code: int, payload: dict[str, Any]) -> None:
    error = payload.get("error", {})
    print(f"step={step}")
    print(f"status_code={status_code}")
    print(f"error_code={error.get('code', 'unknown')}")
    print(f"message={error.get('message', payload)}")


if __name__ == "__main__":
    raise SystemExit(main())
