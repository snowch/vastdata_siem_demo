from typing import Optional
from pydantic.v1 import BaseModel


class NetworkEndpoint(BaseModel):
    """
    The network endpoint object describes a network endpoint, including its IP address, port, hostname, and other network-related information.
    
    Attributes:
    - IP Address (ip) [Optional]: The IP address of the endpoint, in either IPv4 or IPv6 format.
    - Port (port) [Optional]: The port number of the endpoint.
    - Hostname (hostname) [Optional]: The hostname of the endpoint.
    - Domain (domain) [Optional]: The domain of the endpoint.
    - MAC Address (mac) [Optional]: The MAC address of the endpoint.
    - Subnet (subnet) [Optional]: The subnet of the endpoint.
    - VLAN (vlan) [Optional]: The VLAN of the endpoint.
    """
    
    ip: Optional[str]
    port: Optional[int]
    hostname: Optional[str]
    domain: Optional[str]
    mac: Optional[str]
    subnet: Optional[str]
    vlan: Optional[str]
