from enum import IntEnum


class LogonTypeID(IntEnum):
    """
    The normalized logon type identifier.
    """
    
    Unknown = 0
    """The logon type is unknown."""
    
    System = 1
    """Used only by the System account, for example at system startup."""
    
    Interactive = 2
    """A local logon to device console."""
    
    Network = 3
    """A user or device logged onto this device from the network."""
    
    Batch = 4
    """A batch server logon, where processes may be executing on behalf of a user without their direct intervention."""
    
    OSService = 5
    """A logon by a service or daemon that was started by the OS."""
    
    Unlock = 7
    """A user unlocked the device."""
    
    NetworkCleartext = 8
    """A user logged on to this device from the network. The user's password in the authentication package was not hashed."""
    
    NewCredentials = 9
    """A caller cloned its current token and specified new credentials for outbound connections. The new logon session has the same local identity, but uses different credentials for other network connections."""
    
    RemoteInteractive = 10
    """A remote logon using Terminal Services or remote desktop application."""
    
    CachedInteractive = 11
    """A user logged on to this device with network credentials that were stored locally on the device and the domain controller was not contacted to verify the credentials."""
    
    CachedRemoteInteractive = 12
    """Same as Remote Interactive. This is used for internal auditing."""
    
    CachedUnlock = 13
    """Workstation logon."""
    
    Other = 99
    """The logon type is not mapped. See the logon_type attribute, which contains a data source specific value."""
