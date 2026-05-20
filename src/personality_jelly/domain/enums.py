from enum import StrEnum


class InteractionMode(StrEnum):
    REALITY_CHAT = "reality_chat"
    ROLEPLAY_SCENE = "roleplay_scene"
    CO_CREATION = "co_creation"
    META_DISCUSSION = "meta_discussion"


class ClaimStatus(StrEnum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    REJECTED = "rejected"
    CONFLICTED = "conflicted"


class ClaimType(StrEnum):
    IDENTITY = "identity"
    APPEARANCE = "appearance"
    PERSONALITY = "personality"
    RELATIONSHIP = "relationship"
    EVENT = "event"
    ABILITY = "ability"
    SPEECH = "speech"
    WORLD_RULE = "world_rule"


class MemoryScope(StrEnum):
    USER_MEMORY = "user_memory"
    RELATIONSHIP_MEMORY = "relationship_memory"
    SESSION_MEMORY = "session_memory"
    REFLECTIVE_MEMORY = "reflective_memory"


class MemoryStatus(StrEnum):
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class CriticRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CriticAction(StrEnum):
    ACCEPT = "accept"
    RETRY = "retry"
    LOG = "log"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class EvaluationStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvaluationCaseStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"

