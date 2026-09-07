# Personality Jelly

最后更新：2026-09-07

> **项目已废弃：本项目因架构设计不合理而废弃，后续将尝试重新设计。**

本仓库保留现有代码与文档，供历史参考。

Personality Jelly 是一个 CLI 优先的小说角色大脑 MVP，用于将小说原文转化为有证据支撑的角色 canon，将这些 canon 编译为可运行的人格版本，并在对话中区分原作设定、用户记忆、关系记忆和临时剧情。

## 废弃前实现

废弃前的实现是一个本地 MVP，P1 加固、Batch 04 service foundation 与 Batch 05 read-only API adapter closeout 已完成验证，主要能力包括：

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

## 历史开发文档

原有开发指引保留在 [VIBE_CODING_GUIDE.md](./VIBE_CODING_GUIDE.md)，仅作为历史参考，其中的规划不再作为本项目的后续开发安排。

## Batch 11 Update

Batch 11 adds the first provider-backed write route:
`POST /characters/{character_id}/persona-setup-runs`.

The route is synchronous and thin over `personality_jelly.application`. It accepts only safe
provider source/model labels (`stub` or `env`), requires idempotency, stores workflow/audit/LLM
trace links, and returns only safe IDs, counts, statuses, retry hints, and redaction flags.
