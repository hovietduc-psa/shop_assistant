"""
API documentation setup and configuration.
"""

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import json
from pathlib import Path

from app.docs.openapi import OpenAPIDocumentation, APIDocumentationGenerator
from app.core.config import settings


class DocumentationMiddleware(BaseHTTPMiddleware):
    """Middleware to serve documentation endpoints."""

    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.openapi_doc = OpenAPIDocumentation(app)
        self.doc_generator = APIDocumentationGenerator()
        self._setup_documentation_routes(app)

    def _setup_documentation_routes(self, app: FastAPI):
        """Setup documentation routes."""

        @app.get("/docs", include_in_schema=False)
        async def custom_swagger_ui_html():
            """Custom Swagger UI."""
            return get_swagger_ui_html(
                openapi_url=app.openapi_url,
                title=f"{app.title} - Swagger UI",
                oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
                swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
                swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
                swagger_ui_parameters={
                    "deepLinking": True,
                    "displayRequestDuration": True,
                    "docExpansion": "none",
                    "operationsSorter": "alpha",
                    "filter": True,
                    "tryItOutEnabled": True,
                    "persistAuthorization": True,
                    "showExtensions": True,
                    "showCommonExtensions": True
                }
            )

        @app.get("/redoc", include_in_schema=False)
        async def redoc_html():
            """ReDoc documentation."""
            return get_redoc_html(
                openapi_url=app.openapi_url,
                title=f"{app.title} - ReDoc",
                redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.0.0/bundles/redoc.standalone.js",
                redoc_html=f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{app.title} - ReDoc</title>
                    <meta charset="utf-8"/>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
                    <style>
                        body {{
                            margin: 0;
                            padding: 0;
                        }}
                    </style>
                </head>
                <body>
                    <redoc spec-url='{app.openapi_url}'></redoc>
                    <script src="{{redoc_js_url}}"></script>
                </body>
                </html>
                """
            )

        @app.get("/docs/postman", response_class=HTMLResponse, include_in_schema=False)
        async def postman_collection():
            """Generate Postman collection."""
            try:
                openapi_schema = app.openapi()
                collection = self.doc_generator.generate_postman_collection(openapi_schema)

                html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Postman Collection - {app.title}</title>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            max-width: 800px;
                            margin: 0 auto;
                            padding: 20px;
                        }}
                        .header {{
                            background: #ff6c37;
                            color: white;
                            padding: 20px;
                            border-radius: 5px;
                            margin-bottom: 20px;
                        }}
                        .download-btn {{
                            background: #ff6c37;
                            color: white;
                            padding: 12px 24px;
                            border: none;
                            border-radius: 5px;
                            cursor: pointer;
                            font-size: 16px;
                            margin: 10px 0;
                        }}
                        .download-btn:hover {{
                            background: #e55a2b;
                        }}
                        .preview {{
                            background: #f8f9fa;
                            border: 1px solid #dee2e6;
                            border-radius: 5px;
                            padding: 20px;
                            margin: 20px 0;
                        }}
                        pre {{
                            background: #f1f3f4;
                            padding: 15px;
                            border-radius: 5px;
                            overflow-x: auto;
                        }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>Postman Collection</h1>
                        <p>Download the Postman collection for {app.title}</p>
                    </div>

                    <button class="download-btn" onclick="downloadCollection()">
                        Download Postman Collection
                    </button>

                    <div class="preview">
                        <h3>Collection Preview</h3>
                        <pre>{json.dumps(collection, indent=2)[:1000]}...</pre>
                    </div>

                    <script>
                        const collection = {json.dumps(collection)};

                        function downloadCollection() {{
                            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(collection, null, 2));
                            const downloadAnchorNode = document.createElement('a');
                            downloadAnchorNode.setAttribute("href", dataStr);
                            downloadAnchorNode.setAttribute("download", "shop-assistant-api.postman_collection.json");
                            document.body.appendChild(downloadAnchorNode);
                            downloadAnchorNode.click();
                            downloadAnchorNode.remove();
                        }}
                    </script>
                </body>
                </html>
                """
                return HTMLResponse(content=html)
            except Exception as e:
                return HTMLResponse(content=f"<h1>Error generating collection</h1><p>{str(e)}</p>")

        @app.get("/docs/markdown", include_in_schema=False)
        async def markdown_documentation():
            """Generate Markdown documentation."""
            try:
                openapi_schema = app.openapi()
                markdown = self.doc_generator.generate_markdown_documentation(openapi_schema)
                return Response(content=markdown, media_type="text/markdown")
            except Exception as e:
                return Response(content=f"Error generating documentation: {str(e)}", media_type="text/plain")

        @app.get("/docs/sdk/{language}", include_in_schema=False)
        async def sdk_documentation(language: str):
            """Generate SDK documentation."""
            try:
                openapi_schema = app.openapi()
                sdks = self.doc_generator.generate_client_sdks(openapi_schema)

                if language.lower() not in sdks:
                    return Response(
                        content=f"SDK not available for language: {language}",
                        status_code=404
                    )

                sdk_code = sdks[language.lower()]
                filename = f"shop-assistant-sdk.{language.lower()}"

                if language.lower() == "python":
                    media_type = "text/x-python"
                elif language.lower() == "javascript":
                    media_type = "application/javascript"
                else:
                    media_type = "text/plain"

                return Response(
                    content=sdk_code,
                    media_type=media_type,
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            except Exception as e:
                return Response(content=f"Error generating SDK: {str(e)}", media_type="text/plain")

        @app.get("/docs/overview", response_class=HTMLResponse, include_in_schema=False)
        async def documentation_overview():
            """Documentation overview page."""
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>API Documentation - {app.title}</title>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        line-height: 1.6;
                        margin: 0;
                        padding: 0;
                        background: #f8f9fa;
                    }}
                    .container {{
                        max-width: 1200px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 40px 20px;
                        border-radius: 10px;
                        margin-bottom: 30px;
                        text-align: center;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 2.5em;
                        font-weight: 300;
                    }}
                    .header p {{
                        margin: 10px 0 0 0;
                        opacity: 0.9;
                        font-size: 1.2em;
                    }}
                    .docs-grid {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                        gap: 20px;
                        margin-bottom: 30px;
                    }}
                    .doc-card {{
                        background: white;
                        border-radius: 10px;
                        padding: 30px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        transition: transform 0.2s, box-shadow 0.2s;
                    }}
                    .doc-card:hover {{
                        transform: translateY(-5px);
                        box-shadow: 0 5px 20px rgba(0,0,0,0.15);
                    }}
                    .doc-card h3 {{
                        margin: 0 0 15px 0;
                        color: #333;
                        font-size: 1.4em;
                    }}
                    .doc-card p {{
                        color: #666;
                        margin-bottom: 20px;
                    }}
                    .doc-card a {{
                        display: inline-block;
                        background: #667eea;
                        color: white;
                        padding: 10px 20px;
                        text-decoration: none;
                        border-radius: 5px;
                        transition: background 0.2s;
                    }}
                    .doc-card a:hover {{
                        background: #5a6fd8;
                    }}
                    .info-section {{
                        background: white;
                        border-radius: 10px;
                        padding: 30px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        margin-bottom: 30px;
                    }}
                    .info-section h2 {{
                        color: #333;
                        margin-top: 0;
                    }}
                    .badge {{
                        display: inline-block;
                        background: #28a745;
                        color: white;
                        padding: 4px 8px;
                        border-radius: 3px;
                        font-size: 0.8em;
                        margin-left: 10px;
                    }}
                    .code-block {{
                        background: #f8f9fa;
                        border: 1px solid #e9ecef;
                        border-radius: 5px;
                        padding: 15px;
                        margin: 15px 0;
                        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>{app.title} API Documentation</h1>
                        <p>Comprehensive API documentation and developer resources</p>
                    </div>

                    <div class="docs-grid">
                        <div class="doc-card">
                            <h3>Interactive API Docs</h3>
                            <p>Explore and test the API with our interactive Swagger UI</p>
                            <a href="/docs">Open Swagger UI</a>
                        </div>

                        <div class="doc-card">
                            <h3>ReDoc Documentation</h3>
                            <p>Beautiful, responsive API documentation powered by ReDoc</p>
                            <a href="/redoc">Open ReDoc</a>
                        </div>

                        <div class="doc-card">
                            <h3>Postman Collection</h3>
                            <p>Download a ready-to-use Postman collection for API testing</p>
                            <a href="/docs/postman">Get Collection</a>
                        </div>

                        <div class="doc-card">
                            <h3>Markdown Documentation</h3>
                            <p>Download complete API documentation in Markdown format</p>
                            <a href="/docs/markdown" download>Download MD</a>
                        </div>

                        <div class="doc-card">
                            <h3>Python SDK</h3>
                            <p>Download the official Python SDK for easy integration</p>
                            <a href="/docs/sdk/python">Download Python SDK</a>
                        </div>

                        <div class="doc-card">
                            <h3>JavaScript SDK</h3>
                            <p>Download the official JavaScript SDK for web applications</p>
                            <a href="/docs/sdk/javascript">Download JS SDK</a>
                        </div>
                    </div>

                    <div class="info-section">
                        <h2>Quick Start</h2>
                        <p>Get started with the {app.title} API in minutes:</p>

                        <h4>1. Authentication</h4>
                        <div class="code-block">
curl -H "Authorization: Bearer YOUR_API_KEY" \\
     -H "Content-Type: application/json" \\
     https://api.shopassistant.com/v1/chat/message
                        </div>

                        <h4>2. Send Your First Message</h4>
                        <div class="code-block">
curl -X POST \\
     -H "Authorization: Bearer YOUR_API_KEY" \\
     -H "Content-Type: application/json" \\
     -d '{{
       "message": "Hello, I need help with my order"
     }}' \\
     https://api.shopassistant.com/v1/chat/message
                        </div>

                        <h4>3. Install an SDK</h4>
                        <div class="code-block">
# Python SDK (save the downloaded file as shop_assistant_sdk.py)
from shop_assistant_sdk import ShopAssistantAI

client = ShopAssistantAI(
    base_url="https://api.shopassistant.com/v1",
    api_key="your-api-key"
)

response = client.send_message("Hello, I need help")
print(response)
                        </div>
                    </div>

                    <div class="info-section">
                        <h2>API Features</h2>
                        <ul>
                            <li><strong>Natural Language Understanding</strong> - Advanced intent classification and entity extraction</li>
                            <li><strong>Intelligent Dialogue Management</strong> - Context-aware conversations</li>
                            <li><strong>Quality Assessment</strong> - Real-time conversation quality monitoring</li>
                            <li><strong>Memory Management</strong> - Persistent conversation memory</li>
                            <li><strong>Testing Framework</strong> - Comprehensive testing tools</li>
                            <li><strong>Analytics & Insights</strong> - Detailed conversation analytics</li>
                        </ul>
                    </div>

                    <div class="info-section">
                        <h2>Support</h2>
                        <p>Need help? Check out our resources:</p>
                        <ul>
                            <li><a href="/docs">Interactive Documentation</a></li>
                            <li><a href="https://github.com/shopassistant/api-examples">Code Examples</a></li>
                            <li><a href="mailto:api-support@shopassistant.com">Email Support</a></li>
                            <li><a href="https://status.shopassistant.com">API Status</a></li>
                        </ul>
                    </div>

                    <div style="text-align: center; margin-top: 40px; color: #666;">
                        <p>&copy; 2024 Shop Assistant AI. Version {app.version if hasattr(app, 'version') else '3.0.0'}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html)


def setup_documentation(app: FastAPI):
    """Setup comprehensive API documentation."""
    # Setup OpenAPI configuration
    openapi_doc = OpenAPIDocumentation(app)
    openapi_doc.setup_openapi()

    # Add documentation middleware
    DocumentationMiddleware(app)

    # Add CORS for documentation
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify actual origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    logger.info("API documentation setup complete")
    logger.info(f"Swagger UI: http://{settings.API_HOST}:{settings.API_PORT}/docs")
    logger.info(f"ReDoc: http://{settings.API_HOST}:{settings.API_PORT}/redoc")
    logger.info(f"Documentation Overview: http://{settings.API_HOST}:{settings.API_PORT}/docs/overview")