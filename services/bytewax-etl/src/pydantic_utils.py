import logging
import pyarrow as pa
from pydantic import BaseModel
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

def get_model_data(instance: BaseModel) -> dict:
    """Get dictionary representation regardless of Pydantic version"""
    if hasattr(instance, 'model_dump'):
        return instance.model_dump()  # Pydantic v2
    else:
        return instance.dict()  # Pydantic v1

def get_model_fields(model_class: BaseModel):
    """Get model fields regardless of Pydantic version"""
    if hasattr(model_class, 'model_fields'):
        return model_class.model_fields  # Pydantic v2
    else:
        return model_class.__fields__  # Pydantic v1

def pydantic_to_arrow_schema(model_class: BaseModel) -> pa.Schema:
    """Convert Pydantic model to PyArrow schema (version-agnostic)"""
    type_mapping = {
        int: pa.int64(),
        str: pa.string(),
        float: pa.float64(),
        bool: pa.bool_(),
    }
    
    fields = []
    model_fields = get_model_fields(model_class)
    
    for field_name, field_info in model_fields.items():
        if hasattr(field_info, 'annotation'):  # Pydantic v2
            python_type = field_info.annotation
        else:  # Pydantic v1
            python_type = field_info.type_
        
        arrow_type = type_mapping.get(python_type, pa.string())
        fields.append(pa.field(field_name, arrow_type))
    
    return pa.schema(fields)

def clean_nested_data(obj: Any) -> Any:
    """
    Recursively clean nested data structures by removing None values.
    """
    if obj is None:
        return None
    elif isinstance(obj, dict):
        # Recursively clean dictionary and remove None values
        cleaned = {}
        for key, value in obj.items():
            cleaned_value = clean_nested_data(value)
            if cleaned_value is not None:
                # For nested dicts, only include if they have content after cleaning
                if isinstance(cleaned_value, dict) and not cleaned_value:
                    continue
                cleaned[key] = cleaned_value
        return cleaned if cleaned else None
    elif isinstance(obj, (list, tuple)):
        # Recursively clean list items and filter out None values
        cleaned_items = []
        for item in obj:
            cleaned_item = clean_nested_data(item)
            if cleaned_item is not None:
                cleaned_items.append(cleaned_item)
        return cleaned_items if cleaned_items else None
    else:
        # Return primitive values as-is
        return obj

def prepare_data_for_arrow(data: Dict[str, Any]) -> Dict[str, List[Any]]:
    """
    Prepare data dictionary for PyArrow by recursively removing None values,
    empty nested structures, and ensuring all remaining values are lists.
    """
    prepared_data = {}
    
    for key, value in data.items():
        # Recursively clean the value
        cleaned_value = clean_nested_data(value)
        
        # Skip None values or empty structures
        if cleaned_value is None:
            continue
            
        # Handle lists/tuples
        if isinstance(cleaned_value, (list, tuple)):
            # Convert to list - already cleaned by clean_nested_data
            if cleaned_value:  # Only include non-empty lists
                prepared_data[key] = list(cleaned_value)
        else:
            # Wrap single non-None values in a list
            prepared_data[key] = [cleaned_value]
    
    return prepared_data

def remove_null_type_columns(table: pa.Table) -> pa.Table:
    """
    Remove columns that have null data type from the Arrow table.
    """
    valid_columns = []
    valid_column_names = []
    
    for i, field in enumerate(table.schema):
        if field.type != pa.null():
            valid_columns.append(table.column(i))
            valid_column_names.append(field.name)
        else:
            logger.debug(f"Removing null type column: {field.name}")
    
    if valid_columns:
        return pa.table(valid_columns, names=valid_column_names)
    else:
        # Return empty table if no valid columns
        return pa.table({})

def pydantic_to_arrow_table(model_class: BaseModel, instance: BaseModel) -> pa.Table:
    """Convert a Pydantic model instance to an Arrow table, recursively removing null fields and null type columns."""
    model_data = get_model_data(instance)
    
    # Recursively clean data to remove None values and empty nested structures
    prepared_data = prepare_data_for_arrow(model_data)
    
    # Return empty table if no valid data
    if not prepared_data:
        logger.debug("No valid data after cleaning - returning empty table")
        return pa.table({})
    
    try:
        # Let PyArrow infer the schema from the actual data
        table = pa.table(prepared_data)
        
        # Remove any columns that have null data type
        table = remove_null_type_columns(table)
        
        logger.debug(f"Created pa_table with {len(table.column_names)} columns: {table.column_names}")
        return table
    except Exception as e:
        logger.debug(f"Error creating Arrow table: {e}")
        # If there's still an issue, create an empty table
        return pa.table({})
