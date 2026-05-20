from enum import StrEnum
from uuid import uuid4


class EntityKind(StrEnum):
    SOURCE_WORK = "source_work"
    SOURCE_CHUNK = "source_chunk"
    CHARACTER = "character"
    CANON_CLAIM = "canon_claim"
    EVIDENCE_REF = "evidence_ref"
    CLAIM_CONFLICT = "claim_conflict"
    PERSONA_VERSION = "persona_version"
    USER = "user"
    CONVERSATION = "conversation"
    MESSAGE = "message"
    MEMORY = "memory"
    CONTEXT_PACKAGE = "context_package"
    CRITIC_REPORT = "critic_report"
    EVALUATION_RUN = "evaluation_run"
    EVALUATION_CASE_RESULT = "evaluation_case_result"


ID_PREFIXES: dict[EntityKind, str] = {
    EntityKind.SOURCE_WORK: "sw",
    EntityKind.SOURCE_CHUNK: "chunk",
    EntityKind.CHARACTER: "char",
    EntityKind.CANON_CLAIM: "claim",
    EntityKind.EVIDENCE_REF: "ev",
    EntityKind.CLAIM_CONFLICT: "conflict",
    EntityKind.PERSONA_VERSION: "pv",
    EntityKind.USER: "user",
    EntityKind.CONVERSATION: "conv",
    EntityKind.MESSAGE: "msg",
    EntityKind.MEMORY: "mem",
    EntityKind.CONTEXT_PACKAGE: "ctx",
    EntityKind.CRITIC_REPORT: "cr",
    EntityKind.EVALUATION_RUN: "eval",
    EntityKind.EVALUATION_CASE_RESULT: "evalcase",
}


def generate_id(kind: EntityKind) -> str:
    return f"{ID_PREFIXES[kind]}_{uuid4().hex}"

