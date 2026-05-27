from enum import StrEnum
from uuid import uuid4


class EntityKind(StrEnum):
    SOURCE_WORK = "source_work"
    SOURCE_CHUNK = "source_chunk"
    SOURCE_CHUNK_EMBEDDING = "source_chunk_embedding"
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
    FAILURE_CASE = "failure_case"
    LLM_RAW_OUTPUT = "llm_raw_output"
    EVALUATION_RUN = "evaluation_run"
    EVALUATION_CASE_RESULT = "evaluation_case_result"
    RETRIEVAL_EVALUATION_RUN = "retrieval_evaluation_run"
    RETRIEVAL_EVALUATION_CASE_RESULT = "retrieval_evaluation_case_result"
    WORKFLOW_RUN_LINK = "workflow_run_link"
    IDEMPOTENCY_RECORD = "idempotency_record"


ID_PREFIXES: dict[EntityKind, str] = {
    EntityKind.SOURCE_WORK: "sw",
    EntityKind.SOURCE_CHUNK: "chunk",
    EntityKind.SOURCE_CHUNK_EMBEDDING: "chunkemb",
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
    EntityKind.FAILURE_CASE: "fail",
    EntityKind.LLM_RAW_OUTPUT: "llmraw",
    EntityKind.EVALUATION_RUN: "eval",
    EntityKind.EVALUATION_CASE_RESULT: "evalcase",
    EntityKind.RETRIEVAL_EVALUATION_RUN: "retrievaleval",
    EntityKind.RETRIEVAL_EVALUATION_CASE_RESULT: "retrievalcase",
    EntityKind.WORKFLOW_RUN_LINK: "wflink",
    EntityKind.IDEMPOTENCY_RECORD: "idem",
}


def generate_id(kind: EntityKind) -> str:
    return f"{ID_PREFIXES[kind]}_{uuid4().hex}"

