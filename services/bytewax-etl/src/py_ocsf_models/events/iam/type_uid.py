from enum import IntEnum


class AuthenticationTypeUID(IntEnum):
    """
    The event/finding type ID for Authentication events. 
    It identifies the event's semantics and structure. 
    The value is calculated by the logging system as: class_uid * 100 + activity_id.
    """
    
    Unknown = 300200
    """Authentication: Unknown - The event activity is unknown."""
    
    Logon = 300201
    """Authentication: Logon - A new logon session was requested."""
    
    Logoff = 300202
    """Authentication: Logoff - A logon session was terminated and no longer exists."""
    
    AuthenticationTicket = 300203
    """Authentication: Authentication Ticket - A Kerberos authentication ticket (TGT) was requested."""
    
    ServiceTicketRequest = 300204
    """Authentication: Service Ticket Request - A Kerberos service ticket was requested."""
    
    ServiceTicketRenew = 300205
    """Authentication: Service Ticket Renew - A Kerberos service ticket was renewed."""
    
    Preauth = 300206
    """Authentication: Preauth - A preauthentication stage was engaged."""
    
    Other = 300299
    """Authentication: Other - The event activity is not mapped."""
