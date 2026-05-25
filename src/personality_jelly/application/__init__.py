"""Shared application-service bootstrap helpers.

This package is the boundary that CLI commands and future API adapters can both use for
orchestration concerns that do not belong in domain modules.
"""

from personality_jelly.application.bootstrap import (
    DatabaseResources,
    create_database_resources,
    resolve_database_url,
)
from personality_jelly.application.errors import NormalizedError, normalize_error
from personality_jelly.application.providers import (
    ModelRoleBundle,
    ProviderRoleBundle,
    build_turn_role_bundles,
    resolve_embedding_config,
    resolve_embedding_provider,
    resolve_roleplay_provider,
)

__all__ = [
    "DatabaseResources",
    "ModelRoleBundle",
    "NormalizedError",
    "ProviderRoleBundle",
    "build_turn_role_bundles",
    "create_database_resources",
    "normalize_error",
    "resolve_database_url",
    "resolve_embedding_config",
    "resolve_embedding_provider",
    "resolve_roleplay_provider",
]
