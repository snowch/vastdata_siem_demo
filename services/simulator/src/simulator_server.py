#!/usr/bin/env python3
"""
Scapy Traffic Generator Web Interface with Virtual Network Support and SIEM Events
Provides REST API and web interface to generate network traffic on isolated virtual interfaces
"""
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(filename)s - %(levelname)s - %(funcName)s - %(message)s')
logging.getLogger('kafka').setLevel(logging.ERROR)

from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
import threading
import time
import os
import json
import subprocess
from datetime import datetime
from scapy.all import *
import random
from network_traffic_generator import NetworkTrafficGenerator
from enhanced_traffic_generator import EnhancedTrafficGenerator
from siem_event_generator import SIEMEvent

class SIEMEventScenario:
    """Manager for SIEM event scenarios"""
    
    def __init__(self):
        self.running = False
    
    def generate_mixed_siem_events(self, duration=60, events_per_minute=4):
        """Generate mixed SIEM events for general monitoring"""
        self.running = True
        logging.info(f"Starting mixed SIEM events scenario for {duration}s")

        start_time = time.time()
        end_time = start_time + duration
        event_interval = 60.0 / events_per_minute
        next_event_time = start_time
        
        # Weighted event types (normal operations vs security events)
        event_weights = {
            "ssh_login_success": 30,
            "web_login_success": 25,
            "file_access": 20,
            "ssh_login_failure": 10,
            "web_login_failure": 8,
            "sql_injection_attempt": 3,
            "brute_force_attack": 2,
            "malware_detection": 1,
            "data_exfiltration": 1
        }
        
        # Create weighted list for random selection
        weighted_events = []
        for event_type, weight in event_weights.items():
            weighted_events.extend([event_type] * weight)
        
        users = ["alice", "bob", "charlie", "admin", "service_account", "guest"]
        
        while self.running and time.time() < end_time:
            current_time = time.time()
            
            if current_time >= next_event_time:
                event_type = random.choice(weighted_events)
                user = random.choice(users)
                
                event = SIEMEvent(
                    event_type=event_type,
                    user=user,
                    src_ip=f"192.168.100.{random.randint(10, 19)}",
                    dst_ip=f"192.168.100.{random.randint(20, 29)}"
                )
                
                event.trigger()
                next_event_time += event_interval
            
            time.sleep(0.1)

        self.running = False

try:
    from kafka import KafkaConsumer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    logging.warning("kafka-python not available. Kafka consumer will be disabled.")

app = Flask(__name__)
CORS(app)

# Global variables for traffic generation control
traffic_threads = {}
active_sessions = {}
kafka_messages = []
kafka_consumer_thread = None
kafka_running = False
continuous_simulation_running = False
continuous_simulation_thread = None
continuous_simulation = None
available_topics = set()  # Track available topics for filtering
kafka_consumer_instance = None  # Store consumer instance globally

class KafkaMessageConsumer:
    def __init__(self, broker=None, topics=None):
        if not broker or not topics:
            raise ValueError("Kafka broker and topics must be provided")
        self.broker = broker
        self.topics = topics if isinstance(topics, list) else [topics]
        self.running = False
        self.consumer = None
        
    def start_consuming(self):
        """Start consuming Kafka messages from multiple topics in a separate thread"""
        global available_topics, kafka_messages, kafka_running
        
        if not KAFKA_AVAILABLE:
            logging.warning("Kafka consumer not available - kafka-python package not installed")
            return False

        try:
            logging.info(f"Attempting to connect to Kafka broker: {self.broker}")
            logging.info(f"Subscribing to topics: {self.topics}")
            
            self.consumer = KafkaConsumer(
                *self.topics,  # Subscribe to multiple topics
                bootstrap_servers=[self.broker],
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='zeek-web-consumer',
                value_deserializer=lambda x: x.decode('utf-8') if x else None,
                # Remove API version specification to auto-negotiate
                session_timeout_ms=10000,  # Increased to 10 seconds for stability
                request_timeout_ms=20000,  # Increased to 20 seconds
                heartbeat_interval_ms=3000,  # Increased to 3 seconds
                connections_max_idle_ms=120000,  # Increased to 2 minutes
                retry_backoff_ms=1000,  # Increased retry backoff
                max_poll_interval_ms=300000,  # 5 minute max poll interval
                reconnect_backoff_ms=1000,  # Add reconnect backoff
                reconnect_backoff_max_ms=10000,  # Max reconnect backoff
                security_protocol='PLAINTEXT',  # Explicitly set security protocol
                fetch_min_bytes=1,  # Minimum bytes to fetch
                fetch_max_wait_ms=5000,  # Max wait time for fetch
                check_crcs=False  # Disable CRC checks for compatibility
            )
            self.running = True

            logging.info(f"Kafka consumer initialized successfully for topics: {', '.join(self.topics)}")
            
            # Test connection by trying to get partition metadata
            try:
                partitions = self.consumer.partitions_for_topic(self.topics[0])
                if partitions:
                    logging.info(f"Successfully connected to Kafka. Found partitions for {self.topics[0]}: {partitions}")
                else:
                    logging.warning(f"Connected to Kafka but topic {self.topics[0]} has no partitions or doesn't exist")
            except Exception as e:
                logging.warning(f"Kafka partition check failed (but continuing): {e}")

            message_count = 0
            consecutive_errors = 0
            max_consecutive_errors = 10
            logging.info("Starting Kafka message consumption loop...")
            
            # Use poll() method for better control
            while self.running and consecutive_errors < max_consecutive_errors:
                try:
                    # Poll for messages with 5 second timeout
                    message_batch = self.consumer.poll(timeout_ms=5000)
                    
                    if not message_batch:
                        # No messages received, but continue waiting
                        # Reset error counter on successful poll (even if no messages)
                        consecutive_errors = 0
                        continue
                        
                    # Reset error counter on successful message retrieval
                    consecutive_errors = 0
                        
                    # Process all messages in the batch
                    for topic_partition, messages in message_batch.items():
                        for message in messages:
                            if not self.running:
                                break
                                
                            try:
                                message_count += 1
                                # Add topic to available topics set (thread-safe)
                                available_topics.add(message.topic)
                                
                                if message_count == 1:  # Log first message
                                    logging.info(f"Received first message from topic: {message.topic}")
                                elif message_count % 50 == 0:  # Log every 50th message
                                    logging.info(f"Processed {message_count} messages. Current topic: {message.topic}")
                                
                                # Parse the message
                                msg_data = json.loads(message.value) if message.value else {}
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                
                                # Add to global messages list (keep last 100 messages)
                                kafka_messages.append({
                                    'timestamp': timestamp,
                                    'topic': message.topic,
                                    'partition': message.partition,
                                    'offset': message.offset,
                                    'data': msg_data
                                })
                                
                                # Keep only last 100 messages
                                if len(kafka_messages) > 100:
                                    kafka_messages = kafka_messages[-100:]
                                    
                            except json.JSONDecodeError:
                                # Handle non-JSON messages
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                available_topics.add(message.topic)
                                
                                kafka_messages.append({
                                    'timestamp': timestamp,
                                    'topic': message.topic,
                                    'partition': message.partition,
                                    'offset': message.offset,
                                    'data': {'raw_message': message.value}
                                })
                            except Exception as e:
                                logging.error(f"Error processing individual message: {e}")
                                continue
                                
                except Exception as e:
                    consecutive_errors += 1
                    if self.running:  # Only log if we're supposed to be running
                        if "Connection reset by peer" in str(e) or "KafkaConnectionError" in str(e):
                            logging.warning(f"Kafka connection error (attempt {consecutive_errors}/{max_consecutive_errors}): {e}")
                            # Wait before retrying on connection errors
                            time.sleep(min(consecutive_errors * 2, 10))  # Exponential backoff, max 10 seconds
                        else:
                            logging.error(f"Error in Kafka polling loop (attempt {consecutive_errors}/{max_consecutive_errors}): {e}")
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logging.error(f"Too many consecutive errors ({consecutive_errors}), stopping consumer")
                        break
                        
            if consecutive_errors >= max_consecutive_errors:
                logging.error("Kafka consumer stopped due to too many connection errors")
            elif not self.running:
                logging.info("Kafka consumer stopped by user request")
                    
        except Exception as e:
            logging.error(f"Kafka consumer connection failed: {e}")
            logging.error(f"Broker: {self.broker}, Topics: {self.topics}")
            self.running = False
            # Reset global flag when consumer fails
            kafka_running = False
            return False
        finally:
            # Cleanup on exit
            if self.running:
                logging.info(f"Kafka consumer stopped normally. Processed {message_count if 'message_count' in locals() else 0} messages total")
            else:
                logging.info(f"Kafka consumer stopped due to error or stop request. Processed {message_count if 'message_count' in locals() else 0} messages total")
            self.running = False
            kafka_running = False
            
            # Close the consumer properly
            if hasattr(self, 'consumer') and self.consumer:
                try:
                    self.consumer.close()
                    logging.info("Kafka consumer connection closed")
                except Exception as e:
                    logging.warning(f"Error closing Kafka consumer: {e}")

        return True
        
    def stop_consuming(self):
        """Stop consuming Kafka messages"""
        self.running = False
        if self.consumer:
            self.consumer.close()

def get_default_target_ip():
    """Retrieve the default target IP address"""
  
    logging.info("Using default target IP: 192.168.100.2")
    return "192.168.100.2"

class ContinuousSimulation:
    """Manages continuous traffic simulation with weighted scenarios and concurrency support"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.max_concurrent_scenarios = 3  # Default concurrency level
        self.active_scenario_threads = {}  # Track active scenario threads
        
        # Scenario weights (higher = more likely to be selected)
        # Normal traffic scenarios have higher weights
        self.scenario_weights = {
            'web_browsing': 30,      # Most common - normal web traffic
            'office_network': 25,    # Common - office activities
            'file_transfer': 15,     # Moderate - file operations
            'video_streaming': 10,   # Moderate - streaming content
            'dns_queries': 8,        # Background - DNS lookups
            'mixed_traffic': 7,      # Background - general traffic
            'siem_events': 5,        # New - SIEM event simulation
            'malicious_activity': 3, # Low - security incidents
            'port_scan': 1,          # Very low - attack activity
            'sql_injection': 1       # Very low - attack activity
        }
        
        # Create weighted scenario list for random selection
        self.weighted_scenarios = []
        for scenario, weight in self.scenario_weights.items():
            self.weighted_scenarios.extend([scenario] * weight)
    
    def start_continuous_simulation(self, min_interval=30, max_interval=180, max_concurrent=3):
        """Start continuous simulation with random scenarios and concurrency support"""
        if self.running:
            return False, "Continuous simulation already running"
        
        self.max_concurrent_scenarios = max_concurrent
        self.running = True
        self.thread = threading.Thread(
            target=self._simulation_loop,
            args=(min_interval, max_interval)
        )
        self.thread.daemon = True
        self.thread.start()
        
        return True, f"Continuous simulation started with max {max_concurrent} concurrent scenarios"
    
    def stop_continuous_simulation(self):
        """Stop continuous simulation and all active scenarios"""
        if not self.running:
            return False, "Continuous simulation not running"
        
        self.running = False
        
        # Stop all active scenario threads
        for session_id, (generator, thread) in list(self.active_scenario_threads.items()):
            generator.running = False
            logging.info(f"Stopping scenario thread: {session_id}")

        # Wait for main thread to stop
        if self.thread:
            self.thread.join(timeout=5)
        
        # Clean up active threads
        self.active_scenario_threads.clear()
        
        return True, "Continuous simulation stopped"
    
    def _simulation_loop(self, min_interval, max_interval):
        """Main simulation loop that runs scenarios continuously with concurrency support"""
        logging.info(f"Starting continuous simulation loop (interval: {min_interval}-{max_interval}s, max concurrent: {self.max_concurrent_scenarios})")

        while self.running:
            try:
                # Clean up finished scenario threads
                self._cleanup_finished_scenarios()
                
                # Check if we can start a new scenario (respect concurrency limit)
                if len(self.active_scenario_threads) < self.max_concurrent_scenarios:
                    # Select random scenario based on weights
                    scenario = random.choice(self.weighted_scenarios)
                    
                    # Determine scenario duration (shorter for attacks, longer for normal traffic)
                    if scenario in ['malicious_activity', 'port_scan', 'sql_injection']:
                        duration = random.randint(30, 90)  # Shorter attack scenarios
                        pps = random.randint(2, 5)
                    elif scenario == 'siem_events':
                        duration = random.randint(60, 120)  # Medium duration for SIEM events
                        pps = random.randint(2, 6)  # Events per minute converted to rough pps equivalent
                    else:
                        duration = random.randint(60, 180)  # Longer normal scenarios
                        pps = random.randint(1, 8)
                    
                    logging.info(f"Continuous simulation: Starting {scenario} for {duration}s at {pps} pps (concurrent: {len(self.active_scenario_threads)+1}/{self.max_concurrent_scenarios})")

                    # Create new generator for this scenario
                    generator = TrafficGenerator()
                    session_id = f"continuous_{scenario}_{int(time.time())}"
                    
                    # Start the appropriate scenario
                    thread = self._start_scenario_thread(generator, scenario, duration, pps)
                    if thread:
                        # Store the session in both global and local tracking
                        traffic_threads[session_id] = generator
                        active_sessions[session_id] = {
                            'type': f"continuous_{scenario}",
                            'started': datetime.now().isoformat(),
                            'duration': duration,
                            'scenario': scenario,
                            'pps': pps,
                            'continuous': True
                        }
                        
                        # Start thread and track it locally
                        thread.start()
                        self.active_scenario_threads[session_id] = (generator, thread)
                
                # Wait for a shorter interval when running concurrent scenarios
                if self.running:
                    # Use shorter wait times when we have capacity for more scenarios
                    if len(self.active_scenario_threads) < self.max_concurrent_scenarios:
                        wait_time = random.randint(min_interval // 2, min_interval)
                    else:
                        wait_time = random.randint(min_interval, max_interval)

                    logging.info(f"Continuous simulation: Waiting {wait_time}s before next scenario check (active: {len(self.active_scenario_threads)})")

                    # Sleep in small chunks to allow for quick stopping
                    for _ in range(wait_time):
                        if not self.running:
                            break
                        time.sleep(1)
                
            except Exception as e:
                logging.error(f"Error in continuous simulation loop: {e}")
                time.sleep(10)  # Wait before retrying
        
        logging.info("Continuous simulation loop stopped")
    
    def _cleanup_finished_scenarios(self):
        """Clean up finished scenario threads"""
        finished_sessions = []
        
        for session_id, (generator, thread) in list(self.active_scenario_threads.items()):
            if not generator.running or not thread.is_alive():
                finished_sessions.append(session_id)

        for session_id in finished_sessions:
            logging.info(f"Cleaning up finished scenario: {session_id}")
            del self.active_scenario_threads[session_id]
            # Also clean up from global tracking
            if session_id in traffic_threads:
                del traffic_threads[session_id]
            if session_id in active_sessions:
                del active_sessions[session_id]
    
    def _start_scenario_thread(self, generator, scenario, duration, pps):
        """Create and return a thread for the specified scenario"""
        logging.info(f"Starting scenario thread for {scenario} with duration {duration}s at {pps} pps")

        if scenario == "web_browsing":
            return threading.Thread(
                target=generator.generate_web_browsing_scenario,
                args=(duration, pps)
            )
        elif scenario == "file_transfer":
            return threading.Thread(
                target=generator.generate_file_transfer_scenario,
                args=(duration, pps)
            )
        elif scenario == "video_streaming":
            return threading.Thread(
                target=generator.generate_video_streaming_scenario,
                args=(duration, pps)
            )
        elif scenario == "office_network":
            return threading.Thread(
                target=generator.generate_office_network_scenario,
                args=(duration, pps)
            )
        elif scenario == "malicious_activity":
            return threading.Thread(
                target=generator.generate_malicious_activity_scenario,
                args=(duration, pps)
            )
        elif scenario == "siem_events":
            return threading.Thread(
                target=generator.siem_scenario.generate_mixed_siem_events,
                args=(duration, pps)
            )
        elif scenario == "port_scan":
            return threading.Thread(
                target=generator.enhanced_generator.generate_port_scan_traffic,
                args=(generator.zeek_monitor_ip, duration, pps)
            )
        elif scenario == "sql_injection":
            return threading.Thread(
                target=generator.enhanced_generator.generate_malicious_http_traffic,
                args=(generator.zeek_monitor_ip, duration, 2)
            )
        elif scenario == "dns_queries":
            return threading.Thread(
                target=generator.generate_dns_traffic,
                args=(None, duration, pps)
            )
        elif scenario == "mixed_traffic":
            return threading.Thread(
                target=generator.generate_mixed_traffic,
                args=(duration, pps)
            )
        else:
            return threading.Thread(
                target=generator.generate_mixed_traffic,
                args=(duration, pps)
            )

class TrafficGenerator(NetworkTrafficGenerator):
    def __init__(self):
        super().__init__()
        self.default_target_ip = get_default_target_ip()
        self.enhanced_generator = EnhancedTrafficGenerator()
        self.siem_scenario = SIEMEventScenario()  # Add SIEM scenario manager
        
    def generate_http_traffic(self, target_ip=None, duration=60, packets_per_second=1):
        """Generate simulated HTTP traffic with precise timing"""
        # Use discovered Zeek monitor IP if no target specified
        if target_ip is None:
            target_ip = self.default_target_ip
        
        logging.info(f"Generating HTTP traffic to {target_ip} for {duration}s at {packets_per_second} pps")
        
        self.running = True
        start_time = time.time()
        end_time = start_time + duration
        packet_interval = 1.0 / packets_per_second
        next_packet_time = start_time
        
        while self.running and time.time() < end_time:
            try:
                current_time = time.time()
                if current_time >= next_packet_time:
                    # Create HTTP-like TCP traffic
                    src_port = random.randint(1024, 65535)
                    packet = IP(dst=target_ip)/TCP(dport=80, sport=src_port)/Raw(load="GET / HTTP/1.1\r\nHost: example.com\r\n\r\n")
                    send(packet, verbose=0)
                    
                    # Schedule next packet with precise timing
                    next_packet_time += packet_interval
                
                # Small sleep to prevent busy waiting
                time.sleep(0.001)
            except Exception as e:
                logging.error(f"Error generating HTTP traffic: {e}")
                break
                
        self.running = False
    
    def generate_dns_traffic(self, target_ip=None, duration=60, packets_per_second=1):
        """Generate simulated DNS traffic with precise timing"""
        # Use discovered Zeek monitor IP if no target specified
        if target_ip is None:
            target_ip = self.default_target_ip
        
        logging.info(f"Generating DNS traffic to {target_ip} for {duration}s at {packets_per_second} pps")
        
        self.running = True
        start_time = time.time()
        end_time = start_time + duration
        packet_interval = 1.0 / packets_per_second
        next_packet_time = start_time
        domains = ["example.com", "google.com", "github.com", "stackoverflow.com", "wikipedia.org"]
        
        while self.running and time.time() < end_time:
            try:
                current_time = time.time()
                if current_time >= next_packet_time:
                    domain = random.choice(domains)
                    packet = IP(dst=target_ip)/UDP(dport=53)/DNS(rd=1, qd=DNSQR(qname=domain))
                    send(packet, verbose=0)
                    
                    # Schedule next packet with precise timing
                    next_packet_time += packet_interval
                
                # Small sleep to prevent busy waiting
                time.sleep(0.001)
            except Exception as e:
                logging.error(f"Error generating DNS traffic: {e}")
                break
                
        self.running = False
    
    def generate_mixed_traffic(self, duration=60, packets_per_second=2):
        """Generate mixed protocol traffic with precise timing"""
        self.running = True
        start_time = time.time()
        end_time = start_time + duration
        packet_interval = 1.0 / packets_per_second
        next_packet_time = start_time
        
        while self.running and time.time() < end_time:
            try:
                current_time = time.time()
                if current_time >= next_packet_time:
                    traffic_type = random.choice(['http', 'dns', 'tcp', 'udp'])
                    
                    if traffic_type == 'http':
                        target = f"192.168.100.{random.randint(20, 29)}"
                        packet = IP(dst=target)/TCP(dport=80, sport=random.randint(1024, 65535))/Raw(load="GET /index.html HTTP/1.1\r\n\r\n")
                    elif traffic_type == 'dns':
                        packet = IP(dst="192.168.100.1")/UDP(dport=53)/DNS(rd=1, qd=DNSQR(qname=f"host{random.randint(1,100)}.example.com"))
                    elif traffic_type == 'tcp':
                        packet = IP(dst=f"192.168.100.{random.randint(20, 29)}")/TCP(dport=random.choice([22, 443, 993, 995]))
                    else:  # udp
                        packet = IP(dst=f"192.168.100.{random.randint(20, 29)}")/UDP(dport=random.choice([123, 161, 514]))
                    
                    send(packet, verbose=0)
                    
                    # Schedule next packet with precise timing
                    next_packet_time += packet_interval
                
                # Small sleep to prevent busy waiting
                time.sleep(0.001)
            except Exception as e:
                logging.error(f"Error generating mixed traffic: {e}")
                break
                
        self.running = False
    
    def generate_web_browsing_scenario(self, duration=120, packets_per_second=5):
        """Generate web browsing scenario using the same approach as custom traffic"""
        self.running = True
        start_time = time.time()
        end_time = start_time + duration
        packet_interval = 1.0 / packets_per_second
        next_packet_time = start_time
        
        logging.info(f"Starting web browsing scenario for {duration}s at {packets_per_second} pps")
        
        while self.running and time.time() < end_time:
            try:
                current_time = time.time()
                if current_time >= next_packet_time:
                    # Create realistic web browsing traffic
                    traffic_type = random.choice(['http_get', 'https_connect', 'dns_lookup'])
                    
                    if traffic_type == 'http_get':
                        target_ip = f"192.168.100.{random.randint(20, 29)}"
                        src_port = random.randint(1024, 65535)
                        pages = ["/", "/index.html", "/about.html", "/products.html", "/contact.html"]
                        page = random.choice(pages)
                        payload = f"GET {page} HTTP/1.1\r\nHost: example.com\r\nUser-Agent: Mozilla/5.0\r\n\r\n"
                        packet = IP(dst=target_ip)/TCP(dport=80, sport=src_port)/Raw(load=payload)
                    elif traffic_type == 'https_connect':
                        target_ip = f"192.168.100.{random.randint(20, 29)}"
                        packet = IP(dst=target_ip)/TCP(dport=443, sport=random.randint(1024, 65535), flags="S")
                    else:  # dns_lookup
                        domains = ["example.com", "cdn.example.com", "api.example.com", "images.example.com"]
                        domain = random.choice(domains)
                        packet = IP(dst="192.168.100.1")/UDP(dport=53)/DNS(rd=1, qd=DNSQR(qname=domain))
                    
                    send(packet, verbose=0)
                    next_packet_time += packet_interval
                
                time.sleep(0.001)
            except Exception as e:
                logging.error(f"Error in web browsing scenario: {e}")
                break
                
        self.running = False
    
    def generate_file_transfer_scenario(self, duration=120, packets_per_second=5):
        """Generate file transfer scenario"""
        self.running = True
        start_time = time.time()
        end_time = start_time + duration
        packet_interval = 1.0 / packets_per_second
        next_packet_time = start_time
        
        logging.info(f"Starting file transfer scenario for {duration}s at {packets_per_second} pps")
        
        while self.running and time.time() < end_time:
            try:
                current_time = time.time()
                if current_time >= next_packet_time:
                    traffic_type = random.choice(['ftp_control', 'ftp_data', 'sftp'])
                    target_ip = f"192.168.100.{random.randint(20, 29)}"
                    
                    if traffic_type == 'ftp_control':
                        commands = ["USER demo", "PASS secret", "LIST", "RETR file.txt", "STOR upload.txt"]
                        command = random.choice(commands)
                        packet = IP(dst=target_ip)/TCP(dport=21, sport=random.randint(1024, 65535))/Raw(load=command + "\r\n")
                    elif traffic_type == 'ftp_data':
                        data_size = random.randint(500, 1400)
                        payload = "FILE_DATA_" + "A" * (data_size - 10)
                        packet = IP(dst=target_ip)/TCP(dport=20, sport=random.randint(1024, 65535))/Raw(load=payload)
                    else:  # sftp
                        packet = IP(dst=target_ip)/TCP(dport=22, sport=random.randint(1024, 65535))
                    
                    send(packet, verbose=0)
                    next_packet_time += packet_interval
                
                time.sleep(0.001)
            except Exception as e:
                logging.error(f"Error in file transfer scenario: {e}")
                break
                
        self.running = False
    
    def generate_video_streaming_scenario(self, duration=120, packets_per_second=5):
        """Generate video streaming scenario"""
        self.running = True
        start_time = time.time()
        end_time = start_time + duration
        packet_interval = 1.0 / packets_per_second
        next_packet_time = start_time
        
        logging.info(f"Starting video streaming scenario for {duration}s at {packets_per_second} pps")
        
        while self.running and time.time() < end_time:
            try:
                current_time = time.time()
                if current_time >= next_packet_time:
                    # High bandwidth streaming traffic
                    src_ip = f"192.168.100.{random.randint(20, 29)}"  # Server
                    dst_ip = f"192.168.100.{random.randint(10, 19)}"  # Client
                    
                    data_size = random.randint(800, 1400)
                    payload = "VIDEO_STREAM_" + "X" * (data_size - 13)
                    packet = IP(src=src_ip, dst=dst_ip)/UDP(sport=8080, dport=random.randint(1024, 65535))/Raw(load=payload)
                    
                    send(packet, verbose=0)
                    next_packet_time += packet_interval
                
                time.sleep(0.001)
            except Exception as e:
                logging.error(f"Error in video streaming scenario: {e}")
                break
                
        self.running = False
    
    def generate_office_network_scenario(self, duration=120, packets_per_second=5):
        """Generate office network scenario"""
        self.running = True
        start_time = time.time()
        end_time = start_time + duration
        packet_interval = 1.0 / packets_per_second
        next_packet_time = start_time
        
        logging.info(f"Starting office network scenario for {duration}s at {packets_per_second} pps")
        
        while self.running and time.time() < end_time:
            try:
                current_time = time.time()
                if current_time >= next_packet_time:
                    services = ["email", "file_share", "print", "web_proxy"]
                    service = random.choice(services)
                    src_ip = f"192.168.100.{random.randint(10, 19)}"
                    
                    if service == "email":
                        dst_ip = f"192.168.100.{random.randint(20, 29)}"
                        protocols = [("smtp", 25), ("pop3", 110), ("imap", 143), ("smtps", 465)]
                        protocol, port = random.choice(protocols)
                        packet = IP(src=src_ip, dst=dst_ip)/TCP(sport=random.randint(1024, 65535), dport=port)
                    elif service == "file_share":
                        dst_ip = f"192.168.100.{random.randint(20, 29)}"
                        packet = IP(src=src_ip, dst=dst_ip)/TCP(sport=random.randint(1024, 65535), dport=445)  # SMB
                    elif service == "print":
                        dst_ip = f"192.168.100.{random.randint(30, 39)}"  # Printer range
                        packet = IP(src=src_ip, dst=dst_ip)/TCP(sport=random.randint(1024, 65535), dport=631)  # IPP
                    else:  # web_proxy
                        dst_ip = f"192.168.100.{random.randint(20, 29)}"
                        packet = IP(src=src_ip, dst=dst_ip)/TCP(sport=random.randint(1024, 65535), dport=8080)
                    
                    send(packet, verbose=0)
                    next_packet_time += packet_interval
                
                time.sleep(0.001)
            except Exception as e:
                logging.error(f"Error in office network scenario: {e}")
                break
                
        self.running = False
    
    def generate_malicious_activity_scenario(self, duration=120, packets_per_second=5):
        """Generate malicious activity scenario for IDS testing"""
        self.running = True
        start_time = time.time()
        end_time = start_time + duration
        packet_interval = 1.0 / packets_per_second
        next_packet_time = start_time
        
        logging.info(f"Starting malicious activity scenario for {duration}s at {packets_per_second} pps")
        
        while self.running and time.time() < end_time:
            try:
                current_time = time.time()
                if current_time >= next_packet_time:
                    attacks = ["port_scan", "brute_force", "suspicious_dns", "data_exfiltration"]
                    attack = random.choice(attacks)
                    src_ip = f"192.168.100.{random.randint(100, 109)}"  # Suspicious source range
                    dst_ip = f"192.168.100.{random.randint(10, 29)}"
                    
                    if attack == "port_scan":
                        ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 993, 995]
                        port = random.choice(ports)
                        packet = IP(src=src_ip, dst=dst_ip)/TCP(sport=random.randint(1024, 65535), dport=port, flags="S")
                    elif attack == "brute_force":
                        packet = IP(src=src_ip, dst=dst_ip)/TCP(sport=random.randint(1024, 65535), dport=22)
                    elif attack == "suspicious_dns":
                        domains = ["malware-c2.evil", "phishing.bad", "botnet.cmd"]
                        domain = random.choice(domains)
                        packet = IP(src=src_ip, dst="192.168.100.1")/UDP(sport=random.randint(1024, 65535), dport=53)/DNS(rd=1, qd=DNSQR(qname=domain))
                    else:  # data_exfiltration
                        data_size = random.randint(1000, 1400)
                        payload = "EXFIL_DATA_" + "S" * (data_size - 11)
                        packet = IP(src=dst_ip, dst=src_ip)/TCP(sport=random.randint(1024, 65535), dport=443)/Raw(load=payload)
                    
                    send(packet, verbose=0)
                    next_packet_time += packet_interval
                
                time.sleep(0.001)
            except Exception as e:
                logging.error(f"Error in malicious activity scenario: {e}")
                break
                
        self.running = False

# Web interface HTML template
WEB_INTERFACE = """
<!DOCTYPE html>
<html>
<head>
    <title>Network Traffic Generator</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 10px; background: #f8f9fa; font-size: 14px; }
        .header { display: flex; justify-content: space-between; align-items: center; background: white; padding: 15px 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header h1 { margin: 0; font-size: 24px; color: #2c3e50; }
        .status-badge { background: #e3f2fd; color: #1976d2; padding: 8px 12px; border-radius: 20px; font-weight: 500; font-size: 13px; }
        .main-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px; }
        .control-panel { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .scenarios { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; margin: 15px 0; }
        .scenario-btn { background: linear-gradient(135deg, #28a745, #20c997); color: white; border: none; padding: 12px 8px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 500; transition: all 0.2s; text-align: center; }
        .scenario-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
        .custom-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; align-items: end; margin: 15px 0; }
        .form-group { display: flex; flex-direction: column; }
        .form-group label { font-size: 12px; color: #6c757d; margin-bottom: 4px; font-weight: 500; }
        input, select { padding: 8px; border: 1px solid #dee2e6; border-radius: 4px; font-size: 13px; }
        .btn { background: #007bff; color: white; border: none; padding: 10px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500; transition: background 0.2s; }
        .btn:hover { background: #0056b3; }
        .btn-success { background: #28a745; }
        .btn-success:hover { background: #218838; }
        .btn-danger { background: #dc3545; }
        .btn-danger:hover { background: #c82333; }
        .btn-secondary { background: #6c757d; }
        .btn-secondary:hover { background: #545b62; }
        .status-section { background: white; padding: 15px 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 15px; }
        .status-display { padding: 10px; border-radius: 4px; margin: 10px 0; font-weight: 500; }
        .status-success { background: #d4edda; color: #155724; border-left: 4px solid #28a745; }
        .status-error { background: #f8d7da; color: #721c24; border-left: 4px solid #dc3545; }
        .status-info { background: #d1ecf1; color: #0c5460; border-left: 4px solid #17a2b8; }
        .logs-grid { display: grid; grid-template-columns: 1fr 2fr; gap: 15px; min-width: 0; }
        .log-panel { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); min-width: 0; }
        .log-header { padding: 15px 20px; border-bottom: 1px solid #dee2e6; display: flex; justify-content: space-between; align-items: center; }
        .log-header h3 { margin: 0; font-size: 16px; color: #495057; }
        .log-controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .log-box { height: 300px; overflow-x: auto; overflow-y: auto; padding: 15px; font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; font-size: 11px; line-height: 1.4; background: #f8f9fa; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; white-space: nowrap; }
        .kafka-log-box { height: 300px; width: 100%; min-width: 0; max-width: 100%; overflow-x: scroll; overflow-y: auto; padding: 15px; font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; font-size: 11px; line-height: 1.4; background: #f8f9fa; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; white-space: pre; box-sizing: border-box; }
        .kafka-status { display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 11px; font-weight: 600; margin: 0 4px; }
        .kafka-connected { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .kafka-disconnected { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .kafka-connecting { background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
        .btn-sm { padding: 8px 12px; font-size: 11px; border-radius: 4px; font-weight: 500; }
        .section-title { font-size: 16px; font-weight: 600; color: #495057; margin: 0 0 15px 0; }
        .tip { background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; padding: 10px; border-radius: 4px; font-size: 12px; margin: 10px 0; }
        .topic-filter-container { display: flex; flex-direction: row; align-items: center; gap: 8px; min-width: 160px; }
        .filter-label { font-size: 10px; color: #6c757d; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }
        .topic-filter { padding: 6px 10px; border: 1px solid #ced4da; border-radius: 4px; font-size: 11px; background: white; color: #495057; min-width: 140px; }
        .topic-filter:focus { border-color: #007bff; box-shadow: 0 0 0 2px rgba(0,123,255,0.25); outline: none; }
        .kafka-controls-group { display: flex; align-items: center; gap: 6px; }
        .vertical-separator { width: 1px; height: 24px; background-color: #dee2e6; margin: 0 12px; }
        @media (max-width: 768px) {
            .main-grid, .logs-grid { grid-template-columns: 1fr; }
            .scenarios { grid-template-columns: repeat(2, 1fr); }
            .custom-form { grid-template-columns: 1fr; }
            .log-controls { flex-direction: column; align-items: stretch; gap: 8px; }
            .topic-filter-container { min-width: auto; width: 100%; }
            .kafka-controls-group { flex-wrap: wrap; justify-content: center; }
            .vertical-separator { display: none; } /* Hide separator on mobile */
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Network Traffic Generator for Zeek Monitoring</h1>
        <div class="status-badge">📊 Status: Active | 🔗 Network: zeek-network</div>
    </div>
    
    <div class="main-grid">
        <div class="control-panel">
            <h2 class="section-title">🔄 Continuous Simulation</h2>
            <div class="custom-form">
                <div class="form-group">
                    <label>Min Interval (s)</label>
                    <input type="number" id="minInterval" value="30" min="10" max="300">
                </div>
                <div class="form-group">
                    <label>Max Interval (s)</label>
                    <input type="number" id="maxInterval" value="180" min="30" max="600">
                </div>
                <div class="form-group">
                    <label>Max Concurrent</label>
                    <input type="number" id="maxConcurrent" value="3" min="1" max="10">
                </div>
                <div class="form-group">
                    <label>&nbsp;</label>
                    <button id="continuous-start-btn" class="btn btn-success" onclick="startContinuousSimulation()">Start Continuous</button>
                    <button id="continuous-stop-btn" class="btn btn-danger" onclick="stopContinuousSimulation()" style="display: none;">Stop Continuous</button>
                </div>
            </div>
            <div class="tip">🔄 Runs random scenarios continuously with weighted selection. Normal traffic (70%) vs attacks (30%). Concurrency allows multiple scenarios to run simultaneously for increased load.</div>
            <div id="concurrent-status" class="status-display status-info" style="display: none;">Concurrent scenarios: 0/3</div>
        </div>
        
        <div class="control-panel">
            <h2 class="section-title">🎭 Quick Scenarios</h2>
            <div class="scenarios">
                <button class="scenario-btn" onclick="startScenario('web_browsing')">🌐<br>Web Browsing</button>
                <button class="scenario-btn" onclick="startScenario('file_transfer')">📁<br>File Transfer</button>
                <button class="scenario-btn" onclick="startScenario('video_streaming')">🎥<br>Video Stream</button>
                <button class="scenario-btn" onclick="startScenario('office_network')">🏢<br>Office Network</button>
                <button class="scenario-btn" onclick="startScenario('malicious_activity')">🛡️<br>Security Test</button>
                <button class="scenario-btn" onclick="startScenario('enhanced_attacks')">⚡<br>Enhanced Attacks</button>
                <button class="scenario-btn" onclick="startScenario('port_scan')">🔍<br>Port Scan</button>
                <button class="scenario-btn" onclick="startScenario('sql_injection')">💉<br>SQL Injection</button>
                <button class="scenario-btn" onclick="startScenario('siem_events')">🚨<br>(Single) SIEM Event</button>
            </div>
            <div class="tip">💡 Standard scenarios run for 2 minutes. Enhanced attacks create real network connections for better detection. SIEM Events simulate realistic security events with network traffic.</div>
        </div>
        
        <div class="control-panel">
            <h2 class="section-title">⚙️ Custom Traffic</h2>
            <div class="custom-form">
                <div class="form-group">
                    <label>Type</label>
                    <select id="trafficType">
                        <option value="http">HTTP</option>
                        <option value="dns">DNS</option>
                        <option value="mixed">Mixed</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Duration (s)</label>
                    <input type="number" id="duration" value="60" min="1" max="3600">
                </div>
                <div class="form-group">
                    <label>Packets/sec</label>
                    <input type="number" id="pps" value="2" min="1" max="100">
                </div>
                <div class="form-group">
                    <label>&nbsp;</label>
                    <button class="btn btn-success" onclick="startCustomTraffic()">Start Traffic</button>
                </div>
            </div>
            <div class="tip">💡 Traffic automatically targets the Zeek monitor container for proper monitoring</div>
        </div>
    </div>
    
    <div class="status-section">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2 class="section-title">📈 System Status</h2>
            <button class="btn btn-secondary btn-sm" onclick="getStatus()">Refresh</button>
        </div>
        <div id="status" class="status-display status-info">Ready to generate traffic</div>
    </div>
    
    <div class="logs-grid">
        <div class="log-panel">
            <div class="log-header">
                <h3>📝 Activity Log</h3>
                <button class="btn btn-secondary btn-sm" onclick="clearActivityLog()">Clear</button>
            </div>
            <div id="log" class="log-box"></div>
        </div>
        
        <div class="log-panel">
            <div class="log-header">
                <h3>📡 Kafka Consumer</h3>
                <div class="log-controls">
                    <div class="topic-filter-container">
                        <div class="filter-label">Topic Filter</div>
                        <select id="topic-filter" class="topic-filter" onchange="updateTopicFilter()">
                            <option value="all">All Topics</option>
                        </select>
                    </div>
                    <div class="vertical-separator"></div>
                    <div class="kafka-controls-group">
                        <span id="kafka-status" class="kafka-status kafka-disconnected">Disconnected</span>
                        <button id="kafka-start-btn" class="btn btn-success btn-sm" onclick="startKafkaConsumer()">Start</button>
                        <button id="kafka-stop-btn" class="btn btn-danger btn-sm" onclick="stopKafkaConsumer()" style="display: none;">Stop</button>
                        <button class="btn btn-secondary btn-sm" onclick="clearKafkaMessages()">Clear</button>
                        <button class="btn btn-secondary btn-sm" onclick="diagnoseKafkaConnection()">🔍 Diagnose</button>
                    </div>
                </div>
            </div>
            <div id="kafka-log" class="kafka-log-box"></div>
        </div>
    </div>

    <script>
        let currentTopicFilter = 'all';
        let availableTopics = new Set();
        
        function log(message) {
            const logDiv = document.getElementById('log');
            const timestamp = new Date().toLocaleTimeString();
            logDiv.innerHTML += `[${timestamp}] ${message}<br>\n`;
            logDiv.scrollTop = logDiv.scrollHeight;
        }
        
        function showStatus(message, type = 'info') {
            const statusDiv = document.getElementById('status');
            statusDiv.className = `status-display status-${type}`;
            statusDiv.textContent = message;
        }
        
        async function apiCall(endpoint, data = {}) {
            try {
                const response = await fetch(`/api/${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                return await response.json();
            } catch (error) {
                log(`API Error: ${error.message}`);
                showStatus(`Error: ${error.message}`, 'error');
                return null;
            }
        }
        
        async function startScenario(scenario) {
            log(`Starting ${scenario} scenario...`);
            const result = await apiCall('start_scenario', {
                scenario: scenario,
                duration: 120,
                packets_per_second: 5
            });
            if (result && result.success) {
                showStatus(`${scenario} scenario started`, 'success');
                log(`Scenario started - Session ID: ${result.session_id}`);
            }
        }
        
        async function startCustomTraffic() {
            const trafficType = document.getElementById('trafficType').value;
            const duration = parseInt(document.getElementById('duration').value);
            const pps = parseInt(document.getElementById('pps').value);
            
            log(`Starting custom ${trafficType} traffic...`);
            const result = await apiCall('start_traffic', {
                type: trafficType,
                duration: duration,
                packets_per_second: pps
            });
            if (result && result.success) {
                showStatus(`Custom ${trafficType} traffic started`, 'success');
                log(`Custom traffic started - Session ID: ${result.session_id}`);
            }
        }
        
        async function stopAllTraffic() {
            log('Stopping all traffic generation...');
            const result = await apiCall('stop_all');
            if (result && result.success) {
                showStatus('All traffic generation stopped', 'success');
                log('All traffic sessions stopped');
            }
        }
        
        async function getStatus() {
            const result = await apiCall('status');
            if (result) {
                const active = result.active_sessions || 0;
                showStatus(`Active sessions: ${active}`, active > 0 ? 'success' : 'info');
                log(`Status check: ${active} active sessions`);
            }
        }
        
        // Kafka consumer functions
        async function startKafkaConsumer() {
            log('Starting Kafka consumer...');
            
            // Show starting state
            document.getElementById('kafka-status').className = 'kafka-status kafka-connecting';
            document.getElementById('kafka-status').textContent = 'Connecting...';
            document.getElementById('kafka-start-btn').disabled = true;
            
            const result = await apiCall('kafka/start');
            if (result && result.success) {
                log('Kafka consumer start request successful, verifying connection...');
                
                // Wait a bit longer for the consumer to actually connect
                setTimeout(async () => {
                    const statusResult = await checkKafkaStatusAndUpdate();
                    if (statusResult) {
                        log('Kafka consumer verified as running');
                        startKafkaPolling();
                    } else {
                        log('Kafka consumer failed to establish connection - check broker settings and network');
                    }
                    document.getElementById('kafka-start-btn').disabled = false;
                }, 3000); // Wait 3 seconds for proper connection
            } else {
                log(`Failed to start Kafka consumer: ${result ? result.error : 'Unknown error'}`);
                updateKafkaUIState(false);
                document.getElementById('kafka-start-btn').disabled = false;
            }
        }
        
        async function stopKafkaConsumer() {
            log('Stopping Kafka consumer...');
            const result = await apiCall('kafka/stop');
            if (result && result.success) {
                updateKafkaUIState(false);
                log('Kafka consumer stopped');
                stopKafkaPolling();
            } else {
                log(`Error stopping Kafka consumer: ${result ? result.error : 'Unknown error'}`);
                // Check status to sync UI state
                checkKafkaStatusAndUpdate();
            }
        }
        
        function updateKafkaUIState(isConnected) {
            const statusElement = document.getElementById('kafka-status');
            const startBtn = document.getElementById('kafka-start-btn');
            const stopBtn = document.getElementById('kafka-stop-btn');
            
            if (isConnected) {
                statusElement.className = 'kafka-status kafka-connected';
                statusElement.textContent = 'Connected';
                startBtn.style.display = 'none';
                stopBtn.style.display = 'inline-block';
            } else {
                statusElement.className = 'kafka-status kafka-disconnected';
                statusElement.textContent = 'Disconnected';
                startBtn.style.display = 'inline-block';
                stopBtn.style.display = 'none';
            }
            startBtn.disabled = false;
        }
        
        async function checkKafkaStatusAndUpdate() {
            try {
                const response = await fetch('/api/kafka/status');
                const result = await response.json();
                if (result && result.success) {
                    console.log('Kafka status check:', result);
                    updateKafkaUIState(result.running);
                    
                    // Update available topics
                    if (result.available_topics && result.available_topics.length > 0) {
                        availableTopics = new Set(result.available_topics);
                        updateTopicFilterOptions();
                    }
                    
                    // Log debugging information if not running
                    if (!result.running) {
                        console.log('Kafka Debug Info:', result.debug_info);
                        
                        // Provide helpful feedback in the activity log
                        if (result.debug_info) {
                            const debug = result.debug_info;
                            if (debug.broker === 'Not set') {
                                log('❌ KAFKA_BROKER environment variable not set');
                            } else if (debug.zeek_topic === 'Not set' && debug.event_log_topic === 'Not set') {
                                log('❌ No Kafka topics configured (KAFKA_ZEEK_TOPIC or KAFKA_EVENT_LOG_TOPIC)');
                            } else if (!debug.thread_alive && debug.kafka_running_flag) {
                                log('❌ Kafka consumer thread died - likely connection failure');
                                log(`📡 Broker: ${debug.broker}, Topics: ${debug.zeek_topic}, ${debug.event_log_topic}`);
                            }
                        }
                        
                        if (result.total_messages === 0) {
                            console.log('No messages received - likely connection or topic issue');
                        }
                    } else {
                        // Consumer is running successfully
                        if (result.total_messages > 0) {
                            console.log(`Kafka consumer healthy - ${result.total_messages} messages received`);
                        }
                    }
                    
                    return result.running;
                }
            } catch (error) {
                console.error('Error checking Kafka status:', error);
                updateKafkaUIState(false);
                return false;
            }
        }
        
        async function checkKafkaStatus() {
            const isRunning = await checkKafkaStatusAndUpdate();
            
            // Start/stop polling based on actual state
            if (isRunning && !kafkaPollingInterval) {
                startKafkaPolling();
            } else if (!isRunning && kafkaPollingInterval) {
                stopKafkaPolling();
            }
        }
        
        async function clearKafkaMessages() {
            const result = await apiCall('kafka/clear');
            if (result && result.success) {
                document.getElementById('kafka-log').innerHTML = '';
                log('Kafka messages cleared');
            }
        }
        
        async function diagnoseKafkaConnection() {
            log('🔍 Running Kafka connectivity diagnostics...');
            const result = await apiCall('kafka/diagnose');
            
            if (result && result.success) {
                log('✅ Kafka diagnostics successful:');
                log(`📡 Broker: ${result.broker}`);
                log(`🔗 Cluster accessible: ${result.cluster_accessible}`);
                
                if (result.topics) {
                    for (const [topic, info] of Object.entries(result.topics)) {
                        if (info.exists) {
                            log(`📋 Topic "${topic}": ✅ Exists (${info.partitions.length} partitions)`);
                        } else {
                            log(`📋 Topic "${topic}": ❌ Not found - ${info.error || 'Unknown error'}`);
                        }
                    }
                }
            } else {
                log('❌ Kafka diagnostics failed:');
                log(`🔧 Error: ${result ? result.error : 'Unknown error'}`);
                
                if (result && result.broker) {
                    log(`📡 Broker tested: ${result.broker}`);
                }
                
                if (result && result.topics) {
                    log(`📋 Topics configured: ${Array.isArray(result.topics) ? result.topics.join(', ') : JSON.stringify(result.topics)}`);
                }
                
                // Provide troubleshooting suggestions
                log('🛠️ Troubleshooting suggestions:');
                log('  • Check if Kafka broker is running and accessible');
                log('  • Verify KAFKA_BROKER environment variable');
                log('  • Ensure topics exist in Kafka cluster');
                log('  • Check network connectivity and firewall settings');
            }
        }
        
        function clearActivityLog() {
            document.getElementById('log').innerHTML = '';
        }
        
        function updateTopicFilter() {
            currentTopicFilter = document.getElementById('topic-filter').value;
            log(`Topic filter changed to: ${currentTopicFilter}`);
        }
        
        function updateTopicFilterOptions() {
            const filterSelect = document.getElementById('topic-filter');
            const currentValue = filterSelect.value;
            
            console.log('Updating topic filter options:', Array.from(availableTopics));
            
            // Clear existing options except "All Topics"
            filterSelect.innerHTML = '<option value="all">All Topics</option>';
            
            // Add options for each available topic
            Array.from(availableTopics).sort().forEach(topic => {
                const option = document.createElement('option');
                option.value = topic;
                option.textContent = topic;
                filterSelect.appendChild(option);
                console.log('Added topic option:', topic);
            });
            
            // Restore previous selection if it still exists
            if (Array.from(filterSelect.options).some(opt => opt.value === currentValue)) {
                filterSelect.value = currentValue;
            }
        }
        
        let kafkaPollingInterval;
        
        function startKafkaPolling() {
            kafkaPollingInterval = setInterval(async () => {
                try {
                    const url = currentTopicFilter === 'all' 
                        ? '/api/kafka/messages'
                        : `/api/kafka/messages?topic=${encodeURIComponent(currentTopicFilter)}`;
                    
                    const response = await fetch(url);
                    const result = await response.json();
                    if (result && result.success) {
                        updateKafkaLog(result.messages);
                        
                        // Update available topics for filter dropdown
                        if (result.available_topics) {
                            console.log('Received available topics from API:', result.available_topics);
                            const newTopics = new Set(result.available_topics);
                            console.log('Current availableTopics:', Array.from(availableTopics));
                            console.log('New topics from API:', Array.from(newTopics));
                            
                            if (newTopics.size !== availableTopics.size || 
                                !Array.from(newTopics).every(topic => availableTopics.has(topic))) {
                                console.log('Topics changed, updating dropdown');
                                availableTopics = newTopics;
                                updateTopicFilterOptions();
                            } else {
                                console.log('No topic changes detected');
                            }
                        } else {
                            console.log('No available_topics in API response');
                        }
                    }
                } catch (error) {
                    console.error('Error polling Kafka messages:', error);
                }
            }, 1000); // Poll every second
        }
        
        function stopKafkaPolling() {
            if (kafkaPollingInterval) {
                clearInterval(kafkaPollingInterval);
                kafkaPollingInterval = null;
            }
        }
        
        function updateKafkaLog(messages) {
            const kafkaLogDiv = document.getElementById('kafka-log');
            let content = '';
            
            messages.forEach(msg => {
                const timestamp = msg.timestamp;
                const topic = msg.topic || 'unknown';
                const data = msg.data;
                content += `[${timestamp}] TOPIC: ${topic} | DATA: ${JSON.stringify(data)}\n`;
            });
            
            kafkaLogDiv.textContent = content;
            kafkaLogDiv.scrollTop = kafkaLogDiv.scrollHeight;
        }
        
        // Continuous simulation functions
        async function startContinuousSimulation() {
            const minInterval = parseInt(document.getElementById('minInterval').value);
            const maxInterval = parseInt(document.getElementById('maxInterval').value);
            const maxConcurrent = parseInt(document.getElementById('maxConcurrent').value);
            
            log('Starting continuous simulation...');
            const result = await apiCall('continuous/start', {
                min_interval: minInterval,
                max_interval: maxInterval,
                max_concurrent: maxConcurrent
            });
            if (result && result.success) {
                document.getElementById('continuous-start-btn').style.display = 'none';
                document.getElementById('continuous-stop-btn').style.display = 'inline-block';
                document.getElementById('concurrent-status').style.display = 'block';
                showStatus('Continuous simulation started', 'success');
                log(`Continuous simulation started (${minInterval}-${maxInterval}s intervals, max ${maxConcurrent} concurrent)`);
            }
        }
        
        async function stopContinuousSimulation() {
            log('Stopping continuous simulation...');
            const result = await apiCall('continuous/stop');
            if (result && result.success) {
                document.getElementById('continuous-start-btn').style.display = 'inline-block';
                document.getElementById('continuous-stop-btn').style.display = 'none';
                document.getElementById('concurrent-status').style.display = 'none';
                showStatus('Continuous simulation stopped', 'info');
                log('Continuous simulation stopped');
            }
        }
        
        async function getContinuousStatus() {
            try {
                const response = await fetch('/api/continuous/status');
                const result = await response.json();
                if (result && result.success) {
                    if (result.running) {
                        document.getElementById('continuous-start-btn').style.display = 'none';
                        document.getElementById('continuous-stop-btn').style.display = 'inline-block';
                        document.getElementById('concurrent-status').style.display = 'block';
                        
                        // Update concurrent status display
                        const statusDiv = document.getElementById('concurrent-status');
                        const active = result.active_concurrent || 0;
                        const max = result.max_concurrent || 3;
                        statusDiv.textContent = `Concurrent scenarios: ${active}/${max}`;
                        statusDiv.className = `status-display ${active > 0 ? 'status-success' : 'status-info'}`;
                    } else {
                        document.getElementById('continuous-start-btn').style.display = 'inline-block';
                        document.getElementById('continuous-stop-btn').style.display = 'none';
                        document.getElementById('concurrent-status').style.display = 'none';
                    }
                }
            } catch (error) {
                console.error('Error checking continuous status:', error);
            }
        }
        
        // Auto-refresh status every 30 seconds
        setInterval(getStatus, 30000);
        setInterval(getContinuousStatus, 10000);
        setInterval(checkKafkaStatus, 30000); // Check Kafka status every 30 seconds (less frequent)
        
        // Initial status checks
        getStatus();
        getContinuousStatus();
        checkKafkaStatus(); // Check Kafka status on page load
        log('Virtual Network Traffic Generator initialized');
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(WEB_INTERFACE)

@app.route('/api/start_scenario', methods=['POST'])
def start_scenario():
    try:
        data = request.get_json()
        scenario = data.get('scenario', 'web_browsing')
        duration = data.get('duration', 120)
        packets_per_second = data.get('packets_per_second', 5)
        
        # Generate unique session ID
        session_id = f"scenario_{scenario}_{int(time.time())}"
        
        # Create traffic generator
        generator = TrafficGenerator()
        
        # Start scenario simulation - use the same approach as custom traffic
        if scenario == "web_browsing":
            thread = threading.Thread(
                target=generator.generate_web_browsing_scenario,
                args=(duration, packets_per_second)
            )
        elif scenario == "file_transfer":
            thread = threading.Thread(
                target=generator.generate_file_transfer_scenario,
                args=(duration, packets_per_second)
            )
        elif scenario == "video_streaming":
            thread = threading.Thread(
                target=generator.generate_video_streaming_scenario,
                args=(duration, packets_per_second)
            )
        elif scenario == "office_network":
            thread = threading.Thread(
                target=generator.generate_office_network_scenario,
                args=(duration, packets_per_second)
            )
        elif scenario == "malicious_activity":
            thread = threading.Thread(
                target=generator.generate_malicious_activity_scenario,
                args=(duration, packets_per_second)
            )
        elif scenario == "siem_events":
            # For SIEM events, packets_per_second represents events per minute
            thread = threading.Thread(
                target=generator.siem_scenario.generate_mixed_siem_events,
                args=(duration, packets_per_second)
            )
        elif scenario == "enhanced_attacks":
            thread = threading.Thread(
                target=generator.enhanced_generator.run_comprehensive_attack_simulation,
                args=(generator.zeek_monitor_ip, duration)
            )
        elif scenario == "port_scan":
            thread = threading.Thread(
                target=generator.enhanced_generator.generate_port_scan_traffic,
                args=(generator.zeek_monitor_ip, duration, 5)
            )
        elif scenario == "sql_injection":
            thread = threading.Thread(
                target=generator.enhanced_generator.generate_malicious_http_traffic,
                args=(generator.zeek_monitor_ip, duration, 2)
            )
        else:
            thread = threading.Thread(
                target=generator.generate_mixed_traffic,
                args=(duration, packets_per_second)
            )
        
        thread.start()
        
        # Store the session
        traffic_threads[session_id] = generator
        active_sessions[session_id] = {
            'type': f"scenario_{scenario}",
            'interface': 'eth0',
            'started': datetime.now().isoformat(),
            'duration': duration,
            'scenario': scenario,
            'pps': packets_per_second
        }
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': f'{scenario} scenario started on virtual network'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/start_traffic', methods=['POST'])
def start_traffic():
    try:
        data = request.get_json()
        traffic_type = data.get('type', 'mixed')
        duration = data.get('duration', 60)
        packets_per_second = data.get('packets_per_second', 2)
        
        # Generate unique session ID
        session_id = f"{traffic_type}_{int(time.time())}"
        
        # Create traffic generator
        generator = TrafficGenerator()
        
        # Start appropriate traffic generation in a thread
        # HTTP and DNS will automatically use the discovered Zeek monitor IP
        if traffic_type == 'http':
            thread = threading.Thread(
                target=generator.generate_http_traffic,
                args=(None, duration, packets_per_second)  # None = use auto-discovered IP
            )
        elif traffic_type == 'dns':
            thread = threading.Thread(
                target=generator.generate_dns_traffic,
                args=(None, duration, packets_per_second)  # None = use auto-discovered IP
            )
        else:  # mixed
            thread = threading.Thread(
                target=generator.generate_mixed_traffic,
                args=(duration, packets_per_second)
            )
        
        thread.start()
        
        # Store the session
        traffic_threads[session_id] = generator
        active_sessions[session_id] = {
            'type': traffic_type,
            'started': datetime.now().isoformat(),
            'duration': duration,
            'target_ip': generator.zeek_monitor_ip,
            'pps': packets_per_second
        }
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': f'{traffic_type.upper()} traffic generation started'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Add new SIEM event endpoint
@app.route('/api/trigger_siem_event', methods=['POST'])
def trigger_siem_event():
    try:
        data = request.get_json()
        event_type = data.get('event_type', 'ssh_login_success')
        user = data.get('user', 'alice')
        src_ip = data.get('src_ip', f"192.168.100.{random.randint(10, 19)}")
        dst_ip = data.get('dst_ip', f"192.168.100.{random.randint(20, 29)}")
        
        # Create and trigger SIEM event
        event = SIEMEvent(
            event_type=event_type,
            user=user,
            src_ip=src_ip,
            dst_ip=dst_ip
        )
        
        event_data = event.trigger()
        
        return jsonify({
            'success': True,
            'event_data': event_data,
            'message': f'SIEM event {event_type} triggered successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stop_all', methods=['POST'])
def stop_all_traffic():
    try:
        stopped_count = 0
        for session_id, generator in traffic_threads.items():
            generator.running = False
            stopped_count += 1
        
        traffic_threads.clear()
        active_sessions.clear()
        
        return jsonify({
            'success': True,
            'message': f'Stopped {stopped_count} traffic sessions'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/status', methods=['POST', 'GET'])
def get_status():
    try:
        # Clean up finished sessions
        active_count = 0
        for session_id, generator in list(traffic_threads.items()):
            if not generator.running:
                del traffic_threads[session_id]
                if session_id in active_sessions:
                    del active_sessions[session_id]
            else:
                active_count += 1
        
        return jsonify({
            'success': True,
            'active_sessions': active_count,
            'sessions': active_sessions,
            'kafka_running': kafka_running,
            'kafka_available': KAFKA_AVAILABLE
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/kafka/start', methods=['POST'])
def start_kafka_consumer():
    global kafka_consumer_thread, kafka_running, kafka_consumer_instance, available_topics

    if not KAFKA_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Kafka consumer not available - kafka-python package not installed'
        })

    # Check if consumer is actually running (not just the flag)
    if kafka_running and kafka_consumer_instance and kafka_consumer_thread and kafka_consumer_thread.is_alive():
        return jsonify({
            'success': False,
            'error': 'Kafka consumer already running'
        })

    # Clean up any stale state
    if kafka_consumer_instance:
        try:
            kafka_consumer_instance.stop_consuming()
        except:
            pass
        kafka_consumer_instance = None
    
    kafka_running = False  # Reset the flag

    try:
        # Clear previous topics when starting fresh
        available_topics.clear()
        
        # Retrieve broker and topics from environment variables
        kafka_broker = os.environ.get('KAFKA_BROKER')
        kafka_zeek_topic = os.environ.get('KAFKA_ZEEK_TOPIC')
        kafka_event_log_topic = os.environ.get('KAFKA_EVENT_LOG_TOPIC')

        # Build list of topics to subscribe to
        topics = []
        if kafka_zeek_topic:
            topics.append(kafka_zeek_topic)
        if kafka_event_log_topic:
            topics.append(kafka_event_log_topic)

        if not kafka_broker or not topics:
            return jsonify({
                'success': False,
                'error': 'KAFKA_BROKER and at least one of KAFKA_ZEEK_TOPIC or KAFKA_EVENT_LOG_TOPIC environment variables must be set'
            })

        # Store the consumer instance globally
        kafka_consumer_instance = KafkaMessageConsumer(broker=kafka_broker, topics=topics)
        kafka_consumer_thread = threading.Thread(target=kafka_consumer_instance.start_consuming)
        kafka_consumer_thread.daemon = True
        kafka_consumer_thread.start()
        
        # Wait a moment to see if the thread starts successfully
        time.sleep(1.0)  # Increased wait time
        if not kafka_consumer_thread.is_alive():
            kafka_consumer_instance = None
            kafka_running = False
            return jsonify({
                'success': False,
                'error': 'Failed to start Kafka consumer thread'
            })
        
        # Give the consumer a bit more time to establish connection
        time.sleep(1.0)
        
        # Check if consumer is still running after connection attempt
        if not kafka_consumer_instance.running:
            kafka_consumer_instance = None
            kafka_running = False
            return jsonify({
                'success': False,
                'error': 'Kafka consumer failed to establish connection (check broker and network)'
            })
        
        kafka_running = True

        logging.info(f"Kafka consumer started for topics: {', '.join(topics)}")
        return jsonify({
            'success': True,
            'message': f'Kafka consumer started for topics: {", ".join(topics)}'
        })

    except Exception as e:
        logging.error(f"Error starting Kafka consumer: {e}")
        # Clean up on error
        if kafka_consumer_instance:
            try:
                kafka_consumer_instance.stop_consuming()
            except:
                pass
            kafka_consumer_instance = None
        kafka_running = False
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/kafka/stop', methods=['POST'])
def stop_kafka_consumer():
    global kafka_running, kafka_consumer_instance, available_topics
    
    try:
        if kafka_consumer_instance:
            kafka_consumer_instance.stop_consuming()
            kafka_consumer_instance = None
        
        kafka_running = False
        
        # Optionally clear available topics when stopping
        # available_topics.clear()  # Uncomment if you want to clear topics on stop
        
        logging.info("Kafka consumer stopped")
        return jsonify({
            'success': True,
            'message': 'Kafka consumer stopped'
        })
    except Exception as e:
        logging.error(f"Error stopping Kafka consumer: {e}")
        # Force cleanup even if there's an error
        kafka_running = False
        kafka_consumer_instance = None
        return jsonify({
            'success': True,  # Still return success since we've cleaned up
            'message': 'Kafka consumer stopped (with cleanup)'
        })

@app.route('/api/kafka/status', methods=['GET'])
def get_kafka_status():
    global kafka_running, kafka_consumer_instance, kafka_consumer_thread, available_topics
    
    # Check if consumer is actually running
    thread_alive = kafka_consumer_thread and kafka_consumer_thread.is_alive() if kafka_consumer_thread else False
    consumer_running = kafka_consumer_instance and kafka_consumer_instance.running if kafka_consumer_instance else False
    
    actual_running = kafka_running and consumer_running and thread_alive
    
    # If the flag says running but thread is dead, clean up
    if kafka_running and not actual_running:
        logging.warning(f"Kafka consumer state mismatch - Flag: {kafka_running}, Consumer: {consumer_running}, Thread: {thread_alive}")
        kafka_running = False
        if kafka_consumer_instance:
            try:
                kafka_consumer_instance.stop_consuming()
            except:
                pass
            kafka_consumer_instance = None
    
    # Get environment info for debugging
    kafka_broker = os.environ.get('KAFKA_BROKER', 'Not set')
    kafka_zeek_topic = os.environ.get('KAFKA_ZEEK_TOPIC', 'Not set')
    kafka_event_log_topic = os.environ.get('KAFKA_EVENT_LOG_TOPIC', 'Not set')
    
    return jsonify({
        'success': True,
        'running': actual_running,
        'kafka_available': KAFKA_AVAILABLE,
        'available_topics': sorted(list(available_topics)),
        'total_messages': len(kafka_messages),
        'debug_info': {
            'kafka_running_flag': kafka_running,
            'consumer_instance_exists': kafka_consumer_instance is not None,
            'consumer_running': consumer_running,
            'thread_alive': thread_alive,
            'broker': kafka_broker,
            'zeek_topic': kafka_zeek_topic,
            'event_log_topic': kafka_event_log_topic
        }
    })

@app.route('/api/kafka/messages', methods=['GET'])
def get_kafka_messages():
    global kafka_messages, available_topics
    
    # Get topic filter from query parameters
    topic_filter = request.args.get('topic', 'all')
    
    # Debug logging
    logging.debug(f"Available topics: {list(available_topics)}")
    logging.debug(f"Topic filter requested: {topic_filter}")
    
    # Filter messages based on topic
    if topic_filter == 'all':
        filtered_messages = kafka_messages[-50:]  # Return last 50 messages from all topics
    else:
        # Filter messages for specific topic
        filtered_messages = [
            msg for msg in kafka_messages 
            if msg.get('topic') == topic_filter
        ][-50:]  # Return last 50 messages from the specific topic
    
    return jsonify({
        'success': True,
        'messages': filtered_messages,
        'total_count': len(kafka_messages),
        'filtered_count': len(filtered_messages),
        'topic_filter': topic_filter,
        'available_topics': sorted(list(available_topics))  # Sort for consistent ordering
    })

@app.route('/api/kafka/clear', methods=['POST'])
def clear_kafka_messages():
    global kafka_messages
    
    kafka_messages.clear()
    
    return jsonify({
        'success': True,
        'message': 'Kafka messages cleared'
    })

@app.route('/api/kafka/diagnose', methods=['POST'])
def diagnose_kafka_connection():
    """Diagnostic endpoint to test Kafka connectivity"""
    try:
        # Get environment variables
        kafka_broker = os.environ.get('KAFKA_BROKER')
        kafka_zeek_topic = os.environ.get('KAFKA_ZEEK_TOPIC')
        kafka_event_log_topic = os.environ.get('KAFKA_EVENT_LOG_TOPIC')
        
        if not kafka_broker:
            return jsonify({
                'success': False,
                'error': 'KAFKA_BROKER environment variable not set'
            })
        
        topics = []
        if kafka_zeek_topic:
            topics.append(kafka_zeek_topic)
        if kafka_event_log_topic:
            topics.append(kafka_event_log_topic)
            
        if not topics:
            return jsonify({
                'success': False,
                'error': 'No Kafka topics configured'
            })
        
        # Try to create a simple consumer to test connectivity
        try:
            from kafka import KafkaConsumer
            test_consumer = KafkaConsumer(
                bootstrap_servers=[kafka_broker],
                security_protocol='PLAINTEXT',
                api_version_auto_timeout_ms=10000,
                request_timeout_ms=10000,
                consumer_timeout_ms=5000
            )
            
            # Try to get cluster metadata
            cluster_metadata = test_consumer.list_consumer_groups()
            
            # Try to get topic partitions
            topic_info = {}
            for topic in topics:
                try:
                    partitions = test_consumer.partitions_for_topic(topic)
                    topic_info[topic] = {
                        'exists': partitions is not None,
                        'partitions': list(partitions) if partitions else []
                    }
                except Exception as e:
                    topic_info[topic] = {
                        'exists': False,
                        'error': str(e)
                    }
            
            test_consumer.close()
            
            return jsonify({
                'success': True,
                'broker': kafka_broker,
                'cluster_accessible': True,
                'topics': topic_info,
                'message': 'Kafka connectivity test successful'
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'broker': kafka_broker,
                'cluster_accessible': False,
                'error': str(e),
                'topics': topics,
                'message': f'Kafka connectivity test failed: {str(e)}'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Diagnostic test failed: {str(e)}'
        })

@app.route('/api/continuous/start', methods=['POST'])
def start_continuous_simulation():
    global continuous_simulation, continuous_simulation_running
    
    try:
        data = request.get_json() or {}
        min_interval = data.get('min_interval', 30)
        max_interval = data.get('max_interval', 180)
        max_concurrent = data.get('max_concurrent', 3)  # New concurrency parameter
        
        if continuous_simulation_running:
            return jsonify({
                'success': False,
                'error': 'Continuous simulation already running'
            })
        
        # Create new continuous simulation instance
        continuous_simulation = ContinuousSimulation()
        success, message = continuous_simulation.start_continuous_simulation(min_interval, max_interval, max_concurrent)
        
        if success:
            continuous_simulation_running = True
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/continuous/stop', methods=['POST'])
def stop_continuous_simulation():
    global continuous_simulation, continuous_simulation_running
    
    try:
        if not continuous_simulation_running or not continuous_simulation:
            return jsonify({
                'success': False,
                'error': 'Continuous simulation not running'
            })
        
        success, message = continuous_simulation.stop_continuous_simulation()
        
        if success:
            continuous_simulation_running = False
            continuous_simulation = None
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/continuous/status', methods=['GET'])
def get_continuous_status():
    global continuous_simulation, continuous_simulation_running
    
    status_data = {
        'success': True,
        'running': continuous_simulation_running,
        'weights': continuous_simulation.scenario_weights if continuous_simulation else {}
    }
    
    if continuous_simulation:
        status_data.update({
            'max_concurrent': continuous_simulation.max_concurrent_scenarios,
            'active_concurrent': len(continuous_simulation.active_scenario_threads),
            'active_scenarios': list(continuous_simulation.active_scenario_threads.keys())
        })
    
    return jsonify(status_data)

if __name__ == '__main__':
    print("Starting Virtual Network Traffic Generator Server...")
    print("Web interface available at: http://localhost:8080")
    print("Virtual network topology: 192.168.200.0/24")
    print("SIEM Event support enabled")
    # Disable Flask's default logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=8080, debug=False)