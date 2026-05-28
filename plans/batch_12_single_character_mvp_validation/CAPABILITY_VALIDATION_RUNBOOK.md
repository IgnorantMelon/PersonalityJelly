# Batch 12 单角色 MVP 能力验证操作手顺

## 验证目标

本手顺只围绕 5 个产品问题验收：

1. 如何导入文本
2. 是否获得角色提取结果，在哪能看到
3. 结果是否符合要求
4. 如何运用这个产出进行对话
5. 对话相关所有特性如何体验

当前真实边界：

- 文本导入、角色创建、persona setup、结果检查已经有 API。
- 对话创建和对话检查有 API。
- 真正执行一轮角色对话，也就是生成 assistant reply 的 turn workflow，目前还没有 HTTP API；现阶段要通过 `pjelly turn` 或 `pjelly demo` 体验。
- 因此本手顺的验收口径是：API 验证产出是否成立；CLI 验证这些产出是否能驱动当前对话产品面。

## 前置条件

从干净的 `dev` 执行：

```powershell
git switch dev
git pull --ff-only
git status --short --branch
uv sync
```

创建本次证据目录和共用数据库：

```powershell
$RunId = Get-Date -Format "yyyyMMdd-HHmmss"
$EvidenceDir = Join-Path (Resolve-Path .) "tmp\capability-validation\$RunId"
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$DbPath = Join-Path $EvidenceDir "single-character-mvp.db"
$DbUrl = "sqlite:///" + ($DbPath -replace "\\", "/")

git rev-parse HEAD | Tee-Object -FilePath "$EvidenceDir\git-head.txt"
git status --short --branch | Tee-Object -FilePath "$EvidenceDir\git-status.txt"
```

## 1. 如何导入文本

准备一个最小源文本。文件名会作为 API source title，后续 CLI `--reuse-existing` 会靠它复用同一个 source work。

```powershell
$SourcePath = Join-Path $EvidenceDir "single-character-source.md"
Set-Content -LiteralPath $SourcePath -Encoding UTF8 -Value @"
# 第一章

林霜总是先观察，再行动。她不会轻易相信陌生人，但会保护同伴。
"@
```

用 API 导入文本、创建角色、运行 persona setup，并把每个 API 结果写到证据目录：

```powershell
$env:PJ_CAPABILITY_EVIDENCE_DIR = $EvidenceDir
$env:PJ_CAPABILITY_DB_URL = $DbUrl
$ApiFlowPath = Join-Path $EvidenceDir "api-product-flow.py"

Set-Content -LiteralPath $ApiFlowPath -Encoding UTF8 -Value @'
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from personality_jelly.api import create_app
from personality_jelly.application import create_database_resources
from personality_jelly.core import Settings


evidence_dir = Path(os.environ["PJ_CAPABILITY_EVIDENCE_DIR"])
db_url = os.environ["PJ_CAPABILITY_DB_URL"]
resources = create_database_resources(db_url)
app = create_app(
    settings=Settings(config_file="missing-test-pjelly.toml", _env_file=None),
    database_resources=resources,
)

source_content = "# 第一章\n\n林霜总是先观察，再行动。她不会轻易相信陌生人，但会保护同伴。"


def save(name: str, response) -> dict:
    payload = {"status_code": response.status_code, "body": response.json()}
    (evidence_dir / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def require_success(name: str, response, expected_status: int = 201) -> dict:
    payload = save(name, response)
    if response.status_code != expected_status:
        raise AssertionError(f"{name} expected {expected_status}, got {response.status_code}: {response.text}")
    return payload["body"]


with TestClient(app) as client:
    source = require_success(
        "01-source-work",
        client.post(
            "/source-works",
            headers={
                "X-Request-ID": "req_product_source",
                "Idempotency-Key": "product-source-key",
            },
            json={
                "source_work_id": "sw_product_lins_huang",
                "title": "single-character-source",
                "author": "Validation",
                "language": "zh-CN",
                "source_type": "markdown",
                "content": source_content,
                "content_encoding": "utf-8",
                "chunking": {"max_paragraph_chars": 500, "min_paragraph_chars": 1},
                "actor": {
                    "actor_id": "api-local:capability",
                    "actor_label": "Capability validation",
                    "user_id": "user_001",
                    "operation_reason": "import source text for product validation",
                    "metadata": {"entrypoint": "batch-12-product-flow"},
                },
                "metadata": {"client_label": "batch-12-product-flow"},
            },
        ),
    )

    character = require_success(
        "02-character-create",
        client.post(
            "/characters",
            headers={"X-Request-ID": "req_product_character"},
            json={
                "source_work_id": source["ids"]["source_work_id"],
                "character_id": "char_product_lins_huang",
                "canonical_name": "林霜",
                "aliases": ["阿霜"],
                "actor": {
                    "actor_id": "api-local:capability",
                    "actor_label": "Capability validation",
                    "user_id": "user_001",
                    "operation_reason": "create character for product validation",
                    "metadata": {"entrypoint": "batch-12-product-flow"},
                },
                "metadata": {"client_label": "batch-12-product-flow"},
            },
        ),
    )

    setup = require_success(
        "03-persona-setup",
        client.post(
            "/characters/char_product_lins_huang/persona-setup-runs",
            headers={
                "X-Request-ID": "req_product_setup",
                "Idempotency-Key": "product-persona-setup-key",
            },
            json={
                "source_work_id": source["ids"]["source_work_id"],
                "character_id": character["ids"]["character_id"],
                "provider": {
                    "source": "stub",
                    "model": "product-setup-model",
                    "roles": {
                        "reader": {"model": "product-reader-model"},
                        "verifier": {"model": "product-verifier-model"},
                        "persona_compiler": {"model": "product-compiler-model"},
                    },
                },
                "workflow_options": {"max_chunks": 2},
                "actor": {
                    "actor_id": "api-local:capability",
                    "actor_label": "Capability validation",
                    "user_id": "user_001",
                    "operation_reason": "extract role persona for product validation",
                    "metadata": {"entrypoint": "batch-12-product-flow"},
                },
                "metadata": {"client_label": "batch-12-product-flow"},
            },
        ),
    )

    character_detail = require_success(
        "04-character-detail",
        client.get(f"/characters/{character['ids']['character_id']}"),
        expected_status=200,
    )
    claims = require_success(
        "05-claims",
        client.get("/claims", params={"character_id": character["ids"]["character_id"]}),
        expected_status=200,
    )
    first_chunk_id = source["result"]["first_chunk_id"]
    if first_chunk_id:
        require_success(
            "06-source-chunk",
            client.get(f"/source-chunks/{first_chunk_id}"),
            expected_status=200,
        )
    require_success(
        "07-workflow-persona-setup",
        client.get(f"/workflow-runs/{setup['workflow_id']}"),
        expected_status=200,
    )
    require_success(
        "08-audit-persona-setup",
        client.get(f"/audit-events/{setup['ids']['audit_event_id']}"),
        expected_status=200,
    )
    require_success(
        "09-llm-traces",
        client.get("/llm-traces", params={"limit": 20}),
        expected_status=200,
    )

print(f"database_url={db_url}")
print(f"source_work_id={source['ids']['source_work_id']}")
print(f"chunk_count={source['result']['chunk_count']}")
print(f"character_id={character['ids']['character_id']}")
print(f"persona_version_id={setup['ids']['persona_version_id']}")
print(f"claim_count={character_detail['claim_count']}")
print(f"evidence_count={character_detail['evidence_count']}")
print(f"llm_trace_count={len(setup['ids']['llm_trace_ids'])}")
print(f"character_detail_file={evidence_dir / '04-character-detail.json'}")
print(f"claims_file={evidence_dir / '05-claims.json'}")
print(f"source_chunk_file={evidence_dir / '06-source-chunk.json'}")
'@

.\.venv\Scripts\python $ApiFlowPath | Tee-Object -FilePath "$EvidenceDir\api-product-flow.txt"
```

导入成功的判断：

- `01-source-work.json` 的 `status_code` 是 `201`
- `api-product-flow.txt` 中有 `source_work_id`
- `chunk_count` 大于 `0`
- `01-source-work.json` 中有 `result.chunk_ids`
- 写接口响应不直接回显原始 source text，只返回 source/chunk IDs、计数和 redaction flags

## 2. 是否获得角色提取结果，在哪能看到

角色提取结果分三层看：

- 角色壳：`02-character-create.json`
- persona setup 产物索引：`03-persona-setup.json`
- 可读详情：`04-character-detail.json`、`05-claims.json`、`06-source-chunk.json`

重点看这些字段：

- `03-persona-setup.json`
  - `body.status`
  - `body.ids.persona_version_id`
  - `body.result.counts.candidate_claims`
  - `body.result.counts.verified_claims`
  - `body.result.counts.evidence_refs`
  - `body.result.redaction`
- `04-character-detail.json`
  - `body.latest_persona_version_id`
  - `body.latest_persona_version.core_self`
  - `body.claim_count`
  - `body.evidence_count`
  - `body.claims`
- `05-claims.json`
  - `body.items[*].claim_type`
  - `body.items[*].status`
  - `body.items[*].confidence`
  - `body.items[*].content`
  - `body.items[*].evidence`
- `06-source-chunk.json`
  - `body.text`

`06-source-chunk.json` 是刻意用来人工核对 claim 是否有原文依据的详情接口；写接口、workflow、audit 和 error 响应不应泄露原始全文。

## 3. 结果是否符合要求

按下面标准验收，不需要主观猜测：

| 项目 | 合格标准 |
| --- | --- |
| 文本导入 | `chunk_count > 0`，有 `source_work_id` 和 `chunk_ids` |
| 角色创建 | `character_id` 存在，`canonical_name` 是目标角色，`latest_persona_version_id` 在 persona setup 前可为空 |
| persona setup | `status=completed`，有 `persona_version_id`，`llm_trace_count >= 3` |
| claim | `claim_count > 0`，至少有 candidate 或 verified claim |
| evidence | `evidence_count > 0`，claim 里有 `evidence.chunk_id`、`excerpt`、`support_score` |
| persona | `latest_persona_version.core_self` 非空 |
| 溯源 | claim 能通过 `evidence.chunk_id` 对应到 source chunk |
| 脱敏 | 写接口、workflow、audit 不出现 source全文、prompt、provider payload、raw output、密钥、路径 |

如果用 `stub` provider，结果只验证链路和数据形态，不验证语义质量。如果要判断真实角色抽取质量，把 `provider.source` 改成 `env` 并配置真实模型后重跑；语义质量验收仍看 claim、evidence、persona 是否能被原文支撑。

## 4. 如何运用这个产出进行对话

当前真正执行对话 turn 的入口是 CLI。为了复用前面 API 已导入的 source、character、persona，必须使用同一个 `$DbUrl`，并加 `--reuse-existing`。

```powershell
.\.venv\Scripts\pjelly.exe demo $SourcePath `
  --character 林霜 `
  --alias 阿霜 `
  --user "验证用户" `
  --user-message "请记住，我喜欢在夜里写作。" `
  --database-url $DbUrl `
  --provider stub `
  --reuse-existing `
  | Tee-Object -FilePath "$EvidenceDir\10-dialogue-first-turn.txt"
```

提取对话相关 ID：

```powershell
$FirstTurn = Get-Content "$EvidenceDir\10-dialogue-first-turn.txt"
$ConversationId = (($FirstTurn | Select-String "^conversation_id=").Line -split "=", 2)[1]
$ContextPackageId = (($FirstTurn | Select-String "^context_package_id=").Line -split "=", 2)[1]
$CriticReportId = (($FirstTurn | Select-String "^critic_report_id=").Line -split "=", 2)[1]
```

成功判断：

- `conversation_id` 存在
- `assistant=` 有回复
- `context_package_id` 存在
- `critic_report_id` 存在
- `critic_action=accept`
- `failure_case_count=0`
- `memory_count` 存在

如果只使用 API，目前只能创建和查看 conversation，不能通过 HTTP 生成 assistant reply：

```text
POST /conversations
GET /conversations/{conversation_id}
GET /context-packages/{context_package_id}
```

注意：`POST /conversations` 还要求 user 已存在；当前也没有独立 user create API。上面的 `pjelly demo --reuse-existing` 会复用 API 产出的 source/character/persona，并创建本地 user 和 conversation。

缺口：`POST /conversations/{conversation_id}/turns` 或等价 turn API 尚未实现。

## 5. 对话相关所有特性如何体验

### 5.1 连续对话

```powershell
.\.venv\Scripts\pjelly.exe turn $ConversationId `
  --message "如果我要独自去调查，你会怎么提醒我？" `
  --database-url $DbUrl `
  --provider stub `
  | Tee-Object -FilePath "$EvidenceDir\11-dialogue-second-turn.txt"
```

看点：

- 第二轮继续使用同一个 `conversation_id`
- 输出新的 `assistant_message_id`
- 输出新的 `context_package_id`
- `critic_action=accept`

### 5.2 查看会话记录

```powershell
.\.venv\Scripts\pjelly.exe show conversation $ConversationId --database-url $DbUrl --messages 10 `
  | Tee-Object -FilePath "$EvidenceDir\12-show-conversation.txt"
```

提取真实 user id，后面的 memory 检查要用它：

```powershell
$Conversation = Get-Content "$EvidenceDir\12-show-conversation.txt"
$UserId = (($Conversation | Select-String "^user_id=").Line -split "=", 2)[1]
```

看点：

- 能看到 user/assistant 交替消息
- `persona_version_id` 是前面 persona setup 产出的版本
- `mode` 正常

### 5.3 查看本轮上下文组装

```powershell
.\.venv\Scripts\pjelly.exe show context-package $ContextPackageId --database-url $DbUrl `
  | Tee-Object -FilePath "$EvidenceDir\13-show-context-package.txt"
```

看点：

- `claim_ids` 包含角色 canon claim
- `memory_ids` 包含本轮可用记忆
- `retrieved_chunk_ids` 包含检索到的原文 chunk
- `assembled_prompt` 能看到 persona、canon、memory、retrieved context 如何组装

### 5.4 查看 critic 审查

```powershell
.\.venv\Scripts\pjelly.exe show critic-report $CriticReportId --database-url $DbUrl `
  | Tee-Object -FilePath "$EvidenceDir\14-show-critic-report.txt"
```

看点：

- `ooc_risk`
- `fact_risk`
- `memory_risk`
- `mode_risk`
- `suggested_action`
- `reasons`

### 5.5 查看失败案例

```powershell
.\.venv\Scripts\pjelly.exe list failure-cases --conversation-id $ConversationId --database-url $DbUrl `
  | Tee-Object -FilePath "$EvidenceDir\15-list-failure-cases.txt"
```

看点：

- 正常 smoke 下 `failure_case_count=0`
- 如果有失败，记录 `failure_case.id`，再用 `show failure-case` 查看上下文、critic reason、消息内容

### 5.6 查看和管理记忆

```powershell
.\.venv\Scripts\pjelly.exe list memories `
  --user-id $UserId `
  --character-id char_product_lins_huang `
  --database-url $DbUrl `
  | Tee-Object -FilePath "$EvidenceDir\16-list-memories.txt"
```

看点：

- 用户偏好应该进入 user/relationship memory
- 用户输入不应该变成 source canon
- 如果产生 candidate memory，可以用 `review memory` 接受或拒绝
- 如果记忆内容不准，可以用 `edit memory`
- 如果记忆不应继续使用，可以用 `archive memory`

操作模板：

```powershell
.\.venv\Scripts\pjelly.exe review memory <memory_id> --decision accept --reason "人工确认" --database-url $DbUrl
.\.venv\Scripts\pjelly.exe edit memory <memory_id> --content "修正后的记忆" --reason "人工修正" --database-url $DbUrl
.\.venv\Scripts\pjelly.exe archive memory <memory_id> --database-url $DbUrl
```

### 5.7 生成会话摘要

```powershell
.\.venv\Scripts\pjelly.exe summarize conversation $ConversationId `
  --messages 20 `
  --database-url $DbUrl `
  --provider stub `
  | Tee-Object -FilePath "$EvidenceDir\17-summarize-conversation.txt"
```

看点：

- `summary` 存在
- `short_term_scene_state`
- `user_memory_candidates`
- `relationship_memory_notes`
- `reflective_notes`

### 5.8 查看 LLM trace

```powershell
.\.venv\Scripts\pjelly.exe list llm-traces --database-url $DbUrl `
  | Tee-Object -FilePath "$EvidenceDir\18-list-llm-traces.txt"
```

看点：

- persona setup 阶段应有 reader、verifier、compiler trace
- 对话阶段应有 mode、roleplay、critic、memory 相关 trace
- `validation_error_count` 应为 0

### 5.9 角色产出复查

```powershell
.\.venv\Scripts\pjelly.exe show character char_product_lins_huang --database-url $DbUrl `
  | Tee-Object -FilePath "$EvidenceDir\19-show-character.txt"

.\.venv\Scripts\pjelly.exe list claims --character-id char_product_lins_huang --database-url $DbUrl `
  | Tee-Object -FilePath "$EvidenceDir\20-list-claims.txt"
```

看点：

- `latest_persona_version_id` 仍然存在
- `claim_count` 和 `evidence_count` 非零
- `core_self` 可读
- 对话产生的用户记忆没有污染 canon claim

## 最终记录模板

```text
Batch 12 单角色 MVP 产品能力验证

Commit:
Evidence directory:
Database URL:

1. 文本导入:
- source_work_id:
- chunk_count:
- evidence file:

2. 角色提取结果:
- character_id:
- persona_version_id:
- claim_count:
- evidence_count:
- character detail file:
- claims file:

3. 结果合格性:
- source/chunk:
- claims/evidence:
- persona/core_self:
- trace:
- redaction:
- semantic quality with stub/env:

4. 运用产出对话:
- conversation_id:
- first assistant:
- context_package_id:
- critic_report_id:
- critic_action:

5. 对话特性体验:
- multi-turn:
- conversation inspection:
- context package:
- critic:
- failure cases:
- memories:
- summary:
- llm traces:
- canon/memory boundary:

Decision:
- accepted / blocked
- defects:
- missing API surface:
```
