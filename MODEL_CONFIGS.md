# Model Configurations

10 providers configured: Anthropic, OpenAI, DeepSeek, Google, Ollama, vLLM, xAI Grok, MiniMax

See config.yaml for examples.


## Provider Capability Matrix

| Provider | Thinking | Vision | Reasoning Effort | Self-Hosted | Best Use |
|----------|----------|--------|------------------|-------------|----------|
| Anthropic | ✅ | ✅ | ❌ | ❌ | General, coding, reasoning |
| OpenAI | ✅ | ✅ | ✅ | ❌ | Vision, structured output |
| DeepSeek | ✅ | ❌ | ❌ | ❌ | Chinese, low-cost reasoning |
| Google | ✅ | ✅ | ❌ | ❌ | Multimodal, fast response |
| Ollama | ❌ | depends | ❌ | ✅ | Local/private workloads |
| vLLM | depends | depends | depends | ✅ | Self-hosted scale |
| Grok | ✅ | ✅ | ✅ | ❌ | OpenAI-compatible reasoning |
| MiniMax | ✅ | ✅ | ✅ | ❌ | Multilingual / compatible APIs |

## Tuning Guidance

- Use `temperature=0.0~0.2` for deterministic coding / extraction.
- Use `temperature=0.6~0.9` for brainstorming / creative tasks.
- Prefer `thinking_budget_tokens` for Anthropic-style long reasoning workloads.
- Prefer `reasoning_effort` for OpenAI-compatible reasoning models.
- Use `api_base` for self-hosted OpenAI-compatible endpoints (vLLM, MiniMax-like gateways, xAI-compatible proxies).
