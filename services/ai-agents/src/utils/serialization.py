import numpy as np

def truncate_embedding_recursive(obj, max_dims=5):
    """Recursively truncate any embedding vectors found in nested structures."""
    if isinstance(obj, np.ndarray):
        if obj.ndim == 2:
            truncated_rows = []
            for row in obj:
                row_list = row.tolist()
                if len(row_list) > max_dims:
                    truncated_row = row_list[:max_dims] + ["..."]
                else:
                    truncated_row = row_list
                truncated_rows.append(truncated_row)
            return truncated_rows
        elif obj.ndim == 1:
            arr_list = obj.tolist()
            if len(arr_list) > max_dims:
                return arr_list[:max_dims] + ["..."]
            else:
                return arr_list
        else:
            return truncate_embedding_recursive(obj.tolist(), max_dims)
    elif isinstance(obj, list):
        if obj and all(isinstance(x, (int, float, np.number)) for x in obj):
            if len(obj) > max_dims:
                return obj[:max_dims] + ["..."]
            else:
                return obj
        else:
            return [truncate_embedding_recursive(item, max_dims) for item in obj]
    else:
        return obj

def sanitize_chroma_results(chroma_results):
    """Convert numpy arrays in ChromaDB results to lists for JSON serialization."""
    if not isinstance(chroma_results, dict):
        return chroma_results
    
    sanitized = {}
    for key, value in chroma_results.items():
        if key == 'embeddings':
            sanitized[key] = truncate_embedding_recursive(value, max_dims=5)
        elif isinstance(value, np.ndarray):
            sanitized[key] = value.tolist()
        elif isinstance(value, list):
            sanitized[key] = []
            for item in value:
                if isinstance(item, np.ndarray):
                    sanitized[key].append(item.tolist())
                elif isinstance(item, list):
                    nested_list = []
                    for nested_item in item:
                        if isinstance(nested_item, np.ndarray):
                            nested_list.append(nested_item.tolist())
                        else:
                            nested_list.append(nested_item)
                    sanitized[key].append(nested_list)
                else:
                    sanitized[key].append(item)
        else:
            sanitized[key] = value
    
    return sanitized
