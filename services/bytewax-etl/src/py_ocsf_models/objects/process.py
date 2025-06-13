from datetime import datetime
from typing import Optional
from pydantic.v1 import BaseModel


class Process(BaseModel):
    """
    The process object describes a running process, including its name, command line, process ID, and other process-related information.
    
    Attributes:
    - Name (name) [Optional]: The process name.
    - Command Line (cmd_line) [Optional]: The full command line used to launch the process.
    - Process ID (pid) [Optional]: The process identifier.
    - Parent Process ID (parent_pid) [Optional]: The parent process identifier.
    - Unique ID (uid) [Optional]: The unique identifier of the process.
    - Created Time (created_time) [Optional]: The time when the process was created.
    - Terminated Time (terminated_time) [Optional]: The time when the process was terminated.
    - File Path (file_path) [Optional]: The full path to the process executable file.
    """
    
    name: Optional[str]
    cmd_line: Optional[str]
    pid: Optional[int]
    parent_pid: Optional[int]
    uid: Optional[str]
    created_time: Optional[datetime]
    terminated_time: Optional[datetime]
    file_path: Optional[str]
