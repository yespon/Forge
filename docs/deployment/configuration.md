# Configuration Reference

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| DATABASE_URL | Yes | - | PostgreSQL connection string |
| REDIS_URL | No | redis://localhost:6379 | Redis connection |
| ANTHROPIC_API_KEY | No | - | Anthropic API key |
| OPENAI_API_KEY | No | - | OpenAI API key |
| DEEPSEEK_API_KEY | No | - | DeepSeek API key |
| GOOGLE_API_KEY | No | - | Google AI API key |
| FORGE_SECRET_KEY | Yes | - | JWT signing secret |
| FORGE_APP_NAME | No | Forge | Application name |
| FORGE_LOG_LEVEL | No | info | Logging level |
| FORGE_CORS_ORIGINS | No | * | CORS allowed origins |

## YAML Config (config.yaml)

See [configuration.md](../configuration.md) for the full reference.
