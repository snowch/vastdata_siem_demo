from typing import Optional
from pydantic.v1 import BaseModel


class AuthenticationFactor(BaseModel):
    """
    Describes a category of methods used for identity verification in an authentication attempt.
    
    Attributes:
    - Type (type) [Optional]: The authentication factor type.
    - Value (value) [Optional]: The authentication factor value.
    """
    
    type: Optional[str]
    value: Optional[str]
