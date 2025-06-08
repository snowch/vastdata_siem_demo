#!/usr/bin/env python3

import datetime
import time
import random
import logging
import json
from datetime import datetime
from scapy.all import *

class SIEMEvent:
    """Enhanced SIEM Event that generates proper TCP connections for Zeek monitoring"""
    
    def __init__(self, event_type, user=None, src_ip=None, dst_ip=None, timestamp=None):
        logging.info(f"Creating enhanced SIEMEvent: {event_type}, user={user}, src_ip={src_ip}, dst_ip={dst_ip}")
        self.event_type = event_type
        self.user = user or f"user{random.randint(1, 100)}"
        self.src_ip = src_ip or f"192.168.100.{random.randint(10, 19)}"
        self.dst_ip = dst_ip or f"192.168.100.{random.randint(20, 29)}"
        self.timestamp = timestamp or datetime.utcnow()

    def emit_log(self):
        """Write event to log file in format expected by Fluentd"""
        # Use the original format that Fluentd expects
        # log_entry = f"{self.timestamp.isoformat()} event={self.event_type} user={self.user} src_ip={self.src_ip} dst_ip={self.dst_ip}"
        log_entry = f"{self.timestamp} event={self.event_type} user={self.user} src_ip={self.src_ip} dst_ip={self.dst_ip}"

        try:
            with open("/logs/events.log", "a") as f:
                f.write(log_entry + "\n")
            logging.info(f"SIEM event logged: {log_entry}")
        except Exception as e:
            logging.error(f"Failed to write SIEM log: {e}")

    def emit_network(self):
        """Generate realistic TCP connection that Zeek will capture"""
        # Get port based on event type
        port_map = {
            "ssh_login_success": 22,
            "ssh_login_failure": 22,
            "web_login_success": 80,
            "web_login_failure": 80,
            "file_access": 445,
            "brute_force_attack": 22,
            "sql_injection_attempt": 80,
            "malware_detection": 443,
            "data_exfiltration": 443
        }
        
        port = port_map.get(self.event_type, 22)
        src_port = random.randint(1024, 65535)
        
        logging.info(f"Generating TCP connection: {self.src_ip}:{src_port} -> {self.dst_ip}:{port}")
        
        try:
            # Step 1: TCP Handshake (SYN)
            syn_packet = IP(src=self.src_ip, dst=self.dst_ip)/TCP(sport=src_port, dport=port, flags="S", seq=1000)
            send(syn_packet, verbose=0)
            time.sleep(0.1)
            
            # Step 2: SYN-ACK (simulate server response)
            synack_packet = IP(src=self.dst_ip, dst=self.src_ip)/TCP(sport=port, dport=src_port, flags="SA", seq=2000, ack=1001)
            send(synack_packet, verbose=0)
            time.sleep(0.1)
            
            # Step 3: ACK (complete handshake)
            ack_packet = IP(src=self.src_ip, dst=self.dst_ip)/TCP(sport=src_port, dport=port, flags="A", seq=1001, ack=2001)
            send(ack_packet, verbose=0)
            time.sleep(0.2)
            
            # Step 4: Send application data based on event type
            payload = self._get_event_payload()
            if payload:
                data_packet = IP(src=self.src_ip, dst=self.dst_ip)/TCP(sport=src_port, dport=port, flags="PA", seq=1001)/Raw(load=payload)
                send(data_packet, verbose=0)
                time.sleep(0.2)
                
                # Server response
                response = self._get_server_response()
                resp_packet = IP(src=self.dst_ip, dst=self.src_ip)/TCP(sport=port, dport=src_port, flags="PA", seq=2001)/Raw(load=response)
                send(resp_packet, verbose=0)
                time.sleep(0.2)
            
            # Step 5: Close connection properly
            if "success" in self.event_type:
                # Normal close with FIN
                fin_packet = IP(src=self.src_ip, dst=self.dst_ip)/TCP(sport=src_port, dport=port, flags="FA", seq=1002)
                send(fin_packet, verbose=0)
                time.sleep(0.1)
                
                finack_packet = IP(src=self.dst_ip, dst=self.src_ip)/TCP(sport=port, dport=src_port, flags="FA", seq=2002)
                send(finack_packet, verbose=0)
                time.sleep(0.1)
                
                final_ack = IP(src=self.src_ip, dst=self.dst_ip)/TCP(sport=src_port, dport=port, flags="A", seq=1003)
                send(final_ack, verbose=0)
            else:
                # Failed connection - RST
                rst_packet = IP(src=self.dst_ip, dst=self.src_ip)/TCP(sport=port, dport=src_port, flags="R", seq=2002)
                send(rst_packet, verbose=0)
            
            logging.info(f"TCP connection sequence completed for {self.event_type}")
            
        except Exception as e:
            logging.error(f"Failed to generate network traffic: {e}")

    def _get_event_payload(self):
        """Get event-specific payload"""
        payloads = {
            "ssh_login_success": f"SSH-2.0-OpenSSH_8.0\nuser: {self.user}\nauth_success",
            "ssh_login_failure": f"SSH-2.0-OpenSSH_8.0\nuser: {self.user}\nauth_failed",
            "web_login_success": f"POST /login HTTP/1.1\nHost: webapp\nuser={self.user}&pass=valid",
            "web_login_failure": f"POST /login HTTP/1.1\nHost: webapp\nuser={self.user}&pass=invalid",
            "sql_injection_attempt": "GET /search?q=' UNION SELECT * FROM users-- HTTP/1.1\nHost: webapp",
            "file_access": f"SMB_OPEN file_{random.randint(1,100)}.txt",
            "malware_detection": f"MALWARE_BEACON_{random.randint(1000,9999)}",
            "data_exfiltration": "EXFIL_DATA_" + "SENSITIVE_" * 10,
            "brute_force_attack": f"SSH-2.0-OpenSSH_8.0\nuser: {self.user}\nattempt_{random.randint(1,100)}"
        }
        return payloads.get(self.event_type, "GENERIC_DATA")

    def _get_server_response(self):
        """Get server response based on event type"""
        responses = {
            "ssh_login_success": "SSH-2.0-OpenSSH_8.0\nlogin_successful",
            "ssh_login_failure": "SSH-2.0-OpenSSH_8.0\nauthentication_failed",
            "web_login_success": "HTTP/1.1 200 OK\nSet-Cookie: session=abc123",
            "web_login_failure": "HTTP/1.1 401 Unauthorized\nLogin Failed",
            "sql_injection_attempt": "HTTP/1.1 500 Internal Server Error\nDatabase Error",
            "file_access": "SMB_OPEN_RESPONSE STATUS_SUCCESS",
            "malware_detection": f"C2_RESPONSE_{random.randint(1000,9999)}",
            "data_exfiltration": f"UPLOAD_ACK_{random.randint(1,100)}_BYTES",
            "brute_force_attack": "SSH-2.0-OpenSSH_8.0\nauthentication_failed"
        }
        return responses.get(self.event_type, "SERVER_RESPONSE")

    def trigger(self):
        """Trigger both log and network components (enhanced version)"""
        logging.info(f"Triggering enhanced SIEM event: {self.event_type}")
        
        # First emit the log entry
        self.emit_log()
        
        # Small delay, then generate network traffic
        time.sleep(0.5)
        
        # Generate proper TCP connection
        self.emit_network()
        
        return {
            "event_type": self.event_type,
            "user": self.user,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "timestamp": self.timestamp.isoformat()
        }
    
