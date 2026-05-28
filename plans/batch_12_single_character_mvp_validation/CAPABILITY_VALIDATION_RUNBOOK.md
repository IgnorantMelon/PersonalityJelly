# Batch 12 单角色 MVP API 能力验证操作手顺

## 目标

本手顺用于验证 Batch 11 合入后的单角色 API 写链是否已经具备可用闭环。它是能力验证与证据采集流程，不是开发任务清单。

必验闭环包括：

- API 内联源文本摄入：`POST /source-works`
- API 确定性角色创建：`POST /characters`
- API provider-backed persona setup：`POST /characters/{character_id}/persona-setup-runs`
- API workflow、audit、diagnostics、redaction 与 idempotency 检查

CLI 不是 API 验收硬门槛。只有在需要确认当前 CLI 产品面仍可端到端工作，或需要覆盖尚未 HTTP API 化的 turn、summary、benchmark 能力时，才执行后面的可选 CLI 深度验证。

## 禁止范围

执行本手顺时不要新增或临时修改平台能力。发现问题只记录证据并归类，后续再拆成修复批次。

- 不做多作品、多角色扩展
- 不做 auth、workspace、UI、部署、队列、异步轮询、恢复或清理流程
- 不做上传、URL/path 摄入、embedding/source enrichment 路由
- 不新增 turn、summary、benchmark 的 HTTP 写接口
- 不把验证过程中的临时补丁混入 `dev`

## 前置条件

从干净的 `dev` 根检出执行：

```powershell
git switch dev
git pull --ff-only
git status --short --branch
uv sync
.\.venv\Scripts\python -m pytest tests/test_api_character_persona_setup_route.py -q
```

通过标准：

- `git status` 显示 `dev...origin/dev` 且无未提交源码变更
- persona setup route focused test 通过
- 当前阶段是能力验证，不启动 worker 开发分支

## 证据目录

所有输出统一写入 `tmp/capability-validation/<RunId>`。该目录应保持为临时证据，不提交。

```powershell
$RunId = Get-Date -Format "yyyyMMdd-HHmmss"
$EvidenceDir = Join-Path (Resolve-Path .) "tmp\capability-validation\$RunId"
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

git rev-parse HEAD | Tee-Object -FilePath "$EvidenceDir\git-head.txt"
git status --short --branch | Tee-Object -FilePath "$EvidenceDir\git-status.txt"
.\.venv\Scripts\python --version | Tee-Object -FilePath "$EvidenceDir\python-version.txt"
```

## 阶段 1：API 写链回归

先跑已有回归，覆盖 contract、幂等 replay/conflict、安全响应和 redaction。

```powershell
.\.venv\Scripts\python -m pytest `
  tests/test_api_source_ingest_route.py `
  tests/test_api_character_creation_route.py `
  tests/test_api_character_persona_setup_route.py `
  tests/test_api_contract.py `
  | Tee-Object -FilePath "$EvidenceDir\api-write-chain-tests.txt"
```

再跑一次 TestClient 级别的串联 smoke。这里不要求启动常驻 HTTP server，直接验证 FastAPI adapter 到 application 层的真实路由链。

```powershell
$ApiDbPath = Join-Path $EvidenceDir "api-write-chain.db"
$ApiDbUrl = "sqlite:///" + ($ApiDbPath -replace "\\", "/")
$env:PJ_CAPABILITY_EVIDENCE_DIR = $EvidenceDir
$env:PJ_CAPABILITY_API_DB_URL = $ApiDbUrl
$ApiSmokePath = Join-Path $EvidenceDir "api-write-chain-smoke.py"

Set-Content -LiteralPath $ApiSmokePath -Encoding UTF8 -Value @'
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from personality_jelly.api import create_app
from personality_jelly.application import create_database_resources
from personality_jelly.core import Settings


evidence_dir = Path(os.environ["PJ_CAPABILITY_EVIDENCE_DIR"])
db_url = os.environ["PJ_CAPABILITY_API_DB_URL"]
resources = create_database_resources(db_url)
app = create_app(
    settings=Settings(config_file="missing-test-pjelly.toml", _env_file=None),
    database_resources=resources,
)

source_content = "# 第一章\n\n林霜总是先观察，再行动。\n\n她不会把陌生人的话直接当作事实。"


def save_response(name: str, response) -> dict:
    payload = {
        "status_code": response.status_code,
        "body": response.json(),
    }
    (evidence_dir / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def assert_success(name: str, response, expected_status: int = 201) -> dict:
    payload = save_response(name, response)
    if response.status_code != expected_status:
        raise AssertionError(f"{name} expected {expected_status}, got {response.status_code}: {response.text}")
    if source_content in response.text:
        raise AssertionError(f"{name} leaked raw source text")
    return payload["body"]


with TestClient(app) as client:
    source = assert_success(
        "api-source-work",
        client.post(
            "/source-works",
            headers={
                "X-Request-ID": "req_capability_source",
                "Idempotency-Key": "capability-source-key",
            },
            json={
                "source_work_id": "sw_capability",
                "title": "能力验证源文本",
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
                    "operation_reason": "capability validation source ingest",
                    "metadata": {"entrypoint": "capability-validation"},
                },
                "metadata": {"client_label": "capability-validation"},
            },
        ),
    )

    character = assert_success(
        "api-character",
        client.post(
            "/characters",
            headers={"X-Request-ID": "req_capability_character"},
            json={
                "source_work_id": source["ids"]["source_work_id"],
                "character_id": "char_capability_lins_huang",
                "canonical_name": "林霜",
                "aliases": ["阿霜"],
                "actor": {
                    "actor_id": "api-local:capability",
                    "actor_label": "Capability validation",
                    "user_id": "user_001",
                    "operation_reason": "capability validation character create",
                    "metadata": {"entrypoint": "capability-validation"},
                },
                "metadata": {"client_label": "capability-validation"},
            },
        ),
    )

    setup_body = {
        "source_work_id": source["ids"]["source_work_id"],
        "provider": {
            "source": "stub",
            "model": "capability-setup-model",
            "roles": {
                "reader": {"model": "capability-reader-model"},
                "verifier": {"model": "capability-verifier-model"},
                "persona_compiler": {"model": "capability-compiler-model"},
            },
        },
        "workflow_options": {"max_chunks": 2},
        "actor": {
            "actor_id": "api-local:capability",
            "actor_label": "Capability validation",
            "user_id": "user_001",
            "operation_reason": "capability validation persona setup",
            "metadata": {"entrypoint": "capability-validation"},
        },
        "metadata": {"client_label": "capability-validation"},
    }
    setup = assert_success(
        "api-persona-setup",
        client.post(
            "/characters/char_capability_lins_huang/persona-setup-runs",
            headers={
                "X-Request-ID": "req_capability_setup",
                "Idempotency-Key": "capability-setup-key",
            },
            json=setup_body,
        ),
    )

    replay = assert_success(
        "api-persona-setup-replay",
        client.post(
            "/characters/char_capability_lins_huang/persona-setup-runs",
            headers={
                "X-Request-ID": "req_capability_setup_replay",
                "Idempotency-Key": "capability-setup-key",
            },
            json=setup_body,
        ),
    )
    if replay != setup:
        raise AssertionError("persona setup replay payload changed")

    conflict_response = client.post(
        "/characters/char_capability_lins_huang/persona-setup-runs",
        headers={"Idempotency-Key": "capability-setup-key"},
        json={**setup_body, "metadata": {"client_label": "changed"}},
    )
    conflict = save_response("api-persona-setup-conflict", conflict_response)
    if conflict_response.status_code != 409:
        raise AssertionError(f"expected idempotency conflict 409, got {conflict_response.status_code}")
    if "capability-setup-key" in conflict_response.text or source_content in conflict_response.text:
        raise AssertionError("conflict response leaked idempotency key or source text")

    workflow = client.get(f"/workflow-runs/{setup['workflow_id']}")
    save_response("api-persona-setup-workflow", workflow)
    audit = client.get(f"/audit-events/{setup['ids']['audit_event_id']}")
    save_response("api-persona-setup-audit", audit)

print(f"api_db_url={db_url}")
print(f"source_work_id={source['ids']['source_work_id']}")
print(f"character_id={character['ids']['character_id']}")
print(f"persona_version_id={setup['ids']['persona_version_id']}")
print(f"workflow_id={setup['workflow_id']}")
print(f"audit_event_id={setup['ids']['audit_event_id']}")
print(f"llm_trace_count={len(setup['ids']['llm_trace_ids'])}")
'@

.\.venv\Scripts\python $ApiSmokePath | Tee-Object -FilePath "$EvidenceDir\api-write-chain-smoke.txt"
```

通过标准：

- route tests 与 contract tests 全部通过
- smoke 输出 `source_work_id`、`character_id`、`persona_version_id`、`workflow_id`、`audit_event_id`
- persona setup replay 返回完全相同 payload，变更 body 后返回 409 conflict
- response、workflow、audit 证据中不包含原始源文本、prompt、provider payload、raw output、密钥、路径或 stack trace
- 本次能力链只验证 `POST /source-works`、`POST /characters`、`POST /characters/{character_id}/persona-setup-runs`，不引入 turn/summary/benchmark HTTP 写路由

## 阶段 2：可选 CLI 端到端单角色 smoke

本阶段不是 API 验收硬门槛。执行它的目的，是确认 API 写链产出的同类数据仍能支撑当前 CLI 产品面里的对话 runtime。创建一个最小源文件与独立 SQLite 数据库。默认使用 `stub` provider，避免网络与外部模型不稳定性影响能力判断。

```powershell
$SourcePath = Join-Path $EvidenceDir "single-character-source.md"
Set-Content -LiteralPath $SourcePath -Encoding UTF8 -Value @"
# 第一章

林霜总是先观察，再行动。她不会轻易相信陌生人，但会保护同伴。
"@

$CliDbPath = Join-Path $EvidenceDir "cli-capability.db"
$CliDbUrl = "sqlite:///" + ($CliDbPath -replace "\\", "/")
```

运行 deterministic demo：

```powershell
.\.venv\Scripts\pjelly.exe demo $SourcePath `
  --character 林霜 `
  --alias 阿霜 `
  --user "验证用户" `
  --user-message "请记住，我喜欢在夜里写作。" `
  --database-url $CliDbUrl `
  --provider stub `
  | Tee-Object -FilePath "$EvidenceDir\demo.txt"
```

提取关键 ID：

```powershell
$Demo = Get-Content "$EvidenceDir\demo.txt"
$SourceWorkId = (($Demo | Select-String "^source_work_id=").Line -split "=", 2)[1]
$CharacterId = (($Demo | Select-String "^character_id=").Line -split "=", 2)[1]
$PersonaVersionId = (($Demo | Select-String "^persona_version_id=").Line -split "=", 2)[1]
$ConversationId = (($Demo | Select-String "^conversation_id=").Line -split "=", 2)[1]
$ContextPackageId = (($Demo | Select-String "^context_package_id=").Line -split "=", 2)[1]
```

通过标准：

- `source_work_id`、`character_id`、`persona_version_id`、`conversation_id`、`context_package_id` 均存在
- `critic_action=accept`
- `failure_case_count=0`
- `memory_count` 存在且为非负数

## 阶段 3：可选对话连续性

对同一 conversation 执行第二轮：

```powershell
.\.venv\Scripts\pjelly.exe turn $ConversationId `
  --message "如果我要独自去调查，你会怎么提醒我？" `
  --database-url $CliDbUrl `
  --provider stub `
  | Tee-Object -FilePath "$EvidenceDir\turn-2.txt"
```

查看角色与会话：

```powershell
.\.venv\Scripts\pjelly.exe show character $CharacterId --database-url $CliDbUrl `
  | Tee-Object -FilePath "$EvidenceDir\show-character.txt"

.\.venv\Scripts\pjelly.exe show conversation $ConversationId --database-url $CliDbUrl --messages 10 `
  | Tee-Object -FilePath "$EvidenceDir\show-conversation.txt"
```

通过标准：

- 第二轮输出 assistant message、context package、critic report，且 critic action 为 accept
- character 仍挂载最新 persona version
- character 检查中 claim/evidence 数量非零
- conversation 检查中可见两轮 user message 与 assistant reply
- 用户记忆没有被写回 source canon

## 阶段 4：诊断、边界与脱敏

API 验收必须运行 diagnostics/API redaction 回归片段。下面的 CLI list 命令是可选证据采集，用于检查尚未完全 HTTP API 化的本地产品面。

可选列出 trace、claim、memory：

```powershell
.\.venv\Scripts\pjelly.exe list llm-traces --database-url $CliDbUrl `
  | Tee-Object -FilePath "$EvidenceDir\llm-traces.txt"

.\.venv\Scripts\pjelly.exe list claims --character-id $CharacterId --database-url $CliDbUrl `
  | Tee-Object -FilePath "$EvidenceDir\claims.txt"

.\.venv\Scripts\pjelly.exe list memories `
  --user-id user_001 `
  --character-id $CharacterId `
  --database-url $CliDbUrl `
  | Tee-Object -FilePath "$EvidenceDir\memories.txt"
```

运行 diagnostics/API redaction 回归片段：

```powershell
.\.venv\Scripts\python -m pytest `
  tests/test_api_audit_workflow_inspection.py `
  tests/test_api_diagnostics.py `
  tests/test_api_correlation_error_envelope.py `
  tests/test_application_audit_workflow_inspection.py `
  | Tee-Object -FilePath "$EvidenceDir\diagnostics-tests.txt"
```

通过标准：

- LLM trace 至少覆盖 reader、verifier、compiler 与 conversation runtime 调用
- claim list 中有该角色的 candidate 或 verified canon rows
- memory list 中只有 user/relationship memory，不出现重写 source canon 的条目
- diagnostics tests 全部通过
- workflow/audit/diagnostic HTTP 输出只暴露安全 ID、状态、计数、错误码、retry hint、redaction flags，不暴露原始文本或 provider 细节

## 阶段 5：可选 Benchmark 可运行性

Benchmark 执行尚不是 HTTP 写接口。本阶段只在需要确认完整 MVP 质量工具链时执行，不作为 API 化验收硬门槛。先跑 dry-run，确认输入与 case resolution 可用：

```powershell
.\.venv\Scripts\pjelly.exe eval ooc-benchmark `
  --character-id $CharacterId `
  --database-url $CliDbUrl `
  --provider stub `
  --dry-run `
  | Tee-Object -FilePath "$EvidenceDir\ooc-dry-run.txt"

.\.venv\Scripts\pjelly.exe eval retrieval-benchmark `
  --character-id $CharacterId `
  --database-url $CliDbUrl `
  --provider stub `
  --dry-run `
  --max-cases 3 `
  | Tee-Object -FilePath "$EvidenceDir\retrieval-dry-run.txt"
```

dry-run 通过后，跑持久化 smoke：

```powershell
.\.venv\Scripts\pjelly.exe eval ooc-benchmark `
  --character-id $CharacterId `
  --database-url $CliDbUrl `
  --provider stub `
  --test-suite "capability_ooc_$RunId" `
  | Tee-Object -FilePath "$EvidenceDir\ooc-run.txt"

.\.venv\Scripts\pjelly.exe eval retrieval-benchmark `
  --character-id $CharacterId `
  --database-url $CliDbUrl `
  --provider stub `
  --test-suite "capability_retrieval_$RunId" `
  --max-cases 3 `
  | Tee-Object -FilePath "$EvidenceDir\retrieval-run.txt"
```

通过标准：

- dry-run 显示不会创建 run
- 持久化 run 返回 run id
- totals 非零
- pass/fail metrics 被记录
- 如有 benchmark failure，按能力缺陷记录，不在验证现场扩 scope 修复

## 阶段 6：最终回归门

能力检查完成后再跑 focused regression 与 full pytest：

```powershell
.\.venv\Scripts\python -m pytest `
  tests/test_api_source_ingest_route.py `
  tests/test_api_character_creation_route.py `
  tests/test_api_character_persona_setup_route.py `
  tests/test_application_source_ingest_workflow.py `
  tests/test_application_character_creation_workflow.py `
  tests/test_application_character_persona_setup_workflow.py `
  tests/test_persona_setup_provider_trace_foundation.py `
  tests/test_turn_workflow_service.py `
  tests/test_roleplay_runtime.py `
  tests/test_memory_curator.py `
  tests/test_retrieval_benchmark.py `
  tests/test_evaluation_benchmark.py `
  | Tee-Object -FilePath "$EvidenceDir\focused-regression.txt"

.\.venv\Scripts\python -m pytest `
  | Tee-Object -FilePath "$EvidenceDir\full-pytest.txt"

git diff --check | Tee-Object -FilePath "$EvidenceDir\git-diff-check.txt"
git status --short --branch | Tee-Object -FilePath "$EvidenceDir\final-git-status.txt"
```

通过标准：

- focused regression 通过
- full pytest 通过
- `git diff --check` 无 whitespace error
- final status 干净，或只剩被忽略的 `tmp/` 验证证据

## 失败归类

| 类别 | 示例 | 处理方式 |
| --- | --- | --- |
| 能力缺陷 | route 链成功但 persona 不可用、claim 缺失、memory/canon 边界错误 | 建立后续 focused fix task |
| 契约回归 | 状态码错误、幂等 replay/conflict 错误、原始数据泄露、workflow/audit 链断裂 | 阻塞验收并修复 |
| 手顺或样本问题 | 样本文本无有效 chunk、ID 提取失败、dry-run 参数错误 | 修正手顺或样本后重跑 |
| provider/config 问题 | `env` provider 缺 key/model、网络 provider 失败 | 先用 `stub` 复验；`env` 问题单独记录 |
| 已知质量差距 | benchmark failure 但诊断稳定、可解释 | 记录为能力发现，不扩成平台开发 |

## 验收记录模板

```text
Batch 12 单角色 MVP API 能力验证

Commit:
Evidence directory:
API DB URL:
Optional CLI DB URL:

API 写链:
- source ingest:
- character create:
- persona setup:
- replay/conflict:
- redaction:

Optional CLI 端到端:
- source_work_id:
- character_id:
- persona_version_id:
- conversation_id:
- second turn:
- memory boundary:
- canon boundary:

Diagnostics:
- workflow/audit inspection:
- LLM traces:
- claims/evidence:
- raw text/provider payload leakage:

Optional benchmarks:
- OOC dry-run:
- OOC persisted run:
- retrieval dry-run:
- retrieval persisted run:

Regression:
- focused:
- full pytest:
- git diff/status:

Decision:
- accepted / blocked
- defects filed:
- deferred scope unchanged:
```
