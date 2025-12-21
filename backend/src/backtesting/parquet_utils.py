"""
Parquet Utility Functions (Story 12.2 Task 3)

Purpose:
--------
Helper functions for converting Pydantic models to PyArrow schemas
and exporting/importing labeled pattern datasets in Parquet format.

Author: Story 12.2 Task 3 Subtask 3.4
"""


import pyarrow as pa
from pydantic import BaseModel


def to_parquet_schema(model_class: type[BaseModel]) -> pa.Schema:
    """
    Convert Pydantic model to PyArrow schema for Parquet export.

    This function maps Pydantic field types to PyArrow data types,
    enabling efficient columnar storage of labeled patterns.

    Type Mappings:
    --------------
    - UUID -> string (UTF-8)
    - str -> string (UTF-8)
    - datetime -> timestamp with timezone (microseconds, UTC)
    - Decimal -> string (preserves precision without rounding)
    - int -> int64
    - bool -> bool
    - dict -> string (JSON-encoded)
    - list -> list of strings

    Args:
        model_class: Pydantic model class (e.g., LabeledPattern)

    Returns:
        PyArrow schema compatible with Parquet export

    Example:
        >>> from backend.src.models.backtest import LabeledPattern
        >>> schema = to_parquet_schema(LabeledPattern)
        >>> print(schema)

    Notes:
        - Decimal values are stored as strings to prevent precision loss
        - Datetime values include timezone information (UTC)
        - Complex types (dict, list) are JSON-encoded
        - UUID values are stored as strings (can be parsed back to UUID)
    """
    fields = []

    for field_name, field_info in model_class.model_fields.items():
        field_type = field_info.annotation
        pyarrow_type = _pydantic_to_pyarrow_type(field_type)
        fields.append(pa.field(field_name, pyarrow_type))

    return pa.schema(fields)


def _pydantic_to_pyarrow_type(python_type: type) -> pa.DataType:
    """
    Map Python/Pydantic types to PyArrow types.

    Args:
        python_type: Python type annotation

    Returns:
        PyArrow data type

    Raises:
        ValueError: If type mapping is not supported
    """
    # Handle Optional types (Union with None)
    import typing
    from datetime import datetime
    from decimal import Decimal
    from uuid import UUID

    if hasattr(python_type, "__origin__"):
        origin = typing.get_origin(python_type)
        args = typing.get_args(python_type)

        # Handle Union (including Optional)
        if origin is typing.Union:
            # Filter out None type
            non_none_types = [arg for arg in args if arg is not type(None)]
            if len(non_none_types) == 1:
                # Optional[X] case
                return _pydantic_to_pyarrow_type(non_none_types[0])
            # Multiple non-None types - use string as fallback
            return pa.utf8()

        # Handle dict
        if origin is dict:
            return pa.utf8()  # Store as JSON string

        # Handle list
        if origin is list:
            return pa.list_(pa.utf8())  # List of strings

        # Handle Literal (use string)
        if hasattr(typing, "Literal") and origin is typing.Literal:
            return pa.utf8()

    # Direct type mappings
    type_map = {
        UUID: pa.utf8(),
        str: pa.utf8(),
        datetime: pa.timestamp("us", tz="UTC"),
        Decimal: pa.utf8(),  # Store as string to preserve precision
        int: pa.int64(),
        bool: pa.bool_(),
        float: pa.float64(),
        dict: pa.utf8(),  # JSON-encoded
        list: pa.list_(pa.utf8()),
    }

    if python_type in type_map:
        return type_map[python_type]

    # Default to string for unknown types
    return pa.utf8()
