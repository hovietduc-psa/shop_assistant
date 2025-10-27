"""
API versioning strategy and implementation.
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Request, HTTPException, status
from fastapi.routing import APIRoute
from loguru import logger


class APIVersion(Enum):
    """Supported API versions."""
    V1 = "v1"
    V2 = "v2"  # Future version
    LATEST = "latest"


@dataclass
class VersionInfo:
    """API version information."""
    version: APIVersion
    deprecated: bool = False
    deprecation_date: Optional[datetime] = None
    sunset_date: Optional[datetime] = None
    migration_guide: Optional[str] = None
    features: List[str] = None
    breaking_changes: List[str] = None
    supported_until: Optional[datetime] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.features is None:
            self.features = []
        if self.breaking_changes is None:
            self.breaking_changes = []


class APIVersionManager:
    """Manages API versioning and compatibility."""

    def __init__(self):
        """Initialize the version manager."""
        self.versions: Dict[APIVersion, VersionInfo] = {}
        self.default_version = APIVersion.V1
        self.current_version = APIVersion.V1
        self._initialize_versions()

    def _initialize_versions(self):
        """Initialize supported API versions."""
        # Version 1 (current)
        self.versions[APIVersion.V1] = VersionInfo(
            version=APIVersion.V1,
            deprecated=False,
            features=[
                "Basic chat functionality",
                "User authentication",
                "Shopify integration",
                "Product search and recommendations",
                "Order management",
                "Webhook support"
            ],
            supported_until=datetime(2025, 12, 31, tzinfo=timezone.utc)
        )

        # Version 2 (future)
        self.versions[APIVersion.V2] = VersionInfo(
            version=APIVersion.V2,
            deprecated=False,
            features=[
                "Advanced AI capabilities",
                "Multi-channel support",
                "Advanced analytics",
                "Real-time collaboration",
                "Enhanced security"
            ],
            breaking_changes=[
                "Modified response format for chat endpoints",
                "Updated authentication schema",
                "Changed webhook payload structure"
            ],
            supported_until=datetime(2027, 12, 31, tzinfo=timezone.utc)
        )

    def register_version(self, version_info: VersionInfo):
        """Register a new API version."""
        self.versions[version_info.version] = version_info
        logger.info(f"Registered API version: {version_info.version.value}")

    def get_version(self, version: APIVersion) -> Optional[VersionInfo]:
        """Get version information."""
        return self.versions.get(version)

    def is_version_supported(self, version: APIVersion) -> bool:
        """Check if a version is supported."""
        version_info = self.versions.get(version)
        if not version_info:
            return False

        if version_info.deprecated and version_info.sunset_date:
            return datetime.now(timezone.utc) < version_info.sunset_date

        return True

    def get_latest_version(self) -> APIVersion:
        """Get the latest stable version."""
        return max(
            (v for v in self.versions.keys() if self.is_version_supported(v)),
            key=lambda x: int(x.value[1:])  # Extract number from "v1", "v2", etc.
        )

    def parse_version_from_request(self, request: Request) -> APIVersion:
        """Parse API version from request."""
        # Method 1: URL path versioning (/api/v1/...)
        path_version = self._extract_version_from_path(request.url.path)
        if path_version:
            return path_version

        # Method 2: Header versioning (Accept: application/vnd.api+json;version=1)
        header_version = self._extract_version_from_headers(request.headers)
        if header_version:
            return header_version

        # Method 3: Query parameter versioning (?version=v1)
        query_version = self._extract_version_from_query(request.query_params)
        if query_version:
            return query_version

        # Default to current version
        return self.current_version

    def _extract_version_from_path(self, path: str) -> Optional[APIVersion]:
        """Extract version from URL path."""
        # Match patterns like /api/v1/, /v2/, etc.
        match = re.search(r'/api/v(\d+)', path)
        if match:
            version_num = match.group(1)
            try:
                return APIVersion(f"v{version_num}")
            except ValueError:
                pass
        return None

    def _extract_version_from_headers(self, headers: Dict[str, str]) -> Optional[APIVersion]:
        """Extract version from headers."""
        # Check Accept header
        accept = headers.get("accept", "")
        if "application/vnd.api+json" in accept:
            # Extract version from Accept header
            match = re.search(r'version=(\d+)', accept)
            if match:
                version_num = match.group(1)
                try:
                    return APIVersion(f"v{version_num}")
                except ValueError:
                    pass

        # Check custom version header
        api_version = headers.get("api-version", "")
        if api_version:
            try:
                return APIVersion(api_version)
            except ValueError:
                pass

        return None

    def _extract_version_from_query(self, query_params: Dict[str, str]) -> Optional[APIVersion]:
        """Extract version from query parameters."""
        version = query_params.get("version") or query_params.get("v")
        if version:
            try:
                return APIVersion(version)
            except ValueError:
                pass
        return None

    def validate_version(self, version: APIVersion) -> None:
        """Validate that the requested version is supported."""
        if not self.is_version_supported(version):
            if version not in self.versions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Unsupported API version",
                        "requested_version": version.value,
                        "supported_versions": [v.value for v in self.versions.keys()],
                        "latest_version": self.get_latest_version().value
                    }
                )
            else:
                version_info = self.versions[version]
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail={
                        "error": "API version no longer supported",
                        "version": version.value,
                        "sunset_date": version_info.sunset_date.isoformat() if version_info.sunset_date else None,
                        "migration_guide": version_info.migration_guide,
                        "latest_version": self.get_latest_version().value
                    }
                )

    def get_deprecation_warnings(self, version: APIVersion) -> List[Dict[str, Any]]:
        """Get deprecation warnings for a version."""
        warnings = []
        version_info = self.versions.get(version)

        if version_info and version_info.deprecated:
            warning = {
                "type": "deprecation",
                "version": version.value,
                "deprecation_date": version_info.deprecation_date.isoformat() if version_info.deprecation_date else None,
                "sunset_date": version_info.sunset_date.isoformat() if version_info.sunset_date else None,
                "migration_guide": version_info.migration_guide,
                "recommended_action": f"Migrate to {self.get_latest_version().value}"
            }
            warnings.append(warning)

        return warnings

    def get_version_headers(self, version: APIVersion) -> Dict[str, str]:
        """Get response headers for version information."""
        headers = {
            "API-Version": version.value,
            "API-Latest-Version": self.get_latest_version().value,
            "API-Supported-Versions": ",".join(v.value for v in self.versions.keys())
        }

        # Add deprecation warnings
        warnings = self.get_deprecation_warnings(version)
        if warnings:
            headers["API-Deprecation-Warning"] = "true"
            headers["API-Sunset-Date"] = warnings[0]["sunset_date"]

        return headers


class VersionedRoute(APIRoute):
    """API route with version support."""

    def __init__(self, *args, version: APIVersion = APIVersion.V1, **kwargs):
        """Initialize versioned route."""
        self.version = version
        super().__init__(*args, **kwargs)


class APIVersionMiddleware:
    """Middleware for API version handling."""

    def __init__(self, app, version_manager: APIVersionManager):
        """Initialize the middleware."""
        self.app = app
        self.version_manager = version_manager

    async def __call__(self, scope, receive, send):
        """ASGI callable."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract version from request
        request = Request(scope, receive)
        version = self.version_manager.parse_version_from_request(request)

        # Validate version
        try:
            self.version_manager.validate_version(version)
        except HTTPException as e:
            # Send error response
            await self._send_error_response(e, send)
            return

        # Add version information to scope
        scope["api_version"] = version
        scope["version_info"] = self.version_manager.get_version(version)

        # Process request
        await self.app(scope, receive, send)

    async def _send_error_response(self, exc: HTTPException, send):
        """Send error response."""
        import json

        response_start = {
            'type': 'http.response.start',
            'status': exc.status_code,
            'headers': [
                (b'content-type', b'application/json'),
            ]
        }

        response_body = {
            'type': 'http.response.body',
            'body': json.dumps(exc.detail).encode()
        }

        await send(response_start)
        await send(response_body)


# Global version manager
version_manager = APIVersionManager()


def get_version_manager() -> APIVersionManager:
    """Get the global version manager."""
    return version_manager


def versioned_endpoint(version: APIVersion):
    """Decorator for versioned endpoints."""
    def decorator(func):
        func.__api_version__ = version
        return func
    return decorator


# Version compatibility helpers
def ensure_compatible_request(request_data: Dict[str, Any], from_version: APIVersion, to_version: APIVersion) -> Dict[str, Any]:
    """Ensure request data is compatible between versions."""
    if from_version == to_version:
        return request_data

    # Add version-specific transformations here
    transformed_data = request_data.copy()

    # Example: Transform field names between versions
    if from_version == APIVersion.V1 and to_version == APIVersion.V2:
        # V1 to V2 transformations
        if "message" in transformed_data:
            transformed_data["content"] = transformed_data.pop("message")

    elif from_version == APIVersion.V2 and to_version == APIVersion.V1:
        # V2 to V1 transformations
        if "content" in transformed_data:
            transformed_data["message"] = transformed_data.pop("content")

    return transformed_data


def ensure_compatible_response(response_data: Dict[str, Any], version: APIVersion) -> Dict[str, Any]:
    """Ensure response data is compatible with requested version."""
    # Add version-specific response formatting here
    if version == APIVersion.V1:
        # V1 response format
        if "data" in response_data and not isinstance(response_data["data"], list):
            response_data["results"] = response_data.pop("data")

    elif version == APIVersion.V2:
        # V2 response format
        if "results" in response_data:
            response_data["data"] = response_data.pop("results")

    return response_data