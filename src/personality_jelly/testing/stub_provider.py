from __future__ import annotations

from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig


class StubProvider:
    name = "stub"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        return "我记住了。先别急，我们把事情拆开看。"

    def generate_json(self, messages, schema, model_config):
        schema_title = schema.get("title")
        user_content = messages[-1].content if messages else ""
        if schema_title == "ReaderExtraction":
            chunk_id = _first_chunk_id(user_content)
            return {
                "claims": [
                    {
                        "claim_type": "personality",
                        "content": "目标角色行事谨慎，习惯先观察再行动。",
                        "confidence": 0.8,
                        "reasoning": "stub provider 根据输入文本生成的演示 claim。",
                        "evidence": [
                            {
                                "chunk_id": chunk_id,
                                "excerpt": _first_nonempty_line(user_content),
                                "support_score": 0.8,
                            }
                        ],
                    }
                ]
            }
        if schema_title == "VerifierResult":
            claim_ids = _claim_ids(user_content)
            return {
                "decisions": [
                    {
                        "claim_id": claim_id,
                        "status": "verified",
                        "confidence": 0.85,
                        "reasoning": "stub provider 默认验证演示 claim。",
                    }
                    for claim_id in claim_ids
                ],
                "conflicts": [],
            }
        if schema_title == "PersonaCompilation":
            return {
                "core_self": "目标角色谨慎敏锐，行动前会先观察局势。",
                "speech_rules": ["表达克制，避免夸张。"],
                "behavior_rules": ["先判断风险，再回应。"],
                "world_adaptation_rules": ["可以与现实用户交流，但不改写原作经历。"],
                "forbidden_rules": ["不能把用户输入写成原作 canon。"],
            }
        if schema_title == "CriticEvaluation":
            return {
                "ooc_risk": "low",
                "fact_risk": "low",
                "memory_risk": "low",
                "mode_risk": "low",
                "reasons": ["stub provider: 回复通过基础审校。"],
                "suggested_action": "accept",
            }
        if schema_title == "MemoryCuration":
            return {
                "memories": [
                    {
                        "scope": "user_memory",
                        "status": "accepted",
                        "content": "用户希望角色记住当前对话中的偏好或状态。",
                        "importance": 0.6,
                        "reason": "stub provider: 用户消息包含记住请求或可持续偏好。",
                    }
                ]
            }
        raise ValueError(f"Unsupported schema title: {schema_title!r}")

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        return [[0.0] for _ in texts]


def _first_chunk_id(content: str) -> str:
    for line in content.splitlines():
        if line.startswith("[") and line.endswith("]"):
            return line.strip("[]")
    raise ValueError("StubProvider could not find a chunk id in reader prompt")


def _claim_ids(content: str) -> list[str]:
    return [
        line.split(": ", 1)[1]
        for line in content.splitlines()
        if line.startswith("claim_id: ")
    ]


def _first_nonempty_line(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("["):
            return stripped[:120]
    return "stub excerpt"

