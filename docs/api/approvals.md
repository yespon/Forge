# Approvals API

## Pending Approvals
`GET /api/v1/approvals/pending`

## Submit Decision
`POST /api/v1/approvals/:id`
```json
{
  "decision": "approve",
  "reason": "Looks safe",
  "user_id": "user-123"
}
```
