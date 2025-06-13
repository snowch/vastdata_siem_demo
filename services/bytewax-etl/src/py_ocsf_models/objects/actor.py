from typing import Optional
from pydantic.v1 import BaseModel

from py_ocsf_models.objects.user import User
from py_ocsf_models.objects.session import Session
from py_ocsf_models.objects.process import Process


class Actor(BaseModel):
    """
    The actor object describes details about the user/role/process that was the source of the activity.
    
    Attributes:
    - User (user) [Optional]: The user associated with the actor.
    - Session (session) [Optional]: The session associated with the actor.
    - Process (process) [Optional]: The process associated with the actor.
    - Authorization (authorization) [Optional]: The authorization information for the actor.
    """
    
    user: Optional[User]
    session: Optional[Session]
    process: Optional[Process]
    authorization: Optional[str]
