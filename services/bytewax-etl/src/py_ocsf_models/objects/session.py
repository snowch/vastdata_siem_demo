from datetime import datetime
from typing import Optional
from pydantic.v1 import BaseModel


class Session(BaseModel):
    """
    The session object describes the authenticated user or service session.
    
    Attributes:
    - Unique ID (uid) [Optional]: The unique identifier of the session.
    - Created Time (created_time) [Optional]: The time when the session was created.
    - Expiration Time (expiration_time) [Optional]: The time when the session expires.
    - Is Remote (is_remote) [Optional]: Indicates whether the session is remote.
    - Issuer (issuer) [Optional]: The session issuer.
    """
    
    uid: Optional[str]
    created_time: Optional[datetime]
    expiration_time: Optional[datetime]
    is_remote: Optional[bool]
    issuer: Optional[str]
