"""
Batch operations for processing multiple requests efficiently.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Callable, Union, AsyncGenerator
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field, validator
from loguru import logger

from app.core.config import settings


class BatchOperationType(Enum):
    """Types of batch operations."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    CUSTOM = "custom"


class BatchStatus(Enum):
    """Batch operation status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


@dataclass
class BatchRequestItem:
    """Individual item in a batch request."""
    id: str
    operation: BatchOperationType
    method: str
    path: str
    params: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: Optional[float] = None


@dataclass
class BatchResponseItem:
    """Response for a single batch item."""
    id: str
    status: int
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class BatchResult:
    """Overall batch operation result."""
    batch_id: str
    status: BatchStatus
    total_items: int
    completed_items: int
    failed_items: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    responses: List[BatchResponseItem] = field(default_factory=list)


class BatchRequest(BaseModel):
    """Batch request model for API."""
    items: List[Dict[str, Any]] = Field(..., min_items=1, max_items=100)
    parallel: bool = Field(True, description="Execute items in parallel")
    continue_on_error: bool = Field(True, description="Continue processing even if some items fail")
    timeout: Optional[float] = Field(None, description="Overall batch timeout in seconds")

    @validator('items')
    def validate_items(cls, v):
        """Validate batch items."""
        for item in v:
            if 'id' not in item:
                raise ValueError("Each batch item must have an 'id'")
            if 'operation' not in item:
                raise ValueError("Each batch item must have an 'operation'")
            if 'method' not in item:
                raise ValueError("Each batch item must have a 'method'")
            if 'path' not in item:
                raise ValueError("Each batch item must have a 'path'")
        return v


class BatchResponse(BaseModel):
    """Batch response model."""
    batch_id: str
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    processing_time_ms: float
    items: List[Dict[str, Any]]


class BatchProcessor:
    """Advanced batch operation processor."""

    def __init__(self):
        """Initialize the batch processor."""
        self.batch_cache: Dict[str, BatchResult] = {}
        self.max_concurrent_items = 10
        self.default_timeout = 30.0

    async def process_batch(self,
                          batch_request: BatchRequest,
                          request_handler: Callable) -> BatchResult:
        """
        Process a batch of requests.

        Args:
            batch_request: The batch request to process
            request_handler: Function to handle individual requests

        Returns:
            BatchResult with all responses
        """
        batch_id = self._generate_batch_id()
        start_time = datetime.utcnow()

        logger.info(f"Starting batch processing for batch {batch_id} with {len(batch_request.items)} items")

        # Create batch request items
        items = []
        for item_data in batch_request.items:
            try:
                operation = BatchOperationType(item_data['operation'])
                batch_item = BatchRequestItem(
                    id=item_data['id'],
                    operation=operation,
                    method=item_data['method'],
                    path=item_data['path'],
                    params=item_data.get('params', {}),
                    data=item_data.get('data', {}),
                    headers=item_data.get('headers', {}),
                    timeout=item_data.get('timeout', batch_request.timeout)
                )
                items.append(batch_item)
            except Exception as e:
                logger.error(f"Invalid batch item {item_data.get('id', 'unknown')}: {e}")
                if not batch_request.continue_on_error:
                    raise HTTPException(status_code=400, detail=f"Invalid batch item: {str(e)}")

        # Initialize batch result
        batch_result = BatchResult(
            batch_id=batch_id,
            status=BatchStatus.PROCESSING,
            total_items=len(items),
            completed_items=0,
            failed_items=0,
            started_at=start_time
        )

        self.batch_cache[batch_id] = batch_result

        try:
            if batch_request.parallel:
                await self._process_parallel(items, request_handler, batch_result, batch_request.continue_on_error)
            else:
                await self._process_sequential(items, request_handler, batch_result, batch_request.continue_on_error)

            # Update final status
            if batch_result.failed_items == 0:
                batch_result.status = BatchStatus.COMPLETED
            elif batch_result.completed_items > 0:
                batch_result.status = BatchStatus.PARTIAL
            else:
                batch_result.status = BatchStatus.FAILED

        except Exception as e:
            logger.error(f"Batch processing failed for {batch_id}: {e}")
            batch_result.status = BatchStatus.FAILED

        finally:
            batch_result.completed_at = datetime.utcnow()
            processing_time = (batch_result.completed_at - batch_result.started_at).total_seconds() * 1000

            logger.info(f"Batch {batch_id} completed in {processing_time:.2f}ms: "
                       f"{batch_result.completed_items}/{batch_result.total_items} successful")

            # Clean up old batches
            await self._cleanup_old_batches()

        return batch_result

    async def _process_parallel(self,
                               items: List[BatchRequestItem],
                               request_handler: Callable,
                               batch_result: BatchResult,
                               continue_on_error: bool):
        """Process batch items in parallel."""
        semaphore = asyncio.Semaphore(self.max_concurrent_items)

        async def process_item(item: BatchRequestItem) -> BatchResponseItem:
            async with semaphore:
                return await self._process_single_item(item, request_handler)

        # Process all items concurrently
        tasks = [process_item(item) for item in items]

        if continue_on_error:
            # Wait for all tasks, even if some fail
            responses = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            # Cancel all tasks if one fails
            try:
                responses = await asyncio.gather(*tasks)
            except Exception as e:
                # Cancel remaining tasks
                for task in tasks:
                    if not task.done():
                        task.cancel()
                raise e

        # Process responses
        for response in responses:
            if isinstance(response, Exception):
                logger.error(f"Batch item failed: {response}")
                batch_result.failed_items += 1
            else:
                batch_result.responses.append(response)
                if response.status >= 400:
                    batch_result.failed_items += 1
                else:
                    batch_result.completed_items += 1

    async def _process_sequential(self,
                                items: List[BatchRequestItem],
                                request_handler: Callable,
                                batch_result: BatchResult,
                                continue_on_error: bool):
        """Process batch items sequentially."""
        for item in items:
            try:
                response = await self._process_single_item(item, request_handler)
                batch_result.responses.append(response)

                if response.status >= 400:
                    batch_result.failed_items += 1
                    if not continue_on_error:
                        break
                else:
                    batch_result.completed_items += 1

            except Exception as e:
                logger.error(f"Batch item {item.id} failed: {e}")
                batch_result.failed_items += 1

                if not continue_on_error:
                    break

    async def _process_single_item(self,
                                  item: BatchRequestItem,
                                  request_handler: Callable) -> BatchResponseItem:
        """Process a single batch item."""
        start_time = time.time()

        try:
            # Create a mock request for the handler
            mock_request = type('MockRequest', (), {
                'method': item.method,
                'url': {'path': item.path},
                'query_params': item.params,
                'headers': item.headers,
                'json': lambda: item.data if item.data else {}
            })()

            # Process the request
            response = await request_handler(mock_request)

            duration_ms = (time.time() - start_time) * 1000

            return BatchResponseItem(
                id=item.id,
                status=getattr(response, 'status_code', 200),
                data=getattr(response, 'data', None),
                headers=getattr(response, 'headers', {}),
                duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            return BatchResponseItem(
                id=item.id,
                status=500,
                error=str(e),
                duration_ms=duration_ms
            )

    def get_batch_status(self, batch_id: str) -> Optional[BatchResult]:
        """Get the status of a batch operation."""
        return self.batch_cache.get(batch_id)

    def _generate_batch_id(self) -> str:
        """Generate a unique batch ID."""
        import uuid
        return f"batch_{uuid.uuid4().hex[:12]}_{int(time.time())}"

    async def _cleanup_old_batches(self):
        """Clean up old batch results from cache."""
        cutoff_time = datetime.utcnow().timestamp() - 3600  # 1 hour ago

        to_remove = []
        for batch_id, batch_result in self.batch_cache.items():
            if batch_result.started_at.timestamp() < cutoff_time:
                to_remove.append(batch_id)

        for batch_id in to_remove:
            del self.batch_cache[batch_id]
            logger.debug(f"Cleaned up old batch: {batch_id}")


class BatchOperationsAPI:
    """API endpoints for batch operations."""

    def __init__(self, batch_processor: BatchProcessor):
        """Initialize the batch operations API."""
        self.processor = batch_processor

    async def create_batch(self,
                          batch_request: BatchRequest,
                          request: Request) -> Dict[str, Any]:
        """Create and start a new batch operation."""
        # Simple request handler - in production, this would route to actual endpoints
        async def mock_request_handler(mock_request):
            # This is a placeholder - actual implementation would route to FastAPI handlers
            return type('MockResponse', (), {
                'status_code': 200,
                'data': {'message': 'success'},
                'headers': {}
            })()

        batch_result = await self.processor.process_batch(batch_request, mock_request_handler)

        # Convert to response format
        items = []
        for response in batch_result.responses:
            item = {
                'id': response.id,
                'status': response.status,
                'duration_ms': response.duration_ms
            }
            if response.data:
                item['data'] = response.data
            if response.error:
                item['error'] = response.error
            if response.headers:
                item['headers'] = response.headers
            items.append(item)

        processing_time = 0
        if batch_result.completed_at:
            processing_time = (batch_result.completed_at - batch_result.started_at).total_seconds() * 1000

        return {
            'batch_id': batch_result.batch_id,
            'status': batch_result.status.value,
            'total_items': batch_result.total_items,
            'completed_items': batch_result.completed_items,
            'failed_items': batch_result.failed_items,
            'processing_time_ms': processing_time,
            'items': items
        }

    async def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a batch operation."""
        batch_result = self.processor.get_batch_status(batch_id)

        if not batch_result:
            return None

        # Convert to response format
        items = []
        for response in batch_result.responses:
            item = {
                'id': response.id,
                'status': response.status,
                'duration_ms': response.duration_ms
            }
            if response.data:
                item['data'] = response.data
            if response.error:
                item['error'] = response.error
            if response.headers:
                item['headers'] = response.headers
            items.append(item)

        processing_time = 0
        if batch_result.completed_at:
            processing_time = (batch_result.completed_at - batch_result.started_at).total_seconds() * 1000

        return {
            'batch_id': batch_result.batch_id,
            'status': batch_result.status.value,
            'total_items': batch_result.total_items,
            'completed_items': batch_result.completed_items,
            'failed_items': batch_result.failed_items,
            'processing_time_ms': processing_time,
            'items': items
        }