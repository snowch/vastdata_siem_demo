from typing import Optional, List
from pydantic import BaseModel

class File(BaseModel):
    """
    The File object represents the metadata associated with a file stored in a computer system.
    It encompasses information about the file itself, including its attributes, properties, and organizational details.
    """
    name: str  # Required
    type_id: int  # Required

    accessed_time: Optional[int] = None
    accessor: Optional[str] = None  # User
    attributes: Optional[int] = None
    company_name: Optional[str] = None
    confidentiality: Optional[str] = None
    confidentiality_id: Optional[int] = None
    created_time: Optional[int] = None
    creator: Optional[str] = None  # User
    desc: Optional[str] = None
    drive_type: Optional[str] = None
    drive_type_id: Optional[int] = None
    encryption_details: Optional[str] = None  # Encryption Details
    ext: Optional[str] = None
    hashes: Optional[List[str]] = None  # Fingerprint Array
    internal_name: Optional[str] = None
    is_deleted: Optional[bool] = None
    is_encrypted: Optional[bool] = None
    is_system: Optional[bool] = None
    mime_type: Optional[str] = None
    modified_time: Optional[int] = None
    modifier: Optional[str] = None  # User
    owner: Optional[str] = None  # User
    parent_folder: Optional[str] = None
    path: Optional[str] = None
    product: Optional[str] = None  # Product
    security_descriptor: Optional[str] = None
    signature: Optional[str] = None  # Digital Signature
    size: Optional[int] = None
    tags: Optional[dict] = None  # Key:Value object Array
    type: Optional[str] = None
    uid: Optional[str] = None
    uri: Optional[str] = None  # URL String
    url: Optional[str] = None  # Uniform Resource Locator
    version: Optional[str] = None
    volume: Optional[str] = None
    xattributes: Optional[dict] = None  # Object
