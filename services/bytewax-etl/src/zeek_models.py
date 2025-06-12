from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# Pydantic models for Zeek log types
class ZeekAnalyzerLog(BaseModel):
    """Zeek Analyzer log model."""
    ts: Optional[datetime] = None
    cause: Optional[str] = None
    analyzer_kind: Optional[str] = None
    analyzer_name: Optional[str] = None
    uid: Optional[str] = None
    fuid: Optional[str] = None
    id_orig_h: Optional[str] = Field(None, alias="id.orig_h")
    id_orig_p: Optional[int] = Field(None, alias="id.orig_p")
    id_resp_h: Optional[str] = Field(None, alias="id.resp_h")
    id_resp_p: Optional[int] = Field(None, alias="id.resp_p")
    failure_reason: Optional[str] = None
    failure_data: Optional[str] = None

class ZeekConnLog(BaseModel):
    """Zeek Connection log model."""
    ts: Optional[datetime] = None
    uid: Optional[str] = None
    id_orig_h: Optional[str] = Field(None, alias="id.orig_h")
    id_orig_p: Optional[int] = Field(None, alias="id.orig_p")
    id_resp_h: Optional[str] = Field(None, alias="id.resp_h")
    id_resp_p: Optional[int] = Field(None, alias="id.resp_p")
    proto: Optional[str] = None
    service: Optional[str] = None
    duration: Optional[float] = None
    orig_bytes: Optional[int] = None
    resp_bytes: Optional[int] = None
    conn_state: Optional[str] = None
    local_orig: Optional[bool] = None
    local_resp: Optional[bool] = None
    missed_bytes: Optional[int] = None
    history: Optional[str] = None
    orig_pkts: Optional[int] = None
    orig_ip_bytes: Optional[int] = None
    resp_pkts: Optional[int] = None
    resp_ip_bytes: Optional[int] = None
    ip_proto: Optional[int] = None
    tunnel_parents: Optional[str] = None
    vlan: Optional[int] = None
    inner_vlan: Optional[int] = None
    orig_l2_addr: Optional[str] = None
    resp_l2_addr: Optional[str] = None
    community_id: Optional[str] = None
    orig_shim: Optional[str] = None
    resp_shim: Optional[str] = None

class ZeekHttpLog(BaseModel):
    """Zeek HTTP log model."""
    ts: Optional[datetime] = None
    uid: Optional[str] = None
    id_orig_h: Optional[str] = Field(None, alias="id.orig_h")
    id_orig_p: Optional[int] = Field(None, alias="id.orig_p")
    id_resp_h: Optional[str] = Field(None, alias="id.resp_h")
    id_resp_p: Optional[int] = Field(None, alias="id.resp_p")
    trans_depth: Optional[int] = None
    method: Optional[str] = None
    host: Optional[str] = None
    uri: Optional[str] = None
    referrer: Optional[str] = None
    version: Optional[str] = None
    user_agent: Optional[str] = None
    origin: Optional[str] = None
    request_body_len: Optional[int] = None
    response_body_len: Optional[int] = None
    status_code: Optional[int] = None
    status_msg: Optional[str] = None
    info_code: Optional[int] = None
    info_msg: Optional[str] = None
    tags: Optional[list] = None
    username: Optional[str] = None
    password: Optional[str] = None
    proxied: Optional[str] = None
    orig_fuids: Optional[str] = None
    orig_filenames: Optional[str] = None
    orig_mime_types: Optional[str] = None
    resp_fuids: Optional[str] = None
    resp_filenames: Optional[str] = None
    resp_mime_types: Optional[str] = None

class ZeekDnsLog(BaseModel):
    """Zeek DNS log model."""
    ts: Optional[datetime] = None
    uid: Optional[str] = None
    id_orig_h: Optional[str] = Field(None, alias="id.orig_h")
    id_orig_p: Optional[int] = Field(None, alias="id.orig_p")
    id_resp_h: Optional[str] = Field(None, alias="id.resp_h")
    id_resp_p: Optional[int] = Field(None, alias="id.resp_p")
    proto: Optional[str] = None
    trans_id: Optional[int] = None
    rtt: Optional[float] = None
    query: Optional[str] = None
    qclass: Optional[int] = None
    qclass_name: Optional[str] = None
    qtype: Optional[int] = None
    qtype_name: Optional[str] = None
    rcode: Optional[int] = None
    rcode_name: Optional[str] = None
    AA: Optional[bool] = None
    TC: Optional[bool] = None
    RD: Optional[bool] = None
    RA: Optional[bool] = None
    Z: Optional[int] = None
    answers: Optional[str] = None
    TTLs: Optional[str] = None
    rejected: Optional[bool] = None

class ZeekSslLog(BaseModel):
    """Zeek SSL log model."""
    ts: Optional[datetime] = None
    uid: Optional[str] = None
    id_orig_h: Optional[str] = Field(None, alias="id.orig_h")
    id_orig_p: Optional[int] = Field(None, alias="id.orig_p")
    id_resp_h: Optional[str] = Field(None, alias="id.resp_h")
    id_resp_p: Optional[int] = Field(None, alias="id.resp_p")
    version: Optional[str] = None
    cipher: Optional[str] = None
    curve: Optional[str] = None
    server_name: Optional[str] = None
    resumed: Optional[bool] = None
    last_alert: Optional[str] = None
    next_protocol: Optional[str] = None
    established: Optional[bool] = None
    cert_chain_fuids: Optional[str] = None
    client_cert_chain_fuids: Optional[str] = None
    subject: Optional[str] = None
    issuer: Optional[str] = None
    client_subject: Optional[str] = None
    client_issuer: Optional[str] = None
    validation_status: Optional[str] = None

class ZeekWeirdLog(BaseModel):
    """Zeek Weird log model."""
    ts: Optional[datetime] = None
    uid: Optional[str] = None
    id_orig_h: Optional[str] = Field(None, alias="id.orig_h")
    id_orig_p: Optional[int] = Field(None, alias="id.orig_p")
    id_resp_h: Optional[str] = Field(None, alias="id.resp_h")
    id_resp_p: Optional[int] = Field(None, alias="id.resp_p")
    name: Optional[str] = None
    addl: Optional[str] = None
    notice: Optional[bool] = None
    peer: Optional[str] = None

class ZeekFtpLog(BaseModel):
    """Zeek FTP log model."""
    ts: Optional[datetime] = None
    uid: Optional[str] = None
    id_orig_h: Optional[str] = Field(None, alias="id.orig_h")
    id_orig_p: Optional[int] = Field(None, alias="id.orig_p")
    id_resp_h: Optional[str] = Field(None, alias="id.resp_h")
    id_resp_p: Optional[int] = Field(None, alias="id.resp_p")
    user: Optional[str] = None
    command: Optional[str] = None
    arg: Optional[str] = None

class ZeekGenericLog(BaseModel):
    """Generic Zeek log model for unknown log types."""
    pass
