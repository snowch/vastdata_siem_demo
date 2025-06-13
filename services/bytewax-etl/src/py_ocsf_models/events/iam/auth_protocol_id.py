from enum import IntEnum


class AuthProtocolID(IntEnum):
    """
    The normalized identifier of the authentication protocol used to create the user session.
    """
    
    Unknown = 0
    """The authentication protocol is unknown."""
    
    NTLM = 1
    """NTLM authentication protocol."""
    
    Kerberos = 2
    """Kerberos authentication protocol."""
    
    Digest = 3
    """Digest authentication protocol."""
    
    OpenID = 4
    """OpenID authentication protocol."""
    
    SAML = 5
    """SAML authentication protocol."""
    
    OAuth2 = 6
    """OAuth 2.0 authentication protocol."""
    
    PAP = 7
    """Password Authentication Protocol."""
    
    CHAP = 8
    """Challenge-Handshake Authentication Protocol."""
    
    EAP = 9
    """Extensible Authentication Protocol."""
    
    RADIUS = 10
    """Remote Authentication Dial-In User Service."""
    
    BasicAuthentication = 11
    """Basic Authentication protocol."""
    
    LDAP = 12
    """Lightweight Directory Access Protocol."""
    
    Other = 99
    """The authentication protocol is not mapped. See the auth_protocol attribute, which contains a data source specific value."""
