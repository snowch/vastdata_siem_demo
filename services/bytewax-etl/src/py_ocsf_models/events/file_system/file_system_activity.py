from datetime import datetime
from typing import Optional, List
from pydantic.v1 import BaseModel

from py_ocsf_models.events.findings.severity_id import SeverityID
from py_ocsf_models.events.findings.status_id import StatusID
from py_ocsf_models.objects.device import Device
from py_ocsf_models.objects.file import File
from py_ocsf_models.objects.metadata import Metadata
from py_ocsf_models.objects.enrichment import Enrichment
from py_ocsf_models.objects.observable import Observable

class FileSystemActivity(BaseModel):
    """
    File System Activity events report when a process performs an action on a file or folder.
    """
    # Required fields
    activity_id: int
    category_uid: int
    class_uid: int
    metadata: Metadata
    severity_id: SeverityID
    time: int
    
    # Optional/Recommended fields
    access_mask: Optional[int] = None
    activity_name: Optional[str] = None
    category_name: Optional[str] = None
    class_name: Optional[str] = None
    component: Optional[str] = None
    connection_uid: Optional[str] = None
    count: Optional[int] = None
    create_mask: Optional[str] = None
    device: Optional[Device] = None
    duration: Optional[int] = None
    end_time: Optional[int] = None
    end_time_dt: Optional[datetime] = None
    enrichments: Optional[List[Enrichment]] = None
    file: Optional[File] = None
    file_diff: Optional[str] = None
    file_result: Optional[str] = None
    message: Optional[str] = None
    observables: Optional[List[Observable]] = None
    raw_data: Optional[str] = None
    raw_data_size: Optional[int] = None
    severity: Optional[str] = None
    start_time: Optional[int] = None
    start_time_dt: Optional[datetime] = None
    status: Optional[str] = None
    status_code: Optional[str] = None
    status_detail: Optional[str] = None
    status_id: Optional[StatusID] = None
    time_dt: Optional[datetime] = None
    timezone_offset: Optional[int] = None
    type_name: Optional[str] = None
    type_uid: Optional[int] = None
    unmapped: Optional[object] = None
