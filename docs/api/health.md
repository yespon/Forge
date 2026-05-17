# Health Check API

## Overview

Health check endpoints provide status information for monitoring and Kubernetes probes.

## Endpoints

### GET /health

Returns comprehensive health status including database connectivity.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "development",
  "services": {
    "database": "healthy"
  }
}
```

**Status Values:**
- `healthy` - All services operational
- `degraded` - Some services unhealthy but API functional

**Service Status Values:**
- `healthy` - Service responding normally
- `unhealthy: <reason>` - Service has issues

---

### GET /api/v1/ready

Kubernetes readiness probe. Returns 200 when the application is ready to accept traffic.

**Response (200 OK):**
```json
{
  "ready": true
}
```

---

### GET /api/v1/live

Kubernetes liveness probe. Returns 200 when the application is running.

**Response (200 OK):**
```json
{
  "alive": true
}
```

## Usage Examples

### cURL

```bash
# Health check
curl http://localhost:8000/health

# Readiness probe
curl http://localhost:8000/api/v1/ready

# Liveness probe
curl http://localhost:8000/api/v1/live
```

### Kubernetes Probes

```yaml
livenessProbe:
  httpGet:
    path: /api/v1/live
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /api/v1/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

## Error Handling

All endpoints return JSON responses. In case of server errors:

**Response (500 Internal Server Error):**
```json
{
  "detail": "Internal server error"
}
```
