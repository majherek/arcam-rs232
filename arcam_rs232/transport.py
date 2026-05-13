import socket
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import TransportConfig

try:
    import serial
except ImportError:
    print("Missing pyserial package. Install it with: pip install pyserial", file=sys.stderr)
    raise

class SerialTransport:
    def __init__(self, port, baudrate, timeout):
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        self.label = f"serial {port} @ {baudrate}"

    def read(self, n=256):
        return self.ser.read(n)

    def write(self, data):
        self.ser.write(data)
        self.ser.flush()

    def close(self):
        self.ser.close()


class TcpTransport:
    def __init__(self, host, port, timeout):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.label = f"TCP {host}:{port}"

    def read(self, n=4096):
        return self.sock.recv(n)

    def write(self, data):
        self.sock.sendall(data)

    def close(self):
        self.sock.close()


def make_transport(args):
    if args.host:
        if args.port is None:
            raise SystemExit('--port is required when --host is used')
        return TcpTransport(args.host, args.port, args.timeout)
    if args.serial:
        return SerialTransport(args.serial, args.baudrate, args.timeout)
    raise SystemExit('Provide --serial /dev/ttyUSB0 or --host 192.168.1.50 --port 8899')


def make_config_transport(config: "TransportConfig"):
    if config.type == "tcp":
        if config.host is None or config.port is None:
            raise ValueError("TCP transport requires host and port")
        return TcpTransport(config.host, config.port, config.timeout_seconds)
    if config.type == "serial":
        if config.serial_port is None:
            raise ValueError("Serial transport requires port")
        return SerialTransport(config.serial_port, config.baudrate, config.timeout_seconds)
    raise ValueError(f"Unsupported transport type: {config.type}")

