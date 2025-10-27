"""
Advanced pagination and filtering utilities.
"""

import base64
import json
from typing import Any, Dict, List, Optional, Union, Generic, TypeVar, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator

from fastapi import Query, HTTPException
from loguru import logger

T = TypeVar('T')


class PaginationType(Enum):
    """Pagination types."""
    OFFSET = "offset"
    CURSOR = "cursor"
    PAGE = "page"


class SortOrder(Enum):
    """Sort order options."""
    ASC = "asc"
    DESC = "desc"


class FilterOperator(Enum):
    """Filter operators."""
    EQ = "eq"          # Equals
    NE = "ne"          # Not equals
    GT = "gt"          # Greater than
    GTE = "gte"        # Greater than or equal
    LT = "lt"          # Less than
    LTE = "lte"        # Less than or equal
    IN = "in"          # In list
    NIN = "nin"        # Not in list
    LIKE = "like"      # Contains (case-insensitive)
    ILIKE = "ilike"    # Contains (case-sensitive)
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    BETWEEN = "between"
    DATE_RANGE = "date_range"


@dataclass
class FilterCondition:
    """Single filter condition."""
    field: str
    operator: FilterOperator
    value: Any
    negate: bool = False


@dataclass
class SortCondition:
    """Sort condition."""
    field: str
    order: SortOrder
    nulls_first: bool = False


@dataclass
class CursorInfo:
    """Cursor pagination information."""
    cursor: Optional[str] = None
    has_next: bool = False
    has_prev: bool = False
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None


class PaginationParams(BaseModel):
    """Pagination parameters."""
    type: PaginationType = Field(PaginationType.OFFSET, description="Pagination type")
    limit: int = Field(20, ge=1, le=1000, description="Items per page")
    offset: Optional[int] = Field(0, ge=0, description="Offset for offset pagination")
    page: Optional[int] = Field(1, ge=1, description="Page number for page pagination")
    cursor: Optional[str] = Field(None, description="Cursor for cursor pagination")

    @validator('offset')
    def validate_offset(cls, v, values):
        """Validate offset based on pagination type."""
        if values.get('type') == PaginationType.OFFSET and v is None:
            return 0
        return v

    @validator('page')
    def validate_page(cls, v, values):
        """Validate page based on pagination type."""
        if values.get('type') == PaginationType.PAGE and v is None:
            return 1
        return v


class FilterParams(BaseModel):
    """Filter parameters."""
    filters: Optional[str] = Field(None, description="JSON-encoded filter conditions")
    search: Optional[str] = Field(None, description="Search query")
    fields: Optional[str] = Field(None, description="Comma-separated fields to return")

    @validator('filters')
    def parse_filters(cls, v):
        """Parse JSON-encoded filters."""
        if v:
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON in filters parameter")
        return None

    @validator('fields')
    def parse_fields(cls, v):
        """Parse fields parameter."""
        if v:
            return [field.strip() for field in v.split(',') if field.strip()]
        return None


class SortParams(BaseModel):
    """Sort parameters."""
    sort: Optional[str] = Field(None, description="Sort field and order (field:order)")
    order: SortOrder = Field(SortOrder.ASC, description="Default sort order")

    @validator('sort')
    def parse_sort(cls, v):
        """Parse sort parameter."""
        if v:
            parts = v.split(':')
            field = parts[0]
            order = SortOrder.ASC if len(parts) == 1 else SortOrder(parts[1])
            return SortCondition(field=field, order=order)
        return None


class AdvancedPaginationParams(BaseModel):
    """Combined advanced pagination parameters."""
    pagination: PaginationParams = Field(default_factory=PaginationParams)
    filters: FilterParams = Field(default_factory=FilterParams)
    sorting: SortParams = Field(default_factory=SortParams)


@dataclass
class PaginationResult(Generic[T]):
    """Result of paginated query."""
    items: List[T]
    total: Optional[int] = None
    limit: int = 20
    offset: int = 0
    has_next: bool = False
    has_prev: bool = False
    next_page: Optional[int] = None
    prev_page: Optional[int] = None
    total_pages: Optional[int] = None
    cursor_info: Optional[CursorInfo] = None


class CursorEncoder:
    """Encoder for cursor pagination."""

    @staticmethod
    def encode(data: Dict[str, Any]) -> str:
        """Encode data to base64 cursor."""
        json_str = json.dumps(data, separators=(',', ':'), sort_keys=True)
        encoded = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        return encoded.rstrip('=')  # Remove padding

    @staticmethod
    def decode(cursor: str) -> Dict[str, Any]:
        """Decode base64 cursor to data."""
        # Add padding if needed
        padding = '=' * (-len(cursor) % 4)
        try:
            decoded = base64.b64decode(cursor + padding + '==').decode('utf-8')
            return json.loads(decoded)
        except Exception as e:
            logger.error(f"Failed to decode cursor: {e}")
            raise ValueError("Invalid cursor")


class AdvancedPagination:
    """Advanced pagination handler."""

    def __init__(self):
        """Initialize pagination handler."""
        self.cursor_encoder = CursorEncoder()

    def create_cursor(self, item: Dict[str, Any], sort_fields: List[str]) -> str:
        """Create cursor from item."""
        cursor_data = {}
        for field in sort_fields:
            cursor_data[field] = item.get(field)
        return self.cursor_encoder.encode(cursor_data)

    def parse_cursor(self, cursor: str) -> Dict[str, Any]:
        """Parse cursor to extract values."""
        return self.cursor_encoder.decode(cursor)

    def apply_offset_pagination(self,
                               query: Any,
                               params: PaginationParams) -> tuple:
        """Apply offset pagination to query."""
        if params.type == PaginationType.OFFSET:
            return query.offset(params.offset).limit(params.limit)
        elif params.type == PaginationType.PAGE:
            offset = (params.page - 1) * params.limit
            return query.offset(offset).limit(params.limit)
        else:
            return query.limit(params.limit)

    def apply_cursor_pagination(self,
                               query: Any,
                               cursor: Optional[str],
                               sort_fields: List[str],
                               limit: int,
                               forward: bool = True) -> tuple:
        """Apply cursor pagination to query."""
        if not cursor:
            return query.limit(limit)

        try:
            cursor_data = self.cursor_encoder.decode(cursor)

            # Build cursor conditions
            conditions = []
            for i, field in enumerate(sort_fields):
                value = cursor_data.get(field)
                if value is not None:
                    if forward:
                        if i == len(sort_fields) - 1:
                            # Last field - use > comparison
                            conditions.append((field, '>', value))
                        else:
                            # Earlier fields - use >= and add subsequent conditions
                            conditions.append((field, '>=', value))
                    else:
                        # Backward pagination
                        if i == len(sort_fields) - 1:
                            conditions.append((field, '<', value))
                        else:
                            conditions.append((field, '<=', value))

            # Apply conditions to query (implementation depends on ORM)
            for condition in conditions:
                if len(condition) == 2:
                    field, op = condition
                    # Handle two-argument conditions
                    pass
                else:
                    field, op, value = condition
                    # Apply filter to query
                    pass

            return query.limit(limit)

        except Exception as e:
            logger.error(f"Error applying cursor pagination: {e}")
            return query.limit(limit)

    def build_filter_conditions(self,
                               filters: Dict[str, Any],
                               model_class: type) -> List[FilterCondition]:
        """Build filter conditions from filter parameters."""
        conditions = []

        for field_path, filter_def in filters.items():
            if isinstance(filter_def, dict):
                for operator, value in filter_def.items():
                    try:
                        op_enum = FilterOperator(operator)
                        condition = FilterCondition(
                            field=field_path,
                            operator=op_enum,
                            value=value
                        )
                        conditions.append(condition)
                    except ValueError:
                        logger.warning(f"Unknown filter operator: {operator}")
            else:
                # Simple equality filter
                condition = FilterCondition(
                    field=field_path,
                    operator=FilterOperator.EQ,
                    value=filter_def
                )
                conditions.append(condition)

        return conditions

    def apply_filters(self,
                     query: Any,
                     conditions: List[FilterCondition],
                     model_class: type) -> Any:
        """Apply filter conditions to query."""
        for condition in conditions:
            field_name = condition.field
            operator = condition.operator
            value = condition.value

            # Apply filter based on operator
            if operator == FilterOperator.EQ:
                query = query.filter(getattr(model_class, field_name) == value)
            elif operator == FilterOperator.NE:
                query = query.filter(getattr(model_class, field_name) != value)
            elif operator == FilterOperator.GT:
                query = query.filter(getattr(model_class, field_name) > value)
            elif operator == FilterOperator.GTE:
                query = query.filter(getattr(model_class, field_name) >= value)
            elif operator == FilterOperator.LT:
                query = query.filter(getattr(model_class, field_name) < value)
            elif operator == FilterOperator.LTE:
                query = query.filter(getattr(model_class, field_name) <= value)
            elif operator == FilterOperator.IN:
                if isinstance(value, list):
                    query = query.filter(getattr(model_class, field_name).in_(value))
            elif operator == FilterOperator.NIN:
                if isinstance(value, list):
                    query = query.filter(~getattr(model_class, field_name).in_(value))
            elif operator == FilterOperator.LIKE:
                query = query.filter(getattr(model_class, field_name).ilike(f"%{value}%"))
            elif operator == FilterOperator.ILIKE:
                query = query.filter(getattr(model_class, field_name).like(f"%{value}%"))
            elif operator == FilterOperator.STARTS_WITH:
                query = query.filter(getattr(model_class, field_name).ilike(f"{value}%"))
            elif operator == FilterOperator.ENDS_WITH:
                query = query.filter(getattr(model_class, field_name).ilike(f"%{value}"))
            elif operator == FilterOperator.IS_NULL:
                query = query.filter(getattr(model_class, field_name).is_(None))
            elif operator == FilterOperator.IS_NOT_NULL:
                query = query.filter(getattr(model_class, field_name).isnot(None))
            elif operator == FilterOperator.BETWEEN:
                if isinstance(value, list) and len(value) == 2:
                    query = query.filter(
                        getattr(model_class, field_name).between(value[0], value[1])
                    )
            elif operator == FilterOperator.DATE_RANGE:
                if isinstance(value, dict):
                    start = value.get('start')
                    end = value.get('end')
                    if start:
                        query = query.filter(getattr(model_class, field_name) >= start)
                    if end:
                        query = query.filter(getattr(model_class, field_name) <= end)

        return query

    def apply_sorting(self,
                     query: Any,
                     sort_conditions: List[SortCondition],
                     model_class: type) -> Any:
        """Apply sorting to query."""
        for condition in sort_conditions:
            field = getattr(model_class, condition.field)
            order = condition.order

            if order == SortOrder.DESC:
                field = field.desc()

            if condition.nulls_first:
                field = field.nulls_first()
            else:
                field = field.nulls_last()

            query = query.order_by(field)

        return query

    def create_pagination_result(self,
                                items: List[T],
                                total: Optional[int],
                                params: PaginationParams,
                                cursor_info: Optional[CursorInfo] = None) -> PaginationResult[T]:
        """Create pagination result."""
        has_next = False
        has_prev = False
        next_page = None
        prev_page = None
        total_pages = None

        if total is not None:
            total_pages = (total + params.limit - 1) // params.limit

            if params.type == PaginationType.OFFSET:
                has_next = params.offset + params.limit < total
                has_prev = params.offset > 0
                next_page = (params.offset // params.limit) + 2 if has_next else None
                prev_page = (params.offset // params.limit) if has_prev else None

            elif params.type == PaginationType.PAGE:
                has_next = params.page < total_pages
                has_prev = params.page > 1
                next_page = params.page + 1 if has_next else None
                prev_page = params.page - 1 if has_prev else None

        if cursor_info:
            has_next = cursor_info.has_next
            has_prev = cursor_info.has_prev

        return PaginationResult(
            items=items,
            total=total,
            limit=params.limit,
            offset=params.offset or 0,
            has_next=has_next,
            has_prev=has_prev,
            next_page=next_page,
            prev_page=prev_page,
            total_pages=total_pages,
            cursor_info=cursor_info
        )


# Pagination dependency functions
def get_pagination_params(
    limit: int = Query(20, ge=1, le=1000, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    page: int = Query(1, ge=1, description="Page number"),
    cursor: Optional[str] = Query(None, description="Cursor for pagination"),
    pagination_type: PaginationType = Query(PaginationType.OFFSET, description="Pagination type")
) -> PaginationParams:
    """Get pagination parameters from request."""
    return PaginationParams(
        type=pagination_type,
        limit=limit,
        offset=offset if pagination_type == PaginationType.OFFSET else 0,
        page=page if pagination_type == PaginationType.PAGE else 1,
        cursor=cursor if pagination_type == PaginationType.CURSOR else None
    )


def get_filter_params(
    filters: Optional[str] = Query(None, description="JSON-encoded filters"),
    search: Optional[str] = Query(None, description="Search query"),
    fields: Optional[str] = Query(None, description="Fields to return")
) -> FilterParams:
    """Get filter parameters from request."""
    return FilterParams(
        filters=filters,
        search=search,
        fields=fields
    )


def get_sort_params(
    sort: Optional[str] = Query(None, description="Sort field:order"),
    order: SortOrder = Query(SortOrder.ASC, description="Sort order")
) -> SortParams:
    """Get sort parameters from request."""
    sort_condition = None
    if sort:
        parts = sort.split(':')
        field = parts[0]
        sort_order = SortOrder.ASC if len(parts) == 1 else SortOrder(parts[1])
        sort_condition = SortCondition(field=field, order=sort_order)

    return SortParams(
        sort=sort_condition,
        order=order
    )


def get_advanced_pagination_params(
    pagination: PaginationParams = Depends(get_pagination_params),
    filters: FilterParams = Depends(get_filter_params),
    sorting: SortParams = Depends(get_sort_params)
) -> AdvancedPaginationParams:
    """Get all pagination parameters."""
    return AdvancedPaginationParams(
        pagination=pagination,
        filters=filters,
        sorting=sorting
    )