import argparse
import json
import socket
import sys
import time

from . import package_version
from .protocol import (
    DIRECT_GET_COMMANDS,
    DIRECT_SET_COMMANDS,
    DIRECT_VALUE_HELP,
    RC5_COMMANDS,
    SOURCE_NAME_TO_CODE,
    ArcamDecoder,
    FrameReader,
    build_frame,
    build_rc5_frame,
    hex_bytes,
    normalize_name,
    parse_direct_value,
    rc5_frame_from_alias,
    request_frame,
    source_to_rc5_alias,
    volume_to_byte,
    zone_rc5_alias,
)
from .transport import make_transport

def output(decoded, fmt):
    if fmt == 'json':
        print(json.dumps(decoded, ensure_ascii=False))
        return
    if decoded.get('type') == 'ignored':
        return
    print(decoded.get('summary', decoded))
    print(f"  raw:   {decoded.get('raw_hex')}")
    if decoded.get('type') == 'frame':
        print(f"  data:  {decoded.get('data_hex')} | ascii: {decoded.get('data_ascii')}")


def process_stream(read_fn, fmt='text', hex_dump=False):
    dec = ArcamDecoder()
    fr = FrameReader()
    try:
        while True:
            try:
                chunk = read_fn()
            except (TimeoutError, socket.timeout):
                continue
            if not chunk:
                print('Connection closed by peer.')
                break
            if hex_dump:
                print(f"RX chunk: {hex_bytes(chunk)}")
            for raw in fr.feed(chunk):
                output(dec.decode_frame(raw), fmt)
    except KeyboardInterrupt:
        print('Stopped.')


def send_and_collect(transport, frame, fmt='text', hex_dump=False, wait=1.2):
    dec = ArcamDecoder()
    fr = FrameReader()
    print(f"Connected to {transport.label}")
    print(f"TX: {hex_bytes(frame)}")
    transport.write(frame)
    expected_rc5 = frame[4:6] if len(frame) == 7 and frame[2] == 0x08 and frame[3] == 0x02 else None
    rc5_ack = False
    deadline = time.time() + wait
    seen = 0
    while time.time() < deadline:
        try:
            chunk = transport.read(4096)
        except (TimeoutError, socket.timeout):
            continue
        if not chunk:
            break
        if hex_dump:
            print(f"RX chunk: {hex_bytes(chunk)}")
        for raw in fr.feed(chunk):
            seen += 1
            decoded = dec.decode_frame(raw)
            if (
                expected_rc5
                and decoded.get("type") == "frame"
                and raw[2] == 0x08
                and raw[3] == 0x00
                and raw[4] == 0x02
                and raw[5:7] == expected_rc5
            ):
                rc5_ack = True
            output(decoded, fmt)
    if seen == 0:
        print('No response within the wait window.')
    elif expected_rc5 and fmt != 'json':
        print(f"RC5 acknowledgement: {'OK' if rc5_ack else 'not seen'}")


def decode_hex_lines(fmt):
    dec = ArcamDecoder()
    fr = FrameReader()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        parts = line.replace(',', ' ').split()
        data = bytes(int(p, 16) for p in parts)
        for raw in fr.feed(data):
            output(dec.decode_frame(raw), fmt)


def build_action_frame(args):
    if args.send_hex:
        parts = args.send_hex.replace(',', ' ').split()
        return bytes(int(p, 16) for p in parts)
    if args.rc5:
        return rc5_frame_from_alias(args.zone, args.rc5)
    if args.rc5_code:
        system, command = (int(part, 0) for part in args.rc5_code)
        return build_rc5_frame(args.zone, system, command)
    if args.get:
        command = DIRECT_GET_COMMANDS[args.get]
        return request_frame(args.zone, command)
    if args.power:
        alias = zone_rc5_alias(args.zone, "power-on" if args.power == "on" else "power-off")
        return rc5_frame_from_alias(args.zone, alias)
    if args.source:
        return rc5_frame_from_alias(args.zone, source_to_rc5_alias(args.zone, args.source))
    if args.set_volume is not None:
        return build_frame(args.zone, 0x0D, [volume_to_byte(args.zone, args.set_volume)])
    if args.volume_up:
        return rc5_frame_from_alias(args.zone, zone_rc5_alias(args.zone, "volume-up"))
    if args.volume_down:
        return rc5_frame_from_alias(args.zone, zone_rc5_alias(args.zone, "volume-down"))
    if args.mute:
        alias = zone_rc5_alias(args.zone, f"mute-{args.mute}")
        return rc5_frame_from_alias(args.zone, alias)
    if args.set:
        name, value = args.set
        option = normalize_name(name)
        if option not in DIRECT_SET_COMMANDS:
            choices = ", ".join(sorted(DIRECT_SET_COMMANDS))
            raise ValueError(f"unknown direct setting {name!r}; choices: {choices}")
        command, value_parser = DIRECT_SET_COMMANDS[option]
        return build_frame(args.zone, command, [parse_direct_value(value_parser, value)])
    return None


def build_parser():
    p = argparse.ArgumentParser(description='Arcam AVR500/600/AV888 RS232 sniffer/decoder + sender')
    p.add_argument('--version', action='version', version=f'arcam-rs232 {package_version()}')
    transport = p.add_mutually_exclusive_group(required=False)
    transport.add_argument('--serial', help='Serial port, e.g. /dev/ttyUSB0 or COM3')
    transport.add_argument('--host', help='TCP converter IP address or hostname')
    p.add_argument('--port', type=int, help='TCP converter port (required with --host)')
    p.add_argument('--baudrate', type=int, default=38400)
    p.add_argument('--timeout', type=float, default=1.0)
    p.add_argument('--format', choices=['text', 'json'], default='text')
    p.add_argument('--hex-dump', action='store_true')
    p.add_argument('--zone', type=lambda x: int(x, 0), default=0x01, help='Default: 0x01')
    p.add_argument('--wait', type=float, default=1.2, help='Seconds to wait for a response after sending a command')
    p.add_argument('--decode-hex', action='store_true', help='Read hex lines from stdin instead of serial/TCP')
    p.add_argument('--dry-run', action='store_true', help='Print the generated TX frame without opening serial/TCP')
    p.add_argument('--list-rc5', action='store_true', help='List named RC5 command aliases and exit')
    p.add_argument('--list-set', action='store_true', help='List direct RS232 settings and exit')

    action = p.add_mutually_exclusive_group(required=False)
    action.add_argument('--send-hex', help='Send a raw hex frame, e.g. "0x21 0x01 0x0D 0x01 0xF0 0x0D"')
    action.add_argument('--rc5', choices=sorted(RC5_COMMANDS.keys()), help='Send a named RC5 command via command 0x08')
    action.add_argument('--rc5-code', nargs=2, metavar=('SYSTEM', 'COMMAND'), help='Send a raw RC5 system/command pair, e.g. 0x10 0x7B')
    action.add_argument('--get', choices=sorted(DIRECT_GET_COMMANDS.keys()))
    action.add_argument('--set', nargs=2, metavar=('OPTION', 'VALUE'), help='Set a direct RS232 option; use --list-set for options')
    action.add_argument('--power', choices=['on', 'standby'])
    action.add_argument('--source', choices=sorted(SOURCE_NAME_TO_CODE.keys()))
    action.add_argument('--set-volume', type=float)
    action.add_argument('--volume-up', action='store_true')
    action.add_argument('--volume-down', action='store_true')
    action.add_argument('--mute', choices=['on', 'off'])
    return p


def print_rc5_commands():
    for name, (system, command) in sorted(RC5_COMMANDS.items()):
        print(f"{name}: 0x{system:02X} 0x{command:02X}")


def print_direct_settings():
    for name, (_, value_parser) in sorted(DIRECT_SET_COMMANDS.items()):
        if isinstance(value_parser, dict):
            values = ", ".join(sorted(value_parser.keys()))
        else:
            values = DIRECT_VALUE_HELP.get(value_parser, value_parser)
        print(f"{name}: {values}")


def arcam():
    args = build_parser().parse_args()
    if args.list_rc5:
        print_rc5_commands()
        return
    if args.list_set:
        print_direct_settings()
        return
    if args.decode_hex:
        decode_hex_lines(args.format)
        return
    try:
        frame = build_action_frame(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.dry_run:
        if frame is None:
            raise SystemExit('--dry-run requires an action that builds a frame')
        print(hex_bytes(frame))
        return
    transport = make_transport(args)
    try:
        if frame is None:
            print(f"Listening on {transport.label}")
            process_stream(lambda: transport.read(4096), fmt=args.format, hex_dump=args.hex_dump)
        else:
            send_and_collect(transport, frame, fmt=args.format, hex_dump=args.hex_dump, wait=args.wait)
    finally:
        transport.close()


if __name__ == '__main__':
    arcam()
