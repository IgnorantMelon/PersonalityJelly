# Personality Jelly

Personality Jelly is an MVP for building and running high-fidelity AI character brains from novel text.

The first implementation phase focuses on stable engineering boundaries:

- canon and user memory separation
- source evidence tracking
- persona versioning
- replaceable LLM provider abstraction
- SQLite-first storage that can migrate toward PostgreSQL

## LLM provider

The real provider entrypoint is OpenAI-compatible and configured with environment variables:

```powershell
$env:PJ_LLM_PROVIDER = "openai-compatible"
$env:PJ_LLM_BASE_URL = "https://api.openai.com/v1"
$env:PJ_LLM_API_KEY = "<api-key>"
$env:PJ_LLM_MODEL = "<chat-model>"
```

Use `personality_jelly.llm.build_llm_provider(Settings())` to construct the configured provider.

Run the end-to-end CLI with the configured provider:

```powershell
.\.venv\Scripts\pjelly.exe demo .\path\to\novel.md --character 林霜 --provider env
```

The CLI uses `PJ_DATABASE_URL` by default, falling back to `sqlite:///personality_jelly.db`.
Use `--memory-db` for a one-shot isolated run, or `--reuse-existing` to reuse matching source,
character, persona, user, and conversation rows in a persistent database.

Continue an existing conversation with one more user turn:

```powershell
.\.venv\Scripts\pjelly.exe turn conv_... --message "我们继续聊。" --provider env
.\.venv\Scripts\pjelly.exe turn conv_... --message "你是谁？" --retry-on-critic
```

Conversation turns classify interaction mode automatically. Override it when needed:

```powershell
.\.venv\Scripts\pjelly.exe turn conv_... --message "我们一起写一段新剧情。" --interaction-mode co_creation
```

Find and inspect persisted conversations:

```powershell
.\.venv\Scripts\pjelly.exe list conversations
.\.venv\Scripts\pjelly.exe show conversation conv_... --messages 5
.\.venv\Scripts\pjelly.exe show context-package ctx_...
.\.venv\Scripts\pjelly.exe show critic-report cr_...
```

Inspect character profile assets and canon claims:

```powershell
.\.venv\Scripts\pjelly.exe show character char_...
.\.venv\Scripts\pjelly.exe list claims --character-id char_... --status verified
```

Summarize a conversation into its stored context summary:

```powershell
.\.venv\Scripts\pjelly.exe summarize conversation conv_... --messages 20
```

Run the MVP OOC and canon-pollution benchmark against an existing character:

```powershell
.\.venv\Scripts\pjelly.exe eval ooc-benchmark --character-id char_...
```

Inspect, correct, or archive user memories:

```powershell
.\.venv\Scripts\pjelly.exe list memories --user-id user_... --character-id char_...
.\.venv\Scripts\pjelly.exe edit memory mem_... --content "用户喜欢夜里写作。"
.\.venv\Scripts\pjelly.exe archive memory mem_...
```

The default `demo` provider is still `stub`, so existing deterministic local demos do not need
network access or environment variables.
