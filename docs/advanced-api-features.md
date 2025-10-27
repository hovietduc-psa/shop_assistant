# Advanced API Features Documentation

This document describes the comprehensive advanced API features that have been implemented in Cycle 3 of the Shop Assistant AI system.

## Overview

The advanced API features provide enterprise-grade capabilities including batch operations, streaming responses, advanced monitoring, caching strategies, rate limiting, API versioning, and a sandbox environment for testing.

## Features Implemented

### 1. Batch Operations

**Location**: `app/core/api/batch_operations.py`

Enables processing multiple API requests in a single call for improved efficiency.

#### Key Features:
- Parallel and sequential execution modes
- Configurable timeout and error handling
- Detailed response tracking per item
- Support for different operation types (CRUD)

#### Usage Example:
```json
POST /api/v1/batch
{
  "items": [
    {
      "id": "req1",
      "operation": "read",
      "method": "GET",
      "path": "/shopify/products/123"
    },
    {
      "id": "req2",
      "operation": "create",
      "method": "POST",
      "path": "/orders",
      "data": {"customer_id": "456"}
    }
  ],
  "parallel": true,
  "continue_on_error": true
}
```

#### Response Format:
```json
{
  "batch_id": "batch_abc123",
  "status": "completed",
  "total_items": 2,
  "completed_items": 2,
  "failed_items": 0,
  "processing_time_ms": 250.5,
  "items": [...]
}
```

### 2. Streaming Responses & SSE

**Location**: `app/core/api/streaming.py`

Provides real-time data streaming and Server-Sent Events (SSE) capabilities.

#### Key Features:
- Server-Sent Events for real-time updates
- Chunked data streaming for large datasets
- Automatic keep-alive and connection management
- Support for multiple data formats (JSON, NDJSON, CSV)

#### SSE Endpoint Example:
```javascript
// Connect to SSE stream
const eventSource = new EventSource('/api/v1/stream/events');

eventSource.onmessage = function(event) {
  console.log('New event:', JSON.parse(event.data));
};

eventSource.addEventListener('product_update', function(event) {
  console.log('Product updated:', JSON.parse(event.data));
});
```

#### Streaming Data Example:
```http
GET /api/v1/stream/products?format=ndjson
```

### 3. Advanced Rate Limiting

**Location**: `app/core/api/rate_limiter.py`

Implements tiered rate limiting with quota management.

#### Rate Limit Tiers:
- **FREE**: 100 requests/minute, 10K requests/day
- **BASIC**: 300 requests/minute, 50K requests/day
- **PROFESSIONAL**: 1K requests/minute, 200K requests/day
- **ENTERPRISE**: 5K requests/minute, 1M requests/day
- **UNLIMITED**: No restrictions

#### Key Features:
- Redis-based distributed rate limiting
- Concurrent request limits
- Configurable quotas per client
- Automatic retry with exponential backoff

#### Rate Limit Headers:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
Retry-After: 60
```

### 4. API Caching Strategies

**Location**: `app/core/api/cache_manager.py`

Intelligent caching system with multiple strategies and invalidation methods.

#### Cache Strategies:
- **CACHE_FIRST**: Check cache first, fallback to network
- **NETWORK_FIRST**: Always fetch from network, update cache
- **CACHE_ONLY**: Serve only from cache
- **CACHE_THEN_NETWORK**: Return cache, then update in background

#### Key Features:
- Redis-based distributed caching
- Local cache fallback
- Tag-based cache invalidation
- TTL configuration per data type
- Compression for large payloads

#### Cache Decorator Example:
```python
@cache_response(ttl=300, tags=["products"], strategy=CacheStrategy.CACHE_FIRST)
async def get_product(product_id: str):
    # Function implementation
    pass
```

### 5. API Versioning

**Location**: `app/core/api/versioning.py`

Comprehensive API versioning strategy with backward compatibility.

#### Versioning Methods:
1. **URL Path**: `/api/v1/products`, `/api/v2/products`
2. **Header**: `Accept: application/vnd.api+json;version=1`
3. **Query Parameter**: `?version=v1`
4. **Custom Header**: `API-Version: v1`

#### Key Features:
- Automatic version detection
- Deprecation warnings
- Migration guidance
- Version compatibility transformation

#### Version Headers:
```http
API-Version: v1
API-Latest-Version: v2
API-Deprecation-Warning: true
API-Sunset-Date: 2024-12-31T00:00:00Z
```

### 6. Advanced Pagination

**Location**: `app/core/api/pagination.py`

Flexible pagination with multiple strategies and advanced filtering.

#### Pagination Types:
- **Offset**: `?offset=20&limit=10`
- **Page**: `?page=3&limit=10`
- **Cursor**: `?cursor=abc123&limit=10`

#### Advanced Filtering:
```json
{
  "filters": {
    "price": {"gte": 100, "lte": 500},
    "category": {"in": ["electronics", "books"]},
    "created_at": {"date_range": {"start": "2024-01-01", "end": "2024-01-31"}}
  },
  "sort": "price:desc",
  "fields": ["id", "title", "price"]
}
```

#### Cursor Pagination:
```json
{
  "items": [...],
  "cursor_info": {
    "has_next": true,
    "has_prev": true,
    "next_cursor": "abc123",
    "prev_cursor": "xyz789"
  }
}
```

### 7. Monitoring & Analytics

**Locations**:
- `app/core/api/monitoring.py` - Core monitoring system
- `app/api/v1/endpoints/monitoring/` - API endpoints

Comprehensive monitoring, metrics collection, and analytics.

#### Key Features:
- Real-time metrics collection
- Performance monitoring
- Error tracking and alerting
- Usage analytics
- Health checks

#### Health Check Endpoints:
```http
GET /api/v1/health/ping          # Basic health check
GET /api/v1/health/basic         # Service health
GET /api/v1/health/detailed      # Comprehensive health
GET /api/v1/health/component/db # Component-specific health
```

#### Metrics Endpoints:
```http
GET /api/v1/monitoring/metrics/overview     # Metrics overview
GET /api/v1/monitoring/metrics/performance   # Performance metrics
GET /api/v1/monitoring/metrics/realtime      # Real-time metrics
GET /api/v1/monitoring/analytics/usage       # Usage analytics
GET /api/v1/monitoring/analytics/dashboard    # Dashboard data
```

#### Alert System:
- Configurable alert rules
- Multiple alert levels (INFO, WARNING, ERROR, CRITICAL)
- Notification channels (email, webhook, Slack)
- Alert history and trends

### 8. API Sandbox

**Location**: `app/api/v1/endpoints/sandbox/playground.py`

Isolated testing environment for API exploration and testing.

#### Key Features:
- Mock data for testing
- Session-based isolation
- Request quota management
- Real-time request/response inspection
- No impact on production data

#### Sandbox Workflow:
1. Create session: `POST /api/v1/sandbox/session/create`
2. Execute requests: `POST /api/v1/sandbox/session/{id}/execute`
3. Inspect results: Response includes timing, headers, body
4. View mock data: `GET /api/v1/sandbox/session/{id}/mock-data`

#### Example Usage:
```bash
# Create sandbox session
curl -X POST /api/v1/sandbox/session/create \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user"}'

# Execute mock request
curl -X POST /api/v1/sandbox/session/{session_id}/execute \
  -H "Content-Type: application/json" \
  -d '{
    "method": "GET",
    "endpoint": "/api/v1/shopify/products/search",
    "mock_mode": true,
    "body": {"query": "test", "limit": 5}
  }'
```

## API Endpoints Summary

### Core Endpoints
- `/api/v1/health/*` - Health checks and monitoring
- `/api/v1/monitoring/*` - Metrics and analytics
- `/api/v1/sandbox/*` - Testing environment

### Advanced Features
- **Batch Operations**: `/api/v1/batch` (planned)
- **Streaming**: `/api/v1/stream/*` (planned)
- **Webhooks**: `/api/v1/webhooks/*` (Shopify integration)

### Business Endpoints
- **Shopify**: `/api/v1/shopify/*` - Products, orders, customers, etc.
- **AI**: `/api/v1/ai/*` - LLM services and intelligence
- **Chat**: `/api/v1/chat/*` - Conversational AI

## Configuration

### Environment Variables
```bash
# Advanced API Features
REDIS_URL=redis://localhost:6379/0
RATE_LIMIT_PER_MINUTE=60
CACHE_TTL_DEFAULT=300

# Monitoring
MONITORING_ENABLED=true
ALERT_WEBHOOK_URL=https://hooks.slack.com/...

# Sandbox
SANDBOX_ENABLED=true
SANDBOX_QUOTA_REQUESTS_PER_HOUR=100
```

### Rate Limiting Configuration
```python
# Custom rate limits per client
await rate_limiter.set_client_quota(client_id, ClientQuota(
    client_id="premium_client",
    tier=RateLimitTier.PROFESSIONAL,
    monthly_limit=1000000,
    features=["advanced_analytics", "batch_operations"]
))
```

### Cache Configuration
```python
# Cache with custom TTL and tags
await cache_manager.set(
    key="product_123",
    value=product_data,
    ttl=1800,  # 30 minutes
    tags=["products", "category_electronics"]
)
```

## Performance Optimizations

### 1. Caching Strategy
- **Read-heavy data**: 30-minute TTL with tag invalidation
- **User sessions**: 15-minute TTL
- **Search results**: 5-minute TTL
- **Configuration**: 24-hour TTL

### 2. Rate Limiting
- **Redis-based**: Distributed limiting across instances
- **Local fallback**: Cache-based limiting for Redis outages
- **Burst handling**: Token bucket algorithm for traffic spikes

### 3. Monitoring Overhead
- **Async metrics**: Non-blocking metric collection
- **Sampling**: Sample 1% of requests for detailed tracing
- **Batch updates**: Bulk metric updates to reduce overhead

## Security Considerations

### 1. API Keys & Authentication
- Tier-based access control
- API key rotation
- Request signing for sensitive operations

### 2. Rate Limiting
- DDoS protection
- Per-client quotas
- IP-based limiting

### 3. Sandbox Security
- Isolated mock data
- No production data access
- Session-based isolation

### 4. Monitoring Security
- Sensitive data masking in logs
- Audit trail for admin operations
- Secure alert notifications

## Best Practices

### 1. Using Batch Operations
- Group related operations
- Use parallel mode for independent requests
- Handle partial failures gracefully

### 2. Caching
- Use appropriate TTLs
- Implement cache invalidation
- Monitor cache hit rates

### 3. Rate Limiting
- Implement exponential backoff
- Handle rate limit errors gracefully
- Monitor quota usage

### 4. Monitoring
- Set up meaningful alerts
- Track business metrics
- Regular performance reviews

### 5. Versioning
- Plan deprecation timelines
- Provide migration guides
- Maintain backward compatibility

## Troubleshooting

### Common Issues

1. **Rate Limiting Errors**
   - Check `Retry-After` header
   - Implement backoff logic
   - Monitor quota usage

2. **Cache Misses**
   - Verify Redis connectivity
   - Check cache key generation
   - Review TTL settings

3. **Health Check Failures**
   - Check service dependencies
   - Review system resources
   - Monitor error logs

4. **Sandbox Issues**
   - Verify session validity
   - Check mock data availability
   - Review quota limits

### Debug Mode
```python
import logging
logging.getLogger("app.core.api").setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features
1. **GraphQL Federation**: Multi-service GraphQL support
2. **Event Streaming**: Apache Kafka integration
3. **Advanced Analytics**: Machine learning insights
4. **API Gateway**: Centralized API management
5. **Multi-tenant Support**: Organization isolation

### Scalability Improvements
- Horizontal scaling with load balancing
- Database sharding for large datasets
- Edge caching with CDN integration
- Microservices architecture evolution

---

This advanced API features implementation provides enterprise-grade capabilities that make the Shop Assistant AI system production-ready, scalable, and highly maintainable.