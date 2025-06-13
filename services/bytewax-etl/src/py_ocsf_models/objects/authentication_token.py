from typing import Optional
from pydantic.v1 import BaseModel


class AuthenticationToken(BaseModel):
    """
    The authentication token, ticket, or assertion, e.g. Kerberos, OIDC, SAML.
    
    Attributes:
    - Type (type) [Optional]: The authentication token type.
    - Value (value) [Optional]: The authentication token value.
    - Issuer (issuer) [Optional]: The token issuer.
    - Expiration Time (expiration_time) [Optional]: The token expiration time.
    """
    
    type: Optional[str]
    value: Optional[str]
    issuer: Optional[str]
    expiration_time: Optional[int]
