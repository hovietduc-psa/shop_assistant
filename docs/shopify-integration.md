# Shopify Integration

This document describes the comprehensive Shopify integration that has been implemented for the Shop Assistant AI system.

## Overview

The Shopify integration provides full access to Shopify store data through both REST and GraphQL APIs, enabling the AI assistant to:

- Search and retrieve product information
- Check inventory availability
- Compare products
- Get product recommendations
- Access order information
- Manage customer data
- Handle real-time webhook events
- Perform advanced analytics

## Architecture

### Components

1. **ShopifyClient** - Low-level API client handling HTTP requests, rate limiting, and error handling
2. **ShopifyService** - High-level service layer providing business operations
3. **GraphQLQueryBuilder** - Builder for creating complex GraphQL queries
4. **WebhookHandler** - Handler for processing Shopify webhooks
5. **Exception Handling** - Comprehensive error handling with retry logic
6. **API Endpoints** - RESTful API endpoints for all Shopify operations

### Data Models

Comprehensive Pydantic models for:
- Products with variants, images, and options
- Orders with line items and customer information
- Customers with addresses and order history
- Collections and product categorization
- Inventory levels and locations
- Webhook events and payloads

## Configuration

### Environment Variables

```bash
# Shopify Configuration
SHOPIFY_SHOP_DOMAIN=your-shop-name.myshopify.com
SHOPIFY_ACCESS_TOKEN=your-shopify-access-token
SHOPIFY_API_VERSION=2024-01
SHOPIFY_WEBHOOK_SECRET=your-shopify-webhook-secret
SHOPIFY_APP_SECRET=your-shopify-app-secret

# Shopify API Limits
SHOPIFY_RATE_LIMIT_PER_SECOND=2
SHOPIFY_BURST_LIMIT=40
SHOPIFY_BATCH_SIZE=250
```

### Shopify Private App Setup

1. Go to your Shopify admin dashboard
2. Navigate to Apps and sales channels → Develop apps
3. Create a new private app with appropriate permissions:
   - **Read products**: Access product information
   - **Read inventory**: Check inventory levels
   - **Read orders**: Access order data
   - **Read customers**: Access customer information
   - **Read product listings**: Access collections
4. Configure webhooks for real-time updates:
   - Product creation/update/deletion
   - Order status changes
   - Customer changes
   - Inventory updates

## API Endpoints

### Products

#### Search Products
```http
POST /api/v1/shopify/products/search
Content-Type: application/json

{
  "query": "search term",
  "limit": 20,
  "offset": 0,
  "sort_by": "RELEVANCE",
  "reverse": false
}
```

#### Get Product by ID
```http
GET /api/v1/shopify/products/{product_id}
```

#### Get Product by Handle
```http
GET /api/v1/shopify/products/handle/{handle}
```

#### Get Product Recommendations
```http
POST /api/v1/shopify/products/recommendations
Content-Type: application/json

{
  "product_id": "gid://shopify/Product/123456789",
  "limit": 5
}
```

#### Compare Products
```http
POST /api/v1/shopify/products/compare
Content-Type: application/json

{
  "product_ids": [
    "gid://shopify/Product/123456789",
    "gid://shopify/Product/987654321"
  ]
}
```

#### Check Inventory
```http
POST /api/v1/shopify/products/inventory/check
Content-Type: application/json

{
  "variant_ids": ["gid://shopify/ProductVariant/111111111"]
}
```

### Orders

#### Get Order Status
```http
GET /api/v1/shopify/orders/{order_id}/status
```

#### Get Customer Orders
```http
POST /api/v1/shopify/orders/customer
Content-Type: application/json

{
  "customer_id": "gid://shopify/Customer/123456789",
  "limit": 10
}
```

### Customers

#### Search Customers
```http
POST /api/v1/shopify/customers/search
Content-Type: application/json

{
  "query": "email@example.com",
  "limit": 10
}
```

### Collections

#### Get All Collections
```http
GET /api/v1/shopify/collections/?limit=20
```

#### Get Collection Products
```http
GET /api/v1/shopify/collections/{collection_id}
```

### Webhooks

#### Receive Webhook
```http
POST /api/v1/shopify/webhooks/receive
```

#### Webhook Health Check
```http
GET /api/v1/shopify/webhooks/health
```

## Error Handling

### Error Types

- **ShopifyAuthenticationError** - Invalid credentials or permissions
- **ShopifyRateLimitError** - API rate limit exceeded
- **ShopifyNotFoundError** - Resource not found
- **ShopifyValidationError** - Invalid request data
- **ShopifyServerError** - Shopify server errors
- **ShopifyTimeoutError** - Request timeout
- **ShopifyConnectionError** - Network connection issues

### Retry Logic

Automatic retry with exponential backoff for:
- Rate limit errors
- Server errors (5xx)
- Connection timeouts
- Network errors

### Rate Limiting

Built-in rate limiting respects Shopify's API limits:
- **REST API**: 2 requests per second, 40 burst requests
- **GraphQL API**: 1000 points per 60 seconds
- Automatic delay enforcement and burst management
- Graceful handling of limit resets

## Usage Examples

### Basic Product Search

```python
from app.integrations.shopify import ShopifyService

async with ShopifyService() as shopify:
    products, has_more = await shopify.search_products(
        query="blue t-shirt",
        limit=10,
        sort_by="PRICE",
        reverse=True
    )

    for product in products:
        print(f"Product: {product.title}")
        print(f"Price: ${product.price_range[0]} - ${product.price_range[1]}")
        print(f"In Stock: {product.in_stock}")
```

### Inventory Checking

```python
async with ShopifyService() as shopify:
    # Check single variant
    is_available = await shopify.is_variant_available(variant_id)

    # Check multiple variants
    inventory_levels = await shopify.check_inventory_availability([
        "gid://shopify/ProductVariant/111111111",
        "gid://shopify/ProductVariant/222222222"
    ])

    for variant_id, quantity in inventory_levels.items():
        print(f"Variant {variant_id}: {quantity} in stock")
```

### Product Recommendations

```python
async with ShopifyService() as shopify:
    recommendations = await shopify.get_product_recommendations(
        product_id="gid://shopify/Product/123456789",
        limit=5
    )

    for product in recommendations:
        print(f"Recommended: {product.title}")
```

### Order Status Tracking

```python
async with ShopifyService() as shopify:
    order_status = await shopify.get_order_status(order_id)

    print(f"Order #{order_status['order_number']}")
    print(f"Status: {order_status['financial_status']}")
    print(f"Fulfillment: {order_status['fulfillment_status']}")
    print(f"Total: ${order_status['total_price']} {order_status['currency']}")
```

## Webhook Processing

### Supported Webhook Topics

- `products/create` - New product creation
- `products/update` - Product updates
- `products/delete` - Product deletion
- `orders/create` - New orders
- `orders/updated` - Order updates
- `orders/cancelled` - Order cancellations
- `orders/fulfilled` - Order fulfillment
- `customers/create` - New customers
- `customers/update` - Customer updates
- `inventory_levels/update` - Inventory changes
- `collections/create/update/delete` - Collection changes
- `app/uninstalled` - App uninstallation

### Webhook Handler Setup

```python
from app.integrations.shopify.webhooks import WebhookHandler, ShopifyWebhookProcessor

# Create webhook handler
client = ShopifyClient()
webhook_handler = WebhookHandler(client)
processor = ShopifyWebhookProcessor(webhook_handler)

# Process incoming webhook
headers = request.headers
body = await request.body()

success = await webhook_handler.process_webhook(headers, body)
```

## Testing

### Running Tests

```bash
# Run Shopify integration tests
pytest tests/integrations/shopify/ -v

# Run with coverage
pytest tests/integrations/shopify/ --cov=app.integrations.shopify
```

### Test Configuration

Create a test environment with mock Shopify data:

```python
# conftest.py
@pytest.fixture
def mock_shopify_client():
    client = AsyncMock()
    # Configure mock responses
    return client
```

## Performance Considerations

### Caching Strategy

- **Product Data**: Cache frequently accessed products (TTL: 1 hour)
- **Inventory Levels**: Real-time caching with short TTL (5 minutes)
- **Collections**: Cache collection structures (TTL: 30 minutes)
- **Customer Data**: Cache customer profiles (TTL: 15 minutes)

### Batch Operations

- Use GraphQL batch queries for multiple products
- Implement efficient pagination for large datasets
- Leverage Shopify's bulk operations for data sync

### Connection Pooling

- HTTP client with connection pooling
- Configurable timeout settings
- Automatic retry with backoff

## Security Considerations

### API Key Management

- Store credentials securely using environment variables
- Implement API key rotation
- Use least-privilege access tokens

### Webhook Security

- Verify all incoming webhook signatures
- Implement IP whitelisting for Shopify webhooks
- Rate limit webhook processing endpoints

### Data Privacy

- Mask sensitive customer information in logs
- Implement audit logging for data access
- Follow GDPR/CCPA compliance requirements

## Monitoring and Analytics

### Key Metrics

- API response times and success rates
- Rate limit utilization
- Inventory accuracy
- Product recommendation performance
- Webhook processing success rates

### Logging

Comprehensive logging with structured data:
- Request/response details
- Error tracking with context
- Performance metrics
- Security events

### Health Checks

- Shopify API connectivity tests
- Webhook endpoint verification
- Database connection health
- Cache service availability

## Troubleshooting

### Common Issues

1. **Rate Limit Errors**
   - Check API usage patterns
   - Implement proper request batching
   - Monitor rate limit headers

2. **Authentication Failures**
   - Verify access token validity
   - Check app permissions
   - Ensure correct API version

3. **Webhook Failures**
   - Verify webhook signatures
   - Check endpoint availability
   - Review payload format changes

4. **Data Synchronization Issues**
   - Monitor webhook delivery
   - Implement data consistency checks
   - Handle race conditions properly

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger("app.integrations.shopify").setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features

1. **Advanced Analytics**
   - Sales trend analysis
   - Customer behavior insights
   - Inventory optimization

2. **Enhanced Recommendations**
   - Machine learning models
   - Personalized suggestions
   - Real-time personalization

3. **Omnichannel Support**
   - Point-of-sale integration
   - Social media commerce
   - Marketplace synchronization

4. **Automation Features**
   - Automated inventory management
   - Dynamic pricing rules
   - Customer segmentation

### Scalability Improvements

- Horizontal scaling with load balancing
- Database sharding for large stores
- Edge caching for global performance
- Event-driven architecture improvements

## Support

For technical support and questions:

1. Check the comprehensive API documentation
2. Review the troubleshooting guide
3. Monitor system health indicators
4. Contact development team for assistance

---

This Shopify integration provides a robust, scalable foundation for AI-powered e-commerce assistance with comprehensive error handling, security measures, and performance optimization.