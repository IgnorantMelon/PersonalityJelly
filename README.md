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
```

Find and inspect persisted conversations:

```powershell
.\.venv\Scripts\pjelly.exe list conversations
.\.venv\Scripts\pjelly.exe show conversation conv_... --messages 5
```

The default `demo` provider is still `stub`, so existing deterministic local demos do not need
network access or environment variables.
