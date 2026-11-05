# Trading-R1 manual

Each command takes `--help`, which also lists the less common commands and options.

## Commands

| Command | Does |
|---|---|
| `trading-r1 [QUESTION]` | Open the terminal. `--profile NAME`, `--mode MODE` |
| `trading-r1 serve` | Run the backend alone, in the foreground |
| `trading-r1 export ID` | Write a report. `--format pdf\|md\|html`, `-o FILE`, `--send CHANNELS` |
| `trading-r1 sessions list`, `delete ID` | Your sessions; delete one here and its copy in your account |
| `trading-r1 channels add KIND`, `list`, `test NAME`, `remove NAME` | Your channels |
| `trading-r1 jobs add`, `list`, `run ID`, `runs ID`, `remove ID` | Your scheduled reports, and what each run did |
| `trading-r1 secrets set NAME`, `list`, `delete NAME` | Stored keys, passwords and tokens |
| `trading-r1 daemon install`, `status`, `logs`, `uninstall` | The background service |
| `trading-r1 sync status`, `on`, `off`, `pull [ID]` | Session sync; `pull` gets a session back from your account |

`sessions`, `jobs` and most of `sync` need a running backend: the terminal's, the service, or
`trading-r1 serve`.

## Settings

Open **Settings** from the palette.

| Setting | Does | Default |
|---|---|---|
| Verification | Check the report's figures against the records and recompute the worked-out ones. Takes about twice the time and tokens. | off |
| Source review | Check the report against its sources. Ignored when Verification is on. | off |
| Default mode | The mode the app opens in. | auto |
| Auto-compact | Compact the context before it fills the model's window. | on |
| Show reasoning | The model's thinking in the transcript. | on |
| Tool details | `brief` shows a tool call's values; `full` shows every argument by name. | brief |
| Side panel | The plan, data records and sources beside the transcript. | on |
| Also save as Markdown, HTML page | Files saved beside a report's PDF. | Markdown on, page off |
| Session sync | Copy your sessions to your Tauric account. | on |
| Remembered notes… | View or delete what the agent has noted about you. | |

## Reports, channels and jobs

`TR1_REPORTS_DIR` changes the reports folder. Reports the PDF font cannot draw, such as Chinese or
Japanese, become an HTML page.

```bash
trading-r1 channels add telegram
trading-r1 channels add email --preset gmail --to me@example.com   # asks for the app password
trading-r1 channels add folder --path briefs
trading-r1 channels test telegram
trading-r1 export SESSION_ID --format pdf -o report.pdf            # or md, html; --turn N
trading-r1 export SESSION_ID --send telegram,email
```

For Gmail, turn on 2-Step Verification and make an app password in your Google account. Other
providers take `--host`, `--port` and `--username`.

```bash
trading-r1 jobs add --name "Morning brief" --every weekdays --time 08:00 --tz America/New_York \
    --prompt "What moved my watchlist overnight? NVDA, AAPL, MSFT." --deliver email,telegram
trading-r1 jobs add --name "Weekly review" --every week --weekday fri --time 17:00 \
    --prompt "Review my portfolio's week." --deliver email
trading-r1 jobs list
```

`--cron` takes any five-field expression, and `--at 2027-01-04T08:00:00-05:00` runs once.
`--profile` and `--mode` pin the model and mode. Jobs run unattended, so they cannot ask you a
question.

## Session sync

Sync is on by default with a Tauric key, whichever model you use: your sessions, with their
questions, model requests and responses and tool results, are copied to your account at
`api.tauric.ai`. Turn it off under *Settings > Session sync* or with `trading-r1 sync off`.

## Your data and keys

- `trading-r1 secrets set` and the key forms store keys in `~/.trading-r1/credentials.json`, and
  `trading-r1 daemon install` copies them to `~/.trading-r1/daemon.env`. Only you can read these
  files, but your own processes and any backup tool that copies the folder can too.
- Sessions, notes and settings are plain files under `~/.trading-r1/`.
- The backend listens on `127.0.0.1` by default, and every route but its liveness check needs a
  bearer token, kept in a file only you can read. Do not expose it to a network you do not trust.
- The agent can read web pages and call the data API on your behalf, and sends what it reads to
  the model you selected.
- Reports go to your channels through those services (your mail provider, Telegram). With `reply`
  on, the private chat paired with your Telegram bot can ask the agent questions.

## Configuration

Keys are read from the environment, then from `~/.trading-r1/credentials.json`. Settings, channels
and model profiles are in the same folder (`TR1_HOME` moves it).

| Variable | Does |
|---|---|
| `TR1_PROFILE` | The model to start on (`trading-r1 models` lists them) |
| `TR1_REPORTS_DIR` | The reports folder |
| `TR1_SKILLS_DIR` | One more folder of skills |
| `TR1_PORT` | The backend's port |
| `TR1_VLLM_BASE_URL` | Your vLLM server's address, such as `http://gpu-box:8000/v1` |
| `TR1_<NAME>_BASE_URL`, `TR1_<NAME>_MODEL`, `TR1_<NAME>_API_KEY` | One model's address, model and key |
| `CHATGPT_ACCESS_TOKEN`, `CHATGPT_ACCOUNT_ID` | A ChatGPT token, instead of the Codex CLI's login |
| `CODEX_HOME` | Where the Codex CLI keeps its login (default `~/.codex`) |
| `TR1_CHATGPT_ORIGINATOR` | The client name sent to the ChatGPT backend (default `codex_cli_rs`) |

To add a model, give it a profile in `~/.trading-r1/providers.json`:

```json
{"profiles": {"my-qwen": {"extends": "vllm", "base_url": "http://gpu-box:9000/v1",
                          "reader_profile": "my-qwen"}}}
```

Profiles with their own address send no key unless they name one (`"api_key_env": "MY_KEY"`). Those
that extend a hosted profile keep its key, so name the key they should send.

### Providers

`trading-r1 models` lists every provider: whether it is set up (a key, a sign-in, or a server
that answers), what it serves, and the fix when it is not ready. The hosted providers and the
variable each one needs:

| Provider | Key | Models (change with `TR1_<NAME>_MODEL`) |
|---|---|---|
| `tauric` | `TAURIC_API_KEY` | `tauric` |
| `gpt` | `OPENAI_API_KEY` | `gpt-6.1-sol`, reader `gpt-6-luna` |
| `chatgpt` | a ChatGPT plan: `codex login` | `gpt-6.1-sol` |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-5-5`, reader `claude-haiku-5-5` |
| `gemini` | `GEMINI_API_KEY` | `gemini-3.8-flash` |
| `ollama-cloud` | `OLLAMA_API_KEY` (ollama.com) | `gpt-oss:120b` |
| `openrouter` | `OPENROUTER_API_KEY` | `openai/gpt-oss-120b`, reader `openai/gpt-oss-20b` |
| `mistral` | `MISTRAL_API_KEY` | `mistral-large-latest`, reader `mistral-small-latest` |
| `deepseek` | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| `xai` | `XAI_API_KEY` | `grok-4-1-fast-reasoning`, reader `grok-4-1-fast-non-reasoning` |
| `groq` | `GROQ_API_KEY` | `openai/gpt-oss-120b`, reader `openai/gpt-oss-20b` |
| `together` | `TOGETHER_API_KEY` | `openai/gpt-oss-120b` |
| `cerebras` | `CEREBRAS_API_KEY` | `gpt-oss-120b` |

The reader is the model that reads web pages; `TR1_<NAME>_READER_MODEL` changes it where a
provider has one of its own (`gpt-reader`, `mistral-reader`, ...). A provider's model names are
the provider's: check its model list when a call says the model is unknown.

**ChatGPT.** A ChatGPT subscription has no API key. Install the Codex CLI
(`npm install -g @openai/codex`), run `codex login`, and `chatgpt` is set up: Trading-R1 reads
the login Codex keeps in `~/.codex/auth.json`, refreshes the token when it expires and writes the
new one back, so Codex keeps working too. On a machine without a browser, copy that file over, or
set `CHATGPT_ACCESS_TOKEN` (and `CHATGPT_ACCOUNT_ID`) by hand. The ChatGPT backend is not a
documented API and serves the models the plan allows; usage counts against the plan's limits. A
Codex that keeps its login in the system keyring rather than the file is not found: set
`cli_auth_credentials_store = "file"` in `~/.codex/config.toml` and sign in again.

**Claude and Gemini.** Anthropic's terms keep a Claude Pro or Max subscription to Claude Code
and the Claude apps, so `anthropic` takes an API key from the Anthropic console. A Google AI plan
has no API; `gemini` takes a Gemini API key, which has a free tier.

**Local models.** `ollama`, `lmstudio` and `llamacpp` expect the app on its default port
(`:11434`, `:1234`, `:8080`); `vllm` expects `:8000`. `lmstudio` and `llamacpp` use the model
loaded in the app (`auto`: the first the server lists); `ollama` expects `gemma4:e4b` pulled, or
the model in `TR1_OLLAMA_MODEL` (`auto` takes the first pulled). `TR1_<NAME>_BASE_URL` points one
at another machine. A local model needs to call tools and answer in JSON; a small or old one may
not manage the research loop. For any other OpenAI-compatible server (LocalAI, Jan, a cloud
GPU), add a profile:

```json
{"profiles": {"jan": {"extends": "lmstudio", "base_url": "http://127.0.0.1:1337/v1",
                      "reader_profile": "jan"}}}
```

## Adding a skill

Skills are `SKILL.md` files that tell the agent how to do a kind of work with its tools. Put one in
`./skills/my-recipe/SKILL.md` under the folder you start from, or in `TR1_SKILLS_DIR`. Skills with a
built-in's name replace it.
