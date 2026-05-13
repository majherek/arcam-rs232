# arcam-rs232

Command-line RS232/TCP decoder and controller for Arcam AVR500, AVR600 and AV888 receivers.

This project implements parts of the Arcam custom-install protocol described in:

> Serial programming interface and IR remote commands for Arcam AVR500/AVR600/AV888

Protocol reference PDF:

https://www.arcam.co.uk/ugc/tor/av888/RS232/AVR600_RS232_SH217_E_7.0.pdf

It can run as a sniffer for status frames, decode responses, send direct RS232 commands, and emulate IR remote RC5 commands through the documented `Simulate RC5 IR Command` command (`0x08`).

## Supported Connections

The tool can communicate in two modes:

- Serial RS232, using a local serial adapter such as `/dev/ttyUSB0`, `/dev/ttyS0`, or `COM3`.
- TCP, using an RS232-to-Ethernet converter such as USR-DR132 in TCP server mode.

Default serial settings:

- Baud rate: `38400`
- Data bits: `8`
- Parity: none
- Stop bits: `1`
- Flow control: disabled

## Installation

This project uses Python and `pyserial`.

With `uv`:

```bash
uv sync
```

Or with plain `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install pyserial
```

Run the tool:

```bash
uv run arcam --help
```

The legacy wrapper remains available and runs the same CLI:

```bash
uv run python main.py --help
```

Or, if dependencies are already installed:

```bash
arcam --help
python main.py --help
```

The protocol code is also importable as a Python package for daemon or automation integrations:

```python
from arcam_rs232 import ArcamDecoder, FrameReader, request_frame
```

## Basic Usage

Sniff/listen on a serial port:

```bash
uv run arcam --serial /dev/ttyUSB0
```

Sniff/listen on a Windows serial port:

```bash
uv run arcam --serial COM3
```

Connect through an RS232-to-Ethernet converter:

```bash
uv run arcam --host 192.168.1.50 --port 8899
```

Print raw received chunks as hexadecimal bytes:

```bash
uv run arcam --serial /dev/ttyUSB0 --hex-dump
```

Output decoded frames as JSON:

```bash
uv run arcam --serial /dev/ttyUSB0 --format json
```

Select a zone:

```bash
uv run arcam --serial /dev/ttyUSB0 --zone 0x02 --get power
```

Zones are passed as integers, so both `2` and `0x02` are valid.

## Offline Hex Decoding

You can decode captured frames without opening a serial or TCP connection:

```bash
echo "0x21 0x01 0x0D 0x00 0x02 0x2D 0x05 0x0D" | uv run arcam --decode-hex
```

Example output:

```text
Zone 1 | Volume | Status update / OK | Volume: 45.5 dB
  raw:   0x21 0x01 0x0D 0x00 0x02 0x2D 0x05 0x0D
  data:  0x2D 0x05 | ascii: -.
```

## Protocol Notes

Arcam command frames sent to the receiver use:

```text
<St> <Zn> <Cc> <Dl> <Data...> <Et>
```

Responses from the receiver use:

```text
<St> <Zn> <Cc> <Ac> <Dl> <Data...> <Et>
```

Where:

- `St` is always `0x21`
- `Et` is always `0x0D`
- `Zn` is the zone
- `Cc` is the command code
- `Dl` is the data length
- `Ac` is the answer code in responses

This distinction matters. For example, setting Zone 1 volume to `45.5` sends one data byte:

```text
0x21 0x01 0x0D 0x01 0x5B 0x0D
```

The response contains the answer code and returns the volume as integer plus fraction:

```text
0x21 0x01 0x0D 0x00 0x02 0x2D 0x05 0x0D
```

## Reading Status

Use `--get` for direct RS232 status requests:

```bash
uv run arcam --serial /dev/ttyUSB0 --get power
uv run arcam --serial /dev/ttyUSB0 --get source
uv run arcam --serial /dev/ttyUSB0 --get volume
uv run arcam --serial /dev/ttyUSB0 --get mute
uv run arcam --serial /dev/ttyUSB0 --get incoming-audio
uv run arcam --serial /dev/ttyUSB0 --get incoming-video
```

List all supported status request names:

```bash
uv run arcam --help
```

## Sniffer Mode

When no action command is provided, the tool stays connected and works as a sniffer. It reads incoming frames from serial or TCP, extracts complete Arcam frames, and prints decoded status updates.

Serial sniffer:

```bash
uv run arcam --serial /dev/ttyUSB0
```

TCP sniffer:

```bash
uv run arcam --host 192.168.1.50 --port 8899
```

Add `--hex-dump` when you also want to see raw RX chunks.

## Common Control Aliases

The most common controls have convenient aliases:

```bash
uv run arcam --serial /dev/ttyUSB0 --power on
uv run arcam --serial /dev/ttyUSB0 --power standby
uv run arcam --serial /dev/ttyUSB0 --source DVD
uv run arcam --serial /dev/ttyUSB0 --source "Tuner FM"
uv run arcam --serial /dev/ttyUSB0 --set-volume 45.5
uv run arcam --serial /dev/ttyUSB0 --volume-up
uv run arcam --serial /dev/ttyUSB0 --volume-down
uv run arcam --serial /dev/ttyUSB0 --mute on
uv run arcam --serial /dev/ttyUSB0 --mute off
```

Important details:

- `--set-volume` uses the direct RS232 volume command (`0x0D`).
- `--power`, `--source`, `--mute`, `--volume-up`, and `--volume-down` use RC5 emulation through command `0x08` where the Arcam document does not provide a direct setter.
- Zone 1 volume uses `0.5 dB` steps.
- Zone 2 and Zone 3 volume use `1 dB` steps.

## Dry Run

Use `--dry-run` to print the generated transmit frame without opening serial or TCP:

```bash
uv run arcam --dry-run --power on
```

Output:

```text
0x21 0x01 0x08 0x02 0x10 0x7B 0x0D
```

More examples:

```bash
uv run arcam --dry-run --set-volume 45.5
uv run arcam --dry-run --source NET
uv run arcam --dry-run --mute off
uv run arcam --dry-run --set video-output 1080p
uv run arcam --dry-run --rc5 volume-up
```

## Direct RS232 Settings

Some options can be set directly with documented RS232 commands:

```bash
uv run arcam --serial /dev/ttyUSB0 --set video-output 1080p
uv run arcam --serial /dev/ttyUSB0 --set video-input hdmi
uv run arcam --serial /dev/ttyUSB0 --set audio-input digital
uv run arcam --serial /dev/ttyUSB0 --set room-eq on
uv run arcam --serial /dev/ttyUSB0 --set dolby-volume movie
uv run arcam --serial /dev/ttyUSB0 --set lipsync-delay 50
uv run arcam --serial /dev/ttyUSB0 --set subwoofer-trim -2.5
```

List supported direct settings and accepted values:

```bash
uv run arcam --list-set
```

Many settings accept `request`, `up`, `down`, `inc`, or `dec` when those values are documented by Arcam.

`--set` only exposes direct RS232 commands documented as setting/changing values. Request-only commands such as power state, display brightness, headphones, mute status, and current source remain under `--get`; controllable equivalents use RC5 aliases where the protocol documents them.

Display brightness command `0x01` is request-only. Use `--get display-brightness` to read it, or RC5 aliases to emulate the front-panel/remote display brightness commands:

```bash
uv run arcam --serial /dev/ttyUSB0 --rc5 display-off
uv run arcam --serial /dev/ttyUSB0 --rc5 display-l1
uv run arcam --serial /dev/ttyUSB0 --rc5 display-l2
uv run arcam --serial /dev/ttyUSB0 --rc5 display-l3
```

Value formats used by direct settings:

- `signed EQ value: -10..10` is used by tone and picture controls such as `bass`, `treble`, `brightness`, `contrast`, and `colour`.
- `signed offset value: -15..15` is used by controls such as `balance`, `dplii-dimension`, and `dolby-calibration-offset`.
- `trim in 0.25 dB steps` is used by subwoofer trim controls, for example `-2.5`.
- `delay in milliseconds, 5 ms steps` is used by `lipsync-delay`, for example `50`.

Examples:

```bash
uv run arcam --serial /dev/ttyUSB0 --set bass -2
uv run arcam --serial /dev/ttyUSB0 --set treble 3
uv run arcam --serial /dev/ttyUSB0 --set balance -4
uv run arcam --serial /dev/ttyUSB0 --set brightness up
uv run arcam --serial /dev/ttyUSB0 --set subwoofer-trim -2.5
uv run arcam --serial /dev/ttyUSB0 --set lipsync-delay 50
```

## RC5 Emulation

The Arcam protocol supports sending IR remote commands over RS232 with command `0x08`.

After sending a command, the tool waits for responses for the configured `--wait` window and decodes every received frame. For RC5 commands it also checks whether the receiver echoed the same RC5 system/command pair with answer code `0x00`.

For example, RC5 `16-17` (`0x10 0x11`, AVR volume down in Zone 1) is sent as:

```text
0x21 0x01 0x08 0x02 0x10 0x11 0x0D
```

A successful receiver acknowledgement is:

```text
0x21 0x01 0x08 0x00 0x02 0x10 0x11 0x0D
```

In text mode, the tool prints `RC5 acknowledgement: OK` when this acknowledgement is seen.

Use a named RC5 alias:

```bash
uv run arcam --serial /dev/ttyUSB0 --rc5 power-on
uv run arcam --serial /dev/ttyUSB0 --rc5 volume-up
uv run arcam --serial /dev/ttyUSB0 --rc5 source-dvd
uv run arcam --serial /dev/ttyUSB0 --rc5 menu
uv run arcam --serial /dev/ttyUSB0 --rc5 ok
```

List all known RC5 aliases:

```bash
uv run arcam --list-rc5
```

Send a raw RC5 system/command pair:

```bash
uv run arcam --serial /dev/ttyUSB0 --rc5-code 0x10 0x7B
```

This generates a `0x08` frame with two data bytes:

```text
0x21 0x01 0x08 0x02 0x10 0x7B 0x0D
```

## Raw Frames

For testing or unsupported commands, send a raw frame:

```bash
uv run arcam --serial /dev/ttyUSB0 --send-hex "0x21 0x01 0x0D 0x01 0xF0 0x0D"
```

This sends the bytes exactly as provided and then listens for responses for the configured wait window.

The parser treats values passed to `--send-hex` and `--decode-hex` as hexadecimal bytes. The documented style uses the explicit `0xNN` prefix to avoid confusion with decimal notation.

## TCP Converter Example

For a USR-DR132 or similar RS232-to-Ethernet converter:

1. Configure the converter with serial parameters `38400 8N1`.
2. Put the converter in TCP server mode.
3. Note its IP address and TCP port.
4. Connect with:

```bash
uv run arcam --host 192.168.1.50 --port 8899
```

Send a command through TCP:

```bash
uv run arcam --host 192.168.1.50 --port 8899 --power on
```

## Decoded Status Coverage

The decoder currently recognises common AVR500/AVR600/AV888 status responses including:

- Power, source, volume, mute
- Display brightness and display information type
- Audio and video input types
- Decode modes
- RDS, DAB/Sirius and network playback text/status
- Tuner preset and frequency data
- Video output resolution
- Menu status
- EQ, balance, Dolby Volume and compression settings
- Incoming audio format and sample rate
- Incoming video parameters
- Picture processing settings
- HDMI/video output switching

Unknown or unsupported responses are still printed with raw hex and ASCII-safe data.

## Safety Notes

Use `--dry-run` before sending new commands to real hardware.

Some RC5 commands are toggles, for example `mute-toggle` or `direct-toggle`. Prefer explicit aliases such as `mute-on`, `mute-off`, `direct-on`, or `direct-off` when available.

Factory reset and secure-settings commands exist in the protocol, but this tool does not expose convenience aliases for destructive operations.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
