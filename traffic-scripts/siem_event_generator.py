import datetime
from network_traffic_generator import NetworkTrafficGenerator

class SIEMEvent:
    def __init__(self, event_type, user=None, src_ip=None, dst_ip=None, timestamp=None):
        self.event_type = event_type
        self.user = user
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.timestamp = timestamp or datetime.datetime.utcnow()

    def emit_log(self):
        # You can adapt this log format to your actual use
        log_entry = f"{self.timestamp} event={self.event_type} user={self.user} src_ip={self.src_ip} dst_ip={self.dst_ip}"
        with open("/logs/events.log", "a") as f:
            f.write(log_entry + "\n")
        print(f"[LOG] {log_entry}")

    def emit_network(self, interface="eth0", traffic_type="tcp_syn"):
        # Use your existing traffic generator
        traffic_gen = NetworkTrafficGenerator()
        # For SSH login, simulate a TCP SYN or full handshake to port 22
        packet = traffic_gen.create_packet(traffic_type, self.dst_ip)
        # Send the packet using the preferred interface
        try:
            traffic_gen.generate_traffic_to_interface(
                interface=interface,
                traffic_type=traffic_type,
                target_ip=self.dst_ip,
                duration=1,
                packets_per_second=1,
                packet=packet  # Send the created packet
            )
            print(f"[NETWORK] Simulated {traffic_type} network traffic from {self.src_ip} to {self.dst_ip} port 22 on interface {interface}")
        except Exception as e:
            print(f"[ERROR] Failed to generate network traffic: {e}")

    def trigger(self):
        self.emit_log()
        self.emit_network()

# Example usage:
if __name__ == "__main__":
    event = SIEMEvent(
        event_type="ssh_login_success",
        user="alice",
        src_ip="192.168.100.10",
        dst_ip="192.168.100.20"
    )
    event.trigger()
