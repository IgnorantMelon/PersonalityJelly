"""Conversation runtime services."""

from personality_jelly.runtime.context import ContextBuildResult, build_context_package
from personality_jelly.runtime.mode import infer_interaction_mode, resolve_interaction_mode
from personality_jelly.runtime.conversation import (
    ConversationCreationResult,
    UserCreationResult,
    create_conversation,
    create_user,
)
from personality_jelly.runtime.roleplay import RoleplayTurnResult, send_message
from personality_jelly.runtime.summary import ConversationSummaryResult, summarize_conversation
from personality_jelly.runtime.turn import (
    RoleplayTurnModelConfigs,
    RoleplayTurnOrchestrationResult,
    RoleplayTurnProviders,
    send_roleplay_turn,
)

__all__ = [
    "ContextBuildResult",
    "ConversationCreationResult",
    "ConversationSummaryResult",
    "RoleplayTurnResult",
    "RoleplayTurnModelConfigs",
    "RoleplayTurnOrchestrationResult",
    "RoleplayTurnProviders",
    "UserCreationResult",
    "build_context_package",
    "create_conversation",
    "create_user",
    "infer_interaction_mode",
    "resolve_interaction_mode",
    "send_message",
    "send_roleplay_turn",
    "summarize_conversation",
]

