from enum import IntEnum


class IAMCategoryUID(IntEnum):
    """
    The category unique identifier of the IAM event.
    """
    
    IdentityAndAccessManagement = 3
    """Identity & Access Management (IAM) events relate to the supervision of the system's authentication and access control model. Examples of such events are the success or failure of authentication, granting of authority, password change, entity change, privileged use etc."""
