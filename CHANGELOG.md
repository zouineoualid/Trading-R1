# Changelog

## Unreleased

- A ChatGPT subscription as a model (`chatgpt`): sign in once with the Codex CLI (`codex login`)
  and the app uses that login, refreshing it as needed. No API key.
- More hosted providers, each on its API key: Ollama Cloud, OpenRouter, Mistral, DeepSeek, xAI,
  Groq, Together and Cerebras.
- More local runtimes: LM Studio and llama.cpp beside Ollama and vLLM, found on their default
  ports and using the model loaded (`auto`); `TR1_OLLAMA_MODEL=auto` takes the first model pulled.
- `trading-r1 models`: every provider, whether it is set up and answering, and the fix when not.
- The model picker explains a sign-in (ChatGPT) instead of asking for a key.

## [0.1.0] (2026-11-04)

First official release of Trading-R1, the terminal for financial research and analysis by
[Tauric Research](https://tauric.ai/).

- Ask a question, and the agent pulls market data, reads the web, runs the numbers and writes a
  cited report.
- 68 tools and 17 workflow skills: company, market and macro data; valuation, risk, portfolio,
  statistics, fixed income and derivatives.
- Models: Tauric, OpenAI, Anthropic, Gemini, vLLM and Ollama.
- Reports as PDF, Markdown or an HTML page, sent to Telegram, email or a folder.
- Scheduled reports, a background service for Linux and macOS, and Telegram replies.
- Session sync to your Tauric account, on by default, and `SKILL.md` workflows of your own.
