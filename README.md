# Personality Jelly

最后更新：2026-05-27

Personality Jelly 是一个 CLI 优先的小说角色大脑 MVP。项目目标是把小说原文转化为有证据支撑的角色 canon，将这些 canon 编译为可运行的人格版本，并在对话中严格区分原作设定、用户记忆、关系记忆和临时剧情。

## 项目目标

项目最终希望实现一套角色大脑系统，能够：

- 导入 TXT/Markdown 小说文本；
- 提取角色事实、人物关系、关键事件、语气特征和行为边界；
- 用原文证据校验重要 canon claim；
- 从 verified canon 编译可版本化的 persona；
- 让角色以稳定身份、语气和价值观与现实用户自然对话；
- 保存用户记忆和关系记忆，同时避免污染原作 canon；
- 暴露 critic report、LLM trace 和 benchmark 结果，用于质量控制。

长期路线是“方案三优先，方案五演进”：先做可靠的高价值角色大脑，再保留足够的数据边界，逐步演进到多作品、多角色、多用户的平台形态。

## 当前状态

当前实现是一个本地 MVP，P1 加固、Batch 04 service foundation 与 Batch 05 read-only API adapter closeout 已完成验证，主要能力包括：

- Python `>=3.12,<3.14`、`uv`、Pydantic v2、SQLAlchemy 2 和 SQLite；
- 可替换的 LLM 与 embedding provider 抽象；
- TXT/Markdown 原文导入与稳定 chunk 切分；
- 角色创建、Reader 抽取、Verifier 校验、证据引用和 persona 编译；
- 对话运行流程，包括 context assembly、roleplay generation、critic review、memory curation、memory guard 和 layered summary；
- OOC 与 retrieval benchmark，支持内置套件、源控 cases file、持久化运行记录、dry-run 诊断、failed-case 检查和回归资产；
- CLI 检查 conversation、context package、critic report、character、claim、memory、LLM trace、配置和数据库迁移，并提供 benchmark cases-file/export 诊断。
- 可复用的 application service layer，封装 bootstrap、provider role bundle、read-only inspection、turn workflow、summary/benchmark workflow、character persona setup 和 payload-only audit readiness，供 CLI 与 API adapter 共用。
- FastAPI 只读 API adapter，提供 health、conversation/context、character/claim/memory/source chunk、critic/failure/LLM trace/eval run 检查接口，并使用统一错误 envelope。

## 快速开始

创建虚拟环境并安装依赖：

```powershell
uv sync
```

在 `.env` 中配置本地密钥：

```env
PJ_LLM_API_KEY=replace-with-your-llm-api-key
PJ_EMBEDDING_API_KEY=replace-with-your-embedding-api-key
```

非密钥的 provider 默认配置放在被 git 忽略的 `pjelly.toml` 中。一个 OpenAI-compatible 配置示例：

```toml
[llm]
provider = "openai-compatible"
base_url = "https://api.openai.com/v1"
model = "gpt-4.1-mini"
timeout_seconds = 60
json_response_format = "json_schema"

[embedding]
provider = "openai-compatible"
base_url = "https://api.openai.com/v1"
model = "text-embedding-3-small"
timeout_seconds = 60
```

检查本地配置：

```powershell
.\.venv\Scripts\pjelly.exe config show
.\.venv\Scripts\pjelly.exe config check
```

运行一次 demo 对话流水线：

```powershell
.\.venv\Scripts\pjelly.exe demo .\path\to\novel.md --character 林霜 --provider env
```

继续已有 conversation：

```powershell
.\.venv\Scripts\pjelly.exe turn conv_... --message "我们继续聊。" --provider env
```

运行 benchmark：

```powershell
.\.venv\Scripts\pjelly.exe eval ooc-benchmark --character-id char_...
.\.venv\Scripts\pjelly.exe eval retrieval-benchmark --character-id char_... --dry-run
```

## 开发计划

当前阶段：方案三 MVP 的 P2 service foundation、Batch 05 read-only API adapter、Batch 06 API write readiness、Batch 07 API Write Foundation、Batch 08 API Workflow Persistence Foundation 与 Batch 09 provider-backed API planning 已完成 closeout 验证。

- P1：已完成 semantic tracing、benchmark cases、layered summary 消费、retrieval diagnostics 和 CLI diagnostics 加固。
- P2：已完成 FastAPI/service boundary 规划、多作品/多角色数据边界审计、user/workspace/audit 概念设计，以及 CLI/API shared service foundation。
- Batch 05：已引入只读 API adapter，让 FastAPI 作为 `personality_jelly.application` 之上的薄 HTTP 层，暴露 conversation、context package、character、claim、memory、critic report、failure case、LLM trace 和 eval run 等检查接口，并通过 API/CLI focused 与 full pytest closeout。
- Batch 06：已收束延期 API 议题的实现前契约，包括写流程边界、actor/auth/audit、API redaction、分页/filter 约定、trace/workflow correlation，以及下一批次实施建议；该批次不实现写接口。
- Batch 07：已实现最小安全的本地写入基础：redaction/correlation/actor context、`POST /conversations`，以及 manual memory review/edit/archive；不包含 provider-backed 写流程、persistent audit、auth/workspace、部署或 UI。
- Batch 08：已实现 API workflow persistence foundation：persistent audit events、workflow_runs/workflow_run_links、LLM trace correlation fields、idempotency replay/conflict、provider failure/partial-persistence contracts，以及只读 audit/workflow inspection routes；仍不包含 provider-backed 写流程、source ingest/character/persona/turn/summary/benchmark 写接口、auth/workspace、部署或 UI。
- Batch 09：已完成 provider-backed API planning，明确 source ingest、character/persona setup 契约、共享 write contract matrix 与 Batch 10 实施计划；未新增 provider-backed 路由或 source 行为变更。
- Batch 10：下一实施批次先实现 `POST /source-works`，再实现确定性 `POST /characters`；provider-backed persona setup 延后。任何 provider-backed route 都必须继续复用 Batch 08 的 audit/workflow/idempotency/failure contract。

## 开发指南

所有面向编码智能体的指引、实现规则、已采纳架构选择、工作流约束和当前非目标，都集中维护在 [VIBE_CODING_GUIDE.md](./VIBE_CODING_GUIDE.md)。本 README 只用于项目介绍、快速开始和简要开发计划展示。
## Batch 10 Update

Batch 10 source/character API has been implemented and verified on `dev`. The next staged batch is
provider-backed persona setup only (`POST /characters/{character_id}/persona-setup-runs`).
