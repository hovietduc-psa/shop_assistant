"""
OpenAPI/Swagger documentation configuration for Shop Assistant AI.
"""

from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, Response
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from datetime import datetime

from app.core.config import settings


class OpenAPIDocumentation:
    """OpenAPI documentation generator and manager."""

    def __init__(self, app: FastAPI):
        self.app = app
        self.custom_schemas = {}
        self.custom_examples = {}
        self.custom_tags = {}

    def setup_openapi(self):
        """Setup custom OpenAPI configuration."""
        def custom_openapi():
            if self.app.openapi_schema:
                return self.app.openapi_schema

            openapi_schema = get_openapi(
                title="Shop Assistant AI API",
                version="3.0.0",
                description=self._get_api_description(),
                routes=self.app.routes,
                servers=self._get_servers(),
                tags=self._get_api_tags()
            )

            # Add custom schemas
            openapi_schema["components"]["schemas"].update(self.custom_schemas)

            # Add security schemes
            openapi_schema["components"]["securitySchemes"] = {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                },
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key"
                }
            }

            # Add global security
            openapi_schema["security"] = [{"BearerAuth": []}, {"ApiKeyAuth": []}]

            # Add examples
            self._add_examples(openapi_schema)

            # Add extensions
            openapi_schema["x-api-version"] = "3.0.0"
            openapi_schema["x-contact"] = {
                "name": "API Support",
                "email": "api-support@shopassistant.com",
                "url": "https://shopassistant.com/support"
            }
            openapi_schema["x-license"] = {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT"
            }

            self.app.openapi_schema = openapi_schema
            return self.app.openapi_schema

        self.app.openapi = custom_openapi

    def _get_api_description(self) -> str:
        """Get comprehensive API description."""
        return """
# Shop Assistant AI API

The Shop Assistant AI API provides a comprehensive conversational AI platform for e-commerce businesses.

## Features

- **Natural Language Understanding**: Advanced intent classification, entity extraction, and sentiment analysis
- **Intelligent Dialogue Management**: Context-aware conversations with state management
- **Quality Assessment**: Real-time conversation quality monitoring and improvement suggestions
- **Memory Management**: Persistent conversation memory with semantic search
- **Testing Framework**: Comprehensive dialogue testing and validation tools
- **Analytics & Insights**: Detailed conversation analytics and reporting

## Authentication

The API uses JWT Bearer tokens for authentication. Include your token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

Alternatively, you can use an API key:

```
X-API-Key: <your-api-key>
```

## Rate Limiting

API requests are rate-limited to ensure fair usage. Rate limit headers are included in all responses:

- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Time when the rate limit window resets

## Error Handling

The API uses standard HTTP status codes and returns detailed error information:

```json
{
  "error": "Error Type",
  "message": "Detailed error message",
  "details": {...},
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## SDKs and Libraries

Official SDKs are available for:
- Python
- JavaScript/TypeScript
- Ruby
- Java
- Go

Visit our [Developer Portal](https://developers.shopassistant.com) for more information.
        """.strip()

    def _get_servers(self) -> List[Dict[str, str]]:
        """Get API server configurations."""
        return [
            {
                "url": f"http://{settings.API_HOST}:{settings.API_PORT}",
                "description": "Development server"
            },
            {
                "url": "https://api.shopassistant.com/v1",
                "description": "Production server"
            },
            {
                "url": "https://staging-api.shopassistant.com/v1",
                "description": "Staging server"
            }
        ]

    def _get_api_tags(self) -> List[Dict[str, Any]]:
        """Get API endpoint tags."""
        return [
            {
                "name": "Chat",
                "description": "Real-time chat and conversation management"
            },
            {
                "name": "NLU",
                "description": "Natural Language Understanding services"
            },
            {
                "name": "Dialogue",
                "description": "Dialogue management and state control"
            },
            {
                "name": "Quality",
                "description": "Conversation quality assessment and analytics"
            },
            {
                "name": "Memory",
                "description": "Conversation memory and search functionality"
            },
            {
                "name": "Testing",
                "description": "API testing and validation tools"
            },
            {
                "name": "Health",
                "description": "System health and monitoring endpoints"
            },
            {
                "name": "Authentication",
                "description": "User authentication and authorization"
            }
        ]

    def _add_examples(self, openapi_schema: Dict[str, Any]):
        """Add request/response examples to OpenAPI schema."""
        examples = {
            "SendMessageRequest": {
                "value": {
                    "message": "I need help tracking my order #12345",
                    "conversation_id": "conv_abc123"
                }
            },
            "SendMessageResponse": {
                "value": {
                    "id": "msg_def456",
                    "conversation_id": "conv_abc123",
                    "message": "I'll help you track your order #12345. Let me check the current status for you.",
                    "sender": "assistant",
                    "timestamp": "2024-01-01T12:00:00Z",
                    "metadata": {
                        "model": "gpt-4",
                        "dialogue_state": "understanding",
                        "confidence": 0.95,
                        "intent": "order_status",
                        "entities": [{"type": "order_number", "value": "12345"}],
                        "sentiment": "neutral"
                    }
                }
            },
            "ClassifyIntentRequest": {
                "value": {
                    "text": "I want to return my purchase"
                }
            },
            "ClassifyIntentResponse": {
                "value": {
                    "intent": "return_request",
                    "confidence": 0.92,
                    "alternatives": [
                        {"intent": "complaint", "confidence": 0.05},
                        {"intent": "support_request", "confidence": 0.03}
                    ]
                }
            },
            "ErrorResponse": {
                "value": {
                    "error": "ValidationError",
                    "message": "Invalid request format",
                    "details": {
                        "field": "message",
                        "issue": "Field is required"
                    },
                    "timestamp": "2024-01-01T12:00:00Z"
                }
            }
        }

        # Add examples to relevant paths
        if "paths" in openapi_schema:
            for path, path_item in openapi_schema["paths"].items():
                for method, operation in path_item.items():
                    if method in ["get", "post", "put", "delete", "patch"]:
                        # Add examples based on operation
                        self._add_operation_examples(operation, examples)

    def _add_operation_examples(self, operation: Dict[str, Any], examples: Dict[str, Any]):
        """Add examples to a specific operation."""
        operation_id = operation.get("operationId", "")

        # Add request examples
        if "requestBody" in operation and "content" in operation["requestBody"]:
            for content_type in operation["requestBody"]["content"]:
                if "application/json" in content_type:
                    example_key = self._get_example_key_for_operation(operation_id, "request")
                    if example_key in examples:
                        operation["requestBody"]["content"]["application/json"]["example"] = examples[example_key]

        # Add response examples
        if "responses" in operation:
            for status_code, response in operation["responses"].items():
                if "content" in response and "application/json" in response["content"]:
                    example_key = self._get_example_key_for_operation(operation_id, "response", status_code)
                    if example_key in examples:
                        response["content"]["application/json"]["example"] = examples[example_key]
                    elif "ErrorResponse" in examples and status_code.startswith("4"):
                        response["content"]["application/json"]["example"] = examples["ErrorResponse"]

    def _get_example_key_for_operation(self, operation_id: str, example_type: str, status_code: str = "200") -> str:
        """Get example key for an operation."""
        operation_mappings = {
            "send_message": {
                "request": "SendMessageRequest",
                "response": "SendMessageResponse"
            },
            "classify_intent": {
                "request": "ClassifyIntentRequest",
                "response": "ClassifyIntentResponse"
            },
            "extract_entities": {
                "request": "ExtractEntitiesRequest",
                "response": "ExtractEntitiesResponse"
            },
            "analyze_sentiment": {
                "request": "AnalyzeSentimentRequest",
                "response": "AnalyzeSentimentResponse"
            }
        }

        if operation_id in operation_mappings:
            return operation_mappings[operation_id].get(example_type, "")

        return ""

    def add_custom_schema(self, name: str, schema: Dict[str, Any]):
        """Add custom schema definition."""
        self.custom_schemas[name] = schema

    def add_custom_tag(self, name: str, description: str, external_docs: Optional[Dict[str, str]] = None):
        """Add custom API tag."""
        tag_data = {"name": name, "description": description}
        if external_docs:
            tag_data["externalDocs"] = external_docs
        self.custom_tags[name] = tag_data


class APIDocumentationGenerator:
    """Generate comprehensive API documentation."""

    def __init__(self):
        self.sections = {}

    def generate_postman_collection(self, openapi_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Postman collection from OpenAPI schema."""
        collection = {
            "info": {
                "name": "Shop Assistant AI API",
                "description": openapi_schema.get("info", {}).get("description", ""),
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "auth": {
                "type": "bearer",
                "bearer": [
                    {
                        "key": "token",
                        "value": "{{access_token}}",
                        "type": "string"
                    }
                ]
            },
            "variable": [
                {
                    "key": "base_url",
                    "value": "{{base_url}}",
                    "type": "string"
                },
                {
                    "key": "access_token",
                    "value": "",
                    "type": "string"
                }
            ],
            "item": []
        }

        # Convert OpenAPI paths to Postman items
        if "paths" in openapi_schema:
            for path, path_item in openapi_schema["paths"].items():
                folder = self._create_postman_folder(path, path_item, openapi_schema)
                collection["item"].append(folder)

        return collection

    def _create_postman_folder(self, path: str, path_item: Dict[str, Any], openapi_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Create Postman folder for a path."""
        folder = {
            "name": path,
            "item": [],
            "event": [
                {
                    "listen": "prerequest",
                    "script": {
                        "exec": [
                            "// Set common headers",
                            "pm.request.headers.add({",
                            "    key: 'Content-Type',",
                            "    value: 'application/json'",
                            "});"
                        ],
                        "type": "text/javascript"
                    }
                }
            ]
        }

        for method, operation in path_item.items():
            if method in ["get", "post", "put", "delete", "patch"]:
                request = self._create_postman_request(method, path, operation, openapi_schema)
                folder["item"].append(request)

        return folder

    def _create_postman_request(self, method: str, path: str, operation: Dict[str, Any], openapi_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Create Postman request from operation."""
        request = {
            "name": operation.get("summary", f"{method.upper()} {path}"),
            "request": {
                "method": method.upper(),
                "header": [],
                "url": {
                    "raw": "{{base_url}}" + path,
                    "host": ["{{base_url}}"],
                    "path": path.strip("/").split("/")
                }
            },
            "response": []
        }

        # Add request body if present
        if "requestBody" in operation and "content" in operation["requestBody"]:
            if "application/json" in operation["requestBody"]["content"]:
                content = operation["requestBody"]["content"]["application/json"]
                if "example" in content:
                    request["request"]["body"] = {
                        "mode": "raw",
                        "raw": json.dumps(content["example"], indent=2),
                        "options": {
                            "raw": {
                                "language": "json"
                            }
                        }
                    }

        # Add parameters
        if "parameters" in operation:
            for param in operation["parameters"]:
                param_item = {
                    "key": param["name"],
                    "value": f"{{{param['name']}}}",
                    "type": "text"
                }

                if param["in"] == "query":
                    request["request"]["url"].setdefault("query", []).append(param_item)
                elif param["in"] == "path":
                    # Path parameters are already in the URL
                    pass

        # Add response examples
        if "responses" in operation:
            for status_code, response in operation["responses"].items():
                if "content" in response and "application/json" in response["content"]:
                    content = response["content"]["application/json"]
                    if "example" in content:
                        response_example = {
                            "name": f"Example {status_code}",
                            "originalRequest": request["request"].copy(),
                            "status": status_code,
                            "code": int(status_code),
                            "header": [
                                {
                                    "key": "Content-Type",
                                    "value": "application/json"
                                }
                            ],
                            "body": json.dumps(content["example"], indent=2)
                        }
                        request["response"].append(response_example)

        return request

    def generate_markdown_documentation(self, openapi_schema: Dict[str, Any]) -> str:
        """Generate Markdown documentation from OpenAPI schema."""
        markdown = []

        # Title and description
        info = openapi_schema.get("info", {})
        markdown.append(f"# {info.get('title', 'API Documentation')}")
        markdown.append("")
        markdown.append(info.get("description", ""))
        markdown.append("")

        # Table of contents
        markdown.append("## Table of Contents")
        markdown.append("")
        if "paths" in openapi_schema:
            for path in sorted(openapi_schema["paths"].keys()):
                markdown.append(f"- [{path}](#{path.replace('/', '').replace('_', '-')})")
        markdown.append("")

        # Authentication
        markdown.append("## Authentication")
        markdown.append("")
        if "components" in openapi_schema and "securitySchemes" in openapi_schema["components"]:
            for scheme_name, scheme in openapi_schema["components"]["securitySchemes"].items():
                markdown.append(f"### {scheme_name}")
                if scheme.get("type") == "http":
                    markdown.append(f"**Type**: {scheme.get('scheme', '').upper()}")
                markdown.append("")
        markdown.append("")

        # Endpoints
        if "paths" in openapi_schema:
            for path, path_item in openapi_schema["paths"].items():
                markdown.append(f"## {path}")
                markdown.append("")

                for method, operation in path_item.items():
                    if method in ["get", "post", "put", "delete", "patch"]:
                        markdown.append(f"### {method.upper()} {operation.get('summary', '')}")
                        markdown.append("")
                        markdown.append(operation.get("description", ""))
                        markdown.append("")

                        # Parameters
                        if "parameters" in operation:
                            markdown.append("#### Parameters:")
                            markdown.append("")
                            for param in operation["parameters"]:
                                markdown.append(f"- **{param['name']}** ({param.get('in', 'query')}): {param.get('description', '')}")
                                if param.get("required"):
                                    markdown.append("  - *Required*")
                            markdown.append("")

                        # Request body
                        if "requestBody" in operation:
                            markdown.append("#### Request Body:")
                            markdown.append("")
                            if "content" in operation["requestBody"]:
                                for content_type, content in operation["requestBody"]["content"].items():
                                    markdown.append(f"**Content-Type**: {content_type}")
                                    if "example" in content:
                                        markdown.append("```json")
                                        markdown.append(json.dumps(content["example"], indent=2))
                                        markdown.append("```")
                                    markdown.append("")
                        # Responses
                        if "responses" in operation:
                            markdown.append("#### Responses:")
                            markdown.append("")
                            for status_code, response in operation["responses"].items():
                                markdown.append(f"**{status_code}**: {response.get('description', '')}")
                                if "content" in response and "application/json" in response["content"]:
                                    content = response["content"]["application/json"]
                                    if "example" in content:
                                        markdown.append("```json")
                                        markdown.append(json.dumps(content["example"], indent=2))
                                        markdown.append("```")
                                markdown.append("")

                        markdown.append("---")
                        markdown.append("")

        return "\n".join(markdown)

    def generate_client_sdks(self, openapi_schema: Dict[str, Any]) -> Dict[str, str]:
        """Generate basic client SDK code."""
        sdks = {}

        # Python SDK
        python_sdk = self._generate_python_sdk(openapi_schema)
        sdks["python"] = python_sdk

        # JavaScript SDK
        js_sdk = self._generate_javascript_sdk(openapi_schema)
        sdks["javascript"] = js_sdk

        return sdks

    def _generate_python_sdk(self, openapi_schema: Dict[str, Any]) -> str:
        """Generate Python SDK code."""
        sdk_code = '''
import requests
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ShopAssistantAI:
    """Shop Assistant AI Python SDK"""

    base_url: str
    api_key: str
    timeout: int = 30

    def __post_init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to API"""
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response.json()

    def send_message(self, message: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Send a message to the AI assistant"""
        data = {"message": message}
        if conversation_id:
            data["conversation_id"] = conversation_id

        return self._request("POST", "/api/v1/chat/message", json=data)

    def classify_intent(self, text: str) -> Dict[str, Any]:
        """Classify intent of text"""
        return self._request("POST", "/api/v1/nlu/classify-intent", json={"text": text})

    def extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities from text"""
        return self._request("POST", "/api/v1/nlu/extract-entities", json={"text": text})

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text"""
        return self._request("POST", "/api/v1/nlu/analyze-sentiment", json={"text": text})

    def get_conversation_history(self, conversation_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get conversation history"""
        params = {"limit": limit, "offset": offset}
        return self._request("GET", f"/api/v1/chat/history/{conversation_id}", params=params)


# Example usage
if __name__ == "__main__":
    client = ShopAssistantAI(
        base_url="http://localhost:8000",
        api_key="your-api-key-here"
    )

    # Send a message
    response = client.send_message("Hello, I need help with my order")
    print(response)
'''
        return sdk_code.strip()

    def _generate_javascript_sdk(self, openapi_schema: Dict[str, Any]) -> str:
        """Generate JavaScript SDK code."""
        sdk_code = '''
class ShopAssistantAI {
    constructor(baseUrl, apiKey, options = {}) {
        this.baseUrl = baseUrl;
        this.apiKey = apiKey;
        this.timeout = options.timeout || 30000;
        this.headers = {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json',
            ...options.headers
        };
    }

    async _request(method, endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            method,
            headers: this.headers,
            ...options
        };

        if (options.body) {
            config.body = JSON.stringify(options.body);
        }

        const response = await fetch(url, config);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    async sendMessage(message, conversationId = null) {
        const data = { message };
        if (conversationId) {
            data.conversation_id = conversationId;
        }

        return this._request('POST', '/api/v1/chat/message', { body: data });
    }

    async classifyIntent(text) {
        return this._request('POST', '/api/v1/nlu/classify-intent', { body: { text } });
    }

    async extractEntities(text) {
        return this._request('POST', '/api/v1/nlu/extract-entities', { body: { text } });
    }

    async analyzeSentiment(text) {
        return this._request('POST', '/api/v1/nlu/analyze-sentiment', { body: { text } });
    }

    async getConversationHistory(conversationId, limit = 50, offset = 0) {
        const params = new URLSearchParams({ limit: limit.toString(), offset: offset.toString() });
        return this._request('GET', `/api/v1/chat/history/${conversationId}?${params}`);
    }
}

// Example usage
const client = new ShopAssistantAI('http://localhost:8000', 'your-api-key-here');

// Send a message
client.sendMessage('Hello, I need help with my order')
    .then(response => console.log(response))
    .catch(error => console.error(error));
'''
        return sdk_code.strip()