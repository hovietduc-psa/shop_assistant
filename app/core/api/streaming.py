"""
Streaming responses and Server-Sent Events (SSE) support.
"""

import asyncio
import json
from typing import AsyncGenerator, Dict, Any, Optional, Callable, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from fastapi import Response, Request
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse
from loguru import logger


class SSEEvent:
    """Server-Sent Event data structure."""

    def __init__(self,
                 data: Union[str, Dict[str, Any]],
                 event: Optional[str] = None,
                 id: Optional[str] = None,
                 retry: Optional[int] = None):
        """
        Initialize SSE event.

        Args:
            data: Event data (string or dict)
            event: Event type/name
            id: Event ID
            retry: Reconnection time in milliseconds
        """
        self.data = data
        self.event = event
        self.id = id
        self.retry = retry
        self.timestamp = datetime.utcnow()

    def format(self) -> str:
        """Format event as SSE string."""
        lines = []

        # Event type
        if self.event:
            lines.append(f"event: {self.event}")

        # Event ID
        if self.id:
            lines.append(f"id: {self.id}")

        # Retry interval
        if self.retry:
            lines.append(f"retry: {self.retry}")

        # Data
        if isinstance(self.data, dict):
            data_str = json.dumps(self.data, ensure_ascii=False)
        else:
            data_str = str(self.data)

        # Multi-line data support
        for line in data_str.split('\n'):
            lines.append(f"data: {line}")

        # End of event
        lines.append("")  # Empty line marks end of event

        return '\n'.join(lines) + '\n'


class SSEStream:
    """Server-Sent Events stream manager."""

    def __init__(self,
                 keep_alive_interval: int = 30,
                 max_connections: int = 1000):
        """
        Initialize SSE stream.

        Args:
            keep_alive_interval: Seconds between keep-alive pings
            max_connections: Maximum concurrent connections
        """
        self.keep_alive_interval = keep_alive_interval
        self.max_connections = max_connections
        self.active_connections: Dict[str, asyncio.Queue] = {}
        self.connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'peak_connections': 0
        }

    async def create_connection(self, client_id: str) -> asyncio.Queue:
        """Create a new SSE connection."""
        if len(self.active_connections) >= self.max_connections:
            raise Exception("Maximum connections exceeded")

        queue = asyncio.Queue(maxsize=100)  # Buffer up to 100 events
        self.active_connections[client_id] = queue

        self.connection_stats['total_connections'] += 1
        self.connection_stats['active_connections'] = len(self.active_connections)
        self.connection_stats['peak_connections'] = max(
            self.connection_stats['peak_connections'],
            self.connection_stats['active_connections']
        )

        logger.info(f"SSE connection created: {client_id}")

        # Send initial connection event
        await queue.put(SSEEvent(
            data={"type": "connected", "client_id": client_id},
            event="connection",
            id="0"
        ))

        return queue

    async def remove_connection(self, client_id: str):
        """Remove an SSE connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            self.connection_stats['active_connections'] = len(self.active_connections)
            logger.info(f"SSE connection removed: {client_id}")

    async def send_event(self, event: SSEEvent, client_id: Optional[str] = None):
        """Send an event to specific client or all clients."""
        if client_id:
            # Send to specific client
            if client_id in self.active_connections:
                queue = self.active_connections[client_id]
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(f"Event queue full for client {client_id}")
        else:
            # Send to all clients
            disconnected_clients = []
            for cid, queue in self.active_connections.items():
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(f"Event queue full for client {cid}")
                except Exception as e:
                    logger.error(f"Error sending event to client {cid}: {e}")
                    disconnected_clients.append(cid)

            # Clean up disconnected clients
            for cid in disconnected_clients:
                await self.remove_connection(cid)

    async def send_data(self,
                       data: Union[str, Dict[str, Any]],
                       event: Optional[str] = None,
                       client_id: Optional[str] = None):
        """Send data as SSE event."""
        sse_event = SSEEvent(data=data, event=event)
        await self.send_event(sse_event, client_id)

    async def keep_alive_sender(self, client_id: str, queue: asyncio.Queue):
        """Send periodic keep-alive events."""
        try:
            while client_id in self.active_connections:
                await asyncio.sleep(self.keep_alive_interval)
                if client_id in self.active_connections:  # Check still connected
                    keep_alive_event = SSEEvent(
                        data={"type": "keepalive", "timestamp": datetime.utcnow().isoformat()},
                        event="keepalive"
                    )
                    try:
                        queue.put_nowait(keep_alive_event)
                    except asyncio.QueueFull:
                        pass
        except Exception as e:
            logger.error(f"Keep-alive sender error for {client_id}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            **self.connection_stats,
            'keep_alive_interval': self.keep_alive_interval,
            'max_connections': self.max_connections
        }


class StreamingResponse:
    """Enhanced streaming response manager."""

    def __init__(self):
        """Initialize streaming response manager."""
        self.sse_manager = SSEStream()
        self.active_streams: Dict[str, AsyncGenerator] = {}

    async def create_sse_stream(self,
                               request: Request,
                               client_id: Optional[str] = None,
                               events: Optional[list] = None) -> FastAPIStreamingResponse:
        """
        Create a Server-Sent Events stream.

        Args:
            request: FastAPI request object
            client_id: Optional client identifier
            events: List of events to subscribe to

        Returns:
            FastAPI StreamingResponse
        """
        if not client_id:
            import uuid
            client_id = f"client_{uuid.uuid4().hex[:12]}"

        queue = await self.sse_manager.create_connection(client_id)

        async def event_stream():
            """Generate SSE events."""
            try:
                # Start keep-alive sender
                keep_alive_task = asyncio.create_task(
                    self.sse_manager.keep_alive_sender(client_id, queue)
                )

                # Send initial events
                if events:
                    for event_type in events:
                        await queue.put(SSEEvent(
                            data={"type": "subscribed", "event": event_type},
                            event="subscription"
                        ))

                # Stream events
                while client_id in self.sse_manager.active_connections:
                    try:
                        # Wait for event with timeout
                        event = await asyncio.wait_for(queue.get(), timeout=1.0)
                        yield event.format()
                    except asyncio.TimeoutError:
                        # Send comment to keep connection alive
                        yield ": keep-alive\n\n"
                    except Exception as e:
                        logger.error(f"Error in event stream for {client_id}: {e}")
                        break

            except Exception as e:
                logger.error(f"Event stream error for {client_id}: {e}")
            finally:
                # Clean up
                keep_alive_task.cancel()
                await self.sse_manager.remove_connection(client_id)

        response = FastAPIStreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )

        return response

    async def stream_data(self,
                         data_generator: AsyncGenerator[Dict[str, Any], None],
                         format_type: str = "json") -> FastAPIStreamingResponse:
        """
        Stream data from an async generator.

        Args:
            data_generator: Async generator yielding data
            format_type: Output format ("json", "csv", "ndjson")

        Returns:
            FastAPI StreamingResponse
        """
        async def generate_stream():
            """Generate formatted data stream."""
            try:
                if format_type == "json":
                    # Stream as JSON array
                    yield "[\n"
                    first = True
                    async for item in data_generator:
                        if not first:
                            yield ",\n"
                        yield json.dumps(item, ensure_ascii=False)
                        first = False
                    yield "\n]"

                elif format_type == "ndjson":
                    # Stream as Newline Delimited JSON
                    async for item in data_generator:
                        yield json.dumps(item, ensure_ascii=False) + "\n"

                elif format_type == "csv":
                    # Stream as CSV (requires headers)
                    headers_written = False
                    async for item in data_generator:
                        if not headers_written:
                            if isinstance(item, dict):
                                headers = list(item.keys())
                                yield ",".join(headers) + "\n"
                                headers_written = True
                        if isinstance(item, dict):
                            values = [str(item.get(h, "")) for h in headers]
                            yield ",".join(values) + "\n"

                else:
                    # Raw streaming
                    async for item in data_generator:
                        yield str(item)

            except Exception as e:
                logger.error(f"Data stream error: {e}")
                yield f"\n\nERROR: {str(e)}\n\n"

        media_type = {
            "json": "application/json",
            "ndjson": "application/x-ndjson",
            "csv": "text/csv",
            "raw": "text/plain"
        }.get(format_type, "text/plain")

        return FastAPIStreamingResponse(
            generate_stream(),
            media_type=media_type,
            headers={
                "Transfer-Encoding": "chunked",
                "Cache-Control": "no-cache"
            }
        )

    async def stream_file(self,
                         file_path: str,
                         chunk_size: int = 8192) -> FastAPIStreamingResponse:
        """
        Stream a file in chunks.

        Args:
            file_path: Path to the file
            chunk_size: Size of each chunk in bytes

        Returns:
            FastAPI StreamingResponse
        """
        import os
        import mimetypes

        async def file_stream():
            """Generate file chunks."""
            try:
                with open(file_path, 'rb') as file:
                    while chunk := file.read(chunk_size):
                        yield chunk
            except Exception as e:
                logger.error(f"File stream error: {e}")

        # Determine media type
        media_type, _ = mimetypes.guess_type(file_path)
        if not media_type:
            media_type = "application/octet-stream"

        return FastAPIStreamingResponse(
            file_stream(),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={os.path.basename(file_path)}",
                "Accept-Ranges": "bytes"
            }
        )

    async def broadcast_event(self,
                             event_data: Union[str, Dict[str, Any]],
                             event_type: Optional[str] = None,
                             target_clients: Optional[list] = None):
        """
        Broadcast an event to SSE clients.

        Args:
            event_data: Event data
            event_type: Event type
            target_clients: Specific client IDs to send to (None for all)
        """
        if target_clients:
            for client_id in target_clients:
                await self.sse_manager.send_data(event_data, event_type, client_id)
        else:
            await self.sse_manager.send_data(event_data, event_type)

    def get_stream_stats(self) -> Dict[str, Any]:
        """Get streaming statistics."""
        return {
            'sse_stats': self.sse_manager.get_stats(),
            'active_streams': len(self.active_streams)
        }


# Global streaming manager
streaming_manager = StreamingResponse()


def get_streaming_manager() -> StreamingResponse:
    """Get the global streaming manager."""
    return streaming_manager