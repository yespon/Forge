# Models API

## Available Models

`GET /api/v1/integration/models`

Returns list of configured LLM models with their capabilities.

Response:
```json
{
  "models": [
    {
      "name": "claude-sonnet-4-6",
      "display_name": "Claude Sonnet 4.6",
      "supports_thinking": true,
      "supports_vision": true
    }
  ],
  "total": 1
}
```
