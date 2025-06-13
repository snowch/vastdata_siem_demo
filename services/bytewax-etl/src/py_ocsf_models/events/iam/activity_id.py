from enum import IntEnum


class AuthenticationActivityID(IntEnum):
    """
    The normalized identifier of the activity that triggered the Authentication event.
    """
    
    Unknown = 0
    """The event activity is unknown."""
    
    Logon = 1
    """A new logon session was requested."""
    
    Logoff = 2
    """A logon session was terminated and no longer exists."""
    
    AuthenticationTicket = 3
    """A Kerberos authentication ticket (TGT) was requested."""
    
    ServiceTicketRequest = 4
    """A Kerberos service ticket was requested."""
    
    ServiceTicketRenew = 5
    """A Kerberos service ticket was renewed."""
    
    Preauth = 6
    """A preauthentication stage was engaged."""
    
    Other = 99
    """The event activity is not mapped. See the activity_name attribute, which contains a data source specific value."""
