# MCP Integration

## Configuration
Edit `extensions_config.json` to configure MCP servers:

```json
{
  "mcpServers": {
    "mcpServers": {
    "github": {
      "enabled": true,
      "type": "stdio",
      "command": "npx",
      "args": ["@anthropic-ai/claude-code", "--mcp"]
    }
  }
}
```

## Supported Transports
- **stdio**: Subprocess stdin/stdout
- **sse**: HTTP Server-Sent Events

## OAuth Support
Configure OAuth for protected servers under each server's `oauth` key.
