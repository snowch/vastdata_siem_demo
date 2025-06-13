from typing import Optional, List
from pydantic import BaseModel
from py_ocsf_models.objects import Device, File, Metadata

class FileSystemActivity(BaseModel):
    """
    File System Activity events report when a process performs an action on a file or folder.
    """
    activity_id: int
    category_uid: int
    class_uid: int
    device: Device
    file: File
    metadata: Metadata
    time: int

    create_mask: Optional[str] = None
    file_diff: Optional[str] = None
    file_result: Optional[str] = None
    message: Optional[str] = None
    observables: Optional[str] = None  # Observable Array
    status: Optional[str] = None
    status_code: Optional[str] = None
    status_detail: Optional[str] = None
    timezone_offset: Optional[int] = None

    access_mask: Optional[int] = None
    activity_name: Optional[str] = None
    category_name: Optional[str] = None
    class_name: Optional[str] = None
    component: Optional[str] = None
    connection_uid: Optional[str] = None
    count: Optional[int] = None
    duration: Optional[int] = None
    end_time: Optional[int] = None
    enrichments: Optional[str] = None  # Enrichment Array
    raw_data: Optional[str] = None
    raw_data_size: Optional[int] = None
    severity: Optional[str] = None
    severity_id: Optional[int] = None
    start_time: Optional[int] = None
    status_id: Optional[int] = None
    type_name: Optional[str] = None
    type_uid: Optional[int] = None
    unmapped: Optional[str] = None
