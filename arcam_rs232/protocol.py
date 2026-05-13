from dataclasses import dataclass

START = 0x21
END = 0x0D
REQUEST = 0xF0

ZONE_MAP = {0x01: "Zone 1", 0x02: "Zone 2", 0x03: "Zone 3"}
ANSWER_MAP = {
    0x00: "Status update / OK",
    0x82: "Zone invalid",
    0x83: "Command not recognised",
    0x84: "Parameter not recognised",
    0x85: "Command invalid at this time",
    0x86: "Invalid data length",
}
SOURCE_MAP = {
    0x00: "Follow Zone 1", 0x01: "CD", 0x02: "DVD", 0x03: "AV", 0x04: "SAT",
    0x05: "PVR", 0x06: "VCR", 0x07: "Tape", 0x08: "Aux", 0x09: "Phono",
    0x0A: "Tuner AM", 0x0B: "Tuner FM", 0x0C: "Tuner Digital", 0x0D: "MCH",
    0x0E: "NET", 0x0F: "iPod",
}
SOURCE_NAME_TO_CODE = {v: k for k, v in SOURCE_MAP.items() if k != 0x00}
DISPLAY_BRIGHTNESS = {0x00: "Off", 0x01: "L1", 0x02: "L2", 0x03: "L3"}
VIDEO_INPUT_TYPE = {0x00: "Auto", 0x01: "HDMI", 0x02: "Component", 0x03: "S-Video", 0x04: "CVBS"}
VIDEO_SELECTION = {0x00: "DVD", 0x01: "SAT", 0x02: "AV", 0x03: "PVR", 0x04: "VCR"}
AUDIO_INPUT_TYPE = {0x00: "Analogue", 0x01: "Digital", 0x02: "HDMI"}
DIRECT_MODE = {0x00: "Off", 0x01: "On"}
DECODE_2CH = {
    0x00: "Mono", 0x01: "Stereo", 0x02: "Pro Logic II/x Movie", 0x03: "Pro Logic II/x Music",
    0x04: "Pro Logic II Matrix", 0x05: "Pro Logic II Game", 0x06: "Dolby Pro Logic Emulation",
    0x07: "Neo:6 Cinema", 0x08: "Neo:6 Music",
}
DECODE_MCH = {
    0x00: "Mono down-mix", 0x01: "Stereo down-mix", 0x02: "Multi-channel",
    0x03: "Dolby EX / DTS-ES", 0x04: "Pro Logic IIx movie", 0x05: "Pro Logic IIx music",
}
MENU_STATUS = {
    0x00: "No menu", 0x01: "Menu open", 0x02: "Setup menu", 0x03: "Trim menu",
    0x04: "Bass menu", 0x05: "Treble menu", 0x06: "Sync menu", 0x07: "Sub menu",
    0x08: "Tuner menu", 0x09: "Network menu", 0x0A: "iPod menu",
}
NETWORK_STATUS = {0x00: "Navigating", 0x01: "Playing", 0x02: "Paused", 0xFF: "Busy / Not Playing"}
VIDEO_RESOLUTION = {
    0x00: "480i", 0x01: "480p", 0x02: "576i", 0x03: "576p", 0x04: "720p 50Hz", 0x05: "720p 60Hz",
    0x08: "1080i 25Hz", 0x09: "1080i 30Hz", 0x0A: "1080p 24Hz", 0x0D: "1080p 50Hz", 0x0E: "1080p 60Hz",
}
ROOM_EQ = {0x00: "Off", 0x01: "On", 0x02: "Not calculated"}
DOLBY_VOLUME = {0x00: "Off", 0x01: "Music", 0x02: "Movie"}
COMPRESSION = {0x00: "Off", 0x01: "On/Auto", 0x02: "On"}
PICTURE_MODE = {0x00: "Auto", 0x01: "Video", 0x02: "Film"}
LOW_MEDIUM_HIGH = {0x00: "Off", 0x01: "Low", 0x02: "Medium", 0x03: "High"}
ZONE1_OSD = {0x00: "On", 0x01: "Off"}
VIDEO_OUTPUT_SWITCHING = {
    0x00: "HDMI Output 1 Auto-Priority",
    0x01: "HDMI Output 2 Auto-Priority",
    0x02: "HDMI Output 1",
    0x03: "HDMI Output 2",
    0x04: "HDMI Output 1 & 2",
}
OUTPUT_FRAME_RATE = {0x00: "Auto", 0x01: "50Hz", 0x02: "60Hz"}
BYPASS_MODE = {0x00: "Disabled", 0x01: "Enabled"}
INTERLACED_FLAG = {0x00: "Progressive", 0x01: "Interlaced"}
ASPECT_RATIO = {0x00: "Undefined", 0x01: "4:3", 0x02: "16:9"}
STEP_CONTROL = {"request": REQUEST, "up": 0xF1, "down": 0xF2, "inc": 0xF1, "dec": 0xF2}

SAMPLE_RATE_MAP = {
    0x00: "32 kHz",
    0x01: "44.1 kHz",
    0x02: "48 kHz",
    0x03: "88.2 kHz",
    0x04: "96 kHz",
    0x05: "176.4 kHz",
    0x06: "192 kHz",
    0x07: "Unknown",
    0x08: "Undetected",
}

AUDIO_FORMAT = {
    0x00: "PCM",
    0x01: "Analogue Direct",
    0x02: "Dolby Digital",
    0x03: "Dolby Digital EX",
    0x04: "Dolby Digital Surround",
    0x05: "Dolby Digital Plus",
    0x06: "Dolby Digital TrueHD",
    0x07: "DTS",
    0x08: "DTS 96/24",
    0x09: "DTS ES Matrix",
    0x0A: "DTS ES Discrete",
    0x0B: "DTS ES Matrix 96/24",
    0x0C: "DTS ES Discrete 96/24",
    0x0D: "DTS HD Master Audio",
    0x0E: "DTS HD High Res Audio",
    0x0F: "DTS Low Bit Rate",
    0x10: "DTS Core",
    0x11: "AAC",
    0x12: "MPEG",
    0x13: "PCM Zero",
    0x14: "Unsupported",
    0x15: "Undetected",
}
AUDIO_CHANNEL_CONFIG = {
    0x00: "Dual Mono",
    0x01: "Centre only",
    0x02: "Stereo only",
    0x03: "Stereo + mono surround",
    0x04: "Stereo + Surround L & R",
    0x05: "Stereo + Surround L & R + mono Surround Back",
    0x06: "Stereo + Surround L & R + Surround Back L & R",
    0x07: "Stereo + Surround L & R with matrix surround back",
    0x08: "Stereo + Centre",
    0x09: "Stereo + Centre + mono surround",
    0x0A: "Stereo + Centre + Surround L & R",
    0x0B: "Stereo + Centre + Surround L & R + mono Surround Back",
    0x0C: "Stereo + Centre + Surround L & R + Surround Back L & R",
    0x0D: "Stereo + Centre + Surround L & R with matrix surround back",
    0x0E: "Stereo Downmix Lt Rt",
    0x0F: "Stereo Only (Lo Ro)",
    0x10: "Dual Mono + LFE",
    0x11: "Centre + LFE",
    0x12: "Stereo + LFE",
    0x13: "Stereo + single surround + LFE",
    0x14: "Stereo + Surround L & R + LFE",
    0x15: "Stereo + Surround L & R + mono Surround Back + LFE",
    0x16: "Stereo + Surround L & R + Surround Back L & R + LFE",
    0x17: "Stereo + Surround L & R + LFE",
    0x18: "Stereo + Centre + LFE with matrix surround back",
    0x19: "Stereo + Centre + single surround + LFE",
    0x1A: "Stereo + Surround L & R + LFE (5.1)",
    0x1B: "Stereo + Centre + Surround L & R + mono Surround Back + LFE (6.1)",
    0x1C: "Stereo + Centre + Surround L & R + Surround Back L & R + LFE (7.1)",
    0x1D: "Stereo + Centre + Surround L & R + LFE with matrix surround back",
    0x1E: "Stereo Downmix Lt Rt + LFE",
    0x1F: "Stereo Only Lo Ro + LFE",
    0x20: "Unknown",
    0x21: "Undetected",
}

COMMAND_NAME_MAP = {
    0x00: "Power",
    0x01: "Display brightness",
    0x02: "Headphones",
    0x03: "FM genre",
    0x04: "Software version",
    0x05: "Restore factory defaults",
    0x06: "Save/restore secure settings",
    0x08: "Simulate RC5 IR command",
    0x09: "Display information type",
    0x0A: "Video selection",
    0x0B: "Audio input type",
    0x0C: "Video input type",
    0x0D: "Volume",
    0x0E: "Mute",
    0x0F: "Direct mode",
    0x10: "Decode mode 2ch",
    0x11: "Decode mode MCH",
    0x12: "RDS information",
    0x13: "Video output resolution",
    0x14: "Menu status",
    0x15: "Tuner preset",
    0x16: "Tuner frequency",
    0x18: "DAB/Sirius station",
    0x19: "Radio programme type/category",
    0x1A: "DLS/PDT information",
    0x1B: "Preset details",
    0x1C: "Network playback status",
    0x1D: "Current source",
    0x1F: "Headphone override",
    0x35: "Treble EQ",
    0x36: "Bass EQ",
    0x37: "Room EQ",
    0x38: "Dolby Volume",
    0x39: "Dolby Leveller",
    0x3A: "Dolby Volume calibration offset",
    0x3B: "Balance",
    0x3C: "Dolby Pro Logic II Dimension",
    0x3D: "Dolby Pro Logic II Centre Width",
    0x3E: "Dolby Pro Logic II Panorama",
    0x3F: "Subwoofer trim",
    0x40: "Lipsync delay",
    0x41: "Compression",
    0x42: "Incoming video parameters",
    0x43: "Incoming audio format",
    0x44: "Incoming audio sample rate",
    0x45: "Sub stereo trim",
    0x46: "Brightness",
    0x47: "Contrast",
    0x48: "Colour",
    0x49: "Picture mode",
    0x4A: "Edge enhancement",
    0x4B: "Mosquito noise reduction",
    0x4C: "Noise reduction",
    0x4D: "Block noise reduction",
    0x4E: "Zone 1 OSD",
    0x4F: "Video output switching",
    0x50: "Output frame rate",
    0x52: "Unknown command 0x52",
    0x53: "Bypass mode",
}

RC5_COMMANDS = {
    "standby": (0x10, 0x0C),
    "power-on": (0x10, 0x7B),
    "power-off": (0x10, 0x7C),
    "source-sat": (0x10, 0x00),
    "source-phono": (0x10, 0x01),
    "source-av": (0x10, 0x02),
    "source-tuner": (0x10, 0x03),
    "source-dvd": (0x10, 0x04),
    "source-tape": (0x10, 0x05),
    "source-vcr": (0x10, 0x06),
    "source-cd": (0x10, 0x07),
    "source-aux": (0x10, 0x08),
    "source-mch": (0x10, 0x09),
    "source-net": (0x10, 0x0B),
    "source-ipod": (0x10, 0x12),
    "source-pvr": (0x10, 0x22),
    "source-am": (0x10, 0x34),
    "source-fm": (0x10, 0x36),
    "source-dab": (0x10, 0x48),
    "mute-toggle": (0x10, 0x0D),
    "mute-on": (0x10, 0x77),
    "mute-off": (0x10, 0x78),
    "volume-up": (0x10, 0x10),
    "volume-down": (0x10, 0x11),
    "navigate-up": (0x10, 0x56),
    "navigate-left": (0x10, 0x51),
    "ok": (0x10, 0x57),
    "navigate-right": (0x10, 0x50),
    "navigate-down": (0x10, 0x55),
    "menu": (0x10, 0x52),
    "display": (0x10, 0x3B),
    "display-off": (0x10, 0x1F),
    "display-l1": (0x10, 0x21),
    "display-l2": (0x10, 0x23),
    "display-l3": (0x10, 0x24),
    "direct-toggle": (0x10, 0x0A),
    "direct-on": (0x10, 0x4E),
    "direct-off": (0x10, 0x4F),
    "dolby-volume-toggle": (0x10, 0x46),
    "dolby-volume-on": (0x10, 0x46),
    "dolby-volume-off": (0x10, 0x46),
    "mode": (0x10, 0x20),
    "room-eq-toggle": (0x10, 0x1E),
    "bass": (0x10, 0x27),
    "treble": (0x10, 0x0E),
    "speaker-trim": (0x10, 0x25),
    "lipsync": (0x10, 0x32),
    "subwoofer-trim": (0x10, 0x33),
    "ch-down": (0x10, 0x39),
    "ch-up": (0x10, 0x38),
    "red": (0x10, 0x29),
    "green": (0x10, 0x2A),
    "yellow": (0x10, 0x2B),
    "blue": (0x10, 0x37),
    "video-output-preferred": (0x10, 0x7D),
    "video-output-sd-interlaced": (0x10, 0x7E),
    "video-output-sd-progressive": (0x10, 0x0F),
    "video-output-720p": (0x10, 0x17),
    "video-output-1080i": (0x10, 0x1A),
    "video-output-1080p": (0x10, 0x1B),
    "hdmi-output-1": (0x10, 0x49),
    "hdmi-output-2": (0x10, 0x4A),
    "hdmi-output-1-and-2": (0x10, 0x4B),
    "frame-rate-50": (0x10, 0x40),
    "frame-rate-60": (0x10, 0x41),
    "video-bypass-toggle": (0x10, 0x42),
    "video-bypass-on": (0x10, 0x43),
    "video-bypass-off": (0x10, 0x44),
    "zone2-power-on": (0x17, 0x7B),
    "zone2-power-off": (0x17, 0x7C),
    "zone2-volume-up": (0x17, 0x01),
    "zone2-volume-down": (0x17, 0x02),
    "zone2-mute-toggle": (0x17, 0x03),
    "zone2-mute-on": (0x17, 0x04),
    "zone2-mute-off": (0x17, 0x05),
    "zone2-source-cd": (0x17, 0x06),
    "zone2-source-dvd": (0x17, 0x07),
    "zone2-source-sat": (0x17, 0x08),
    "zone2-source-av": (0x17, 0x09),
    "zone2-source-tape": (0x17, 0x0A),
    "zone2-source-vcr": (0x17, 0x0B),
    "zone2-source-pvr": (0x17, 0x0C),
    "zone2-source-aux": (0x17, 0x0D),
    "zone2-source-fm": (0x17, 0x0E),
    "zone2-source-am": (0x17, 0x0F),
    "zone2-source-dab": (0x17, 0x10),
    "zone2-source-phono": (0x17, 0x11),
    "zone2-source-ipod": (0x17, 0x12),
    "zone2-source-net": (0x17, 0x13),
    "zone3-power-on": (0x17, 0x79),
    "zone3-power-off": (0x17, 0x7A),
    "zone3-volume-up": (0x17, 0x17),
    "zone3-volume-down": (0x17, 0x15),
    "zone3-mute-toggle": (0x17, 0x16),
    "zone3-mute-on": (0x17, 0x17),
    "zone3-mute-off": (0x17, 0x18),
}

DIRECT_SET_COMMANDS = {
    "video-selection": (0x0A, {"dvd": 0x00, "sat": 0x01, "av": 0x02, "pvr": 0x03, "vcr": 0x04, **STEP_CONTROL}),
    "audio-input": (0x0B, {"analogue": 0x00, "analog": 0x00, "digital": 0x01, "hdmi": 0x02, **STEP_CONTROL}),
    "video-input": (0x0C, {"auto": 0x00, "hdmi": 0x01, "component": 0x02, "s-video": 0x03, "svideo": 0x03, "cvbs": 0x04, **STEP_CONTROL}),
    "video-output": (0x13, {"sd-interlaced": 0x01, "sd-progressive": 0x02, "720p": 0x03, "1080i": 0x04, "1080p": 0x05, "preferred": 0x06, **STEP_CONTROL}),
    "headphone-override": (0x1F, {"clear": 0x00, "off": 0x00, "set": 0x01, "on": 0x01}),
    "treble": (0x35, "signed_eq"),
    "bass": (0x36, "signed_eq"),
    "room-eq": (0x37, {"off": 0xF2, "on": 0xF1, "request": REQUEST}),
    "dolby-volume": (0x38, {"off": 0x00, "music": 0x01, "movie": 0x02, "request": REQUEST}),
    "dolby-leveller": (0x39, "dolby_leveller"),
    "dolby-calibration-offset": (0x3A, "signed_offset"),
    "balance": (0x3B, "signed_offset"),
    "dplii-dimension": (0x3C, "signed_offset"),
    "dplii-centre-width": (0x3D, "int"),
    "dplii-panorama": (0x3E, {"off": 0x00, "on": 0x01, "request": REQUEST}),
    "subwoofer-trim": (0x3F, "quarter_db"),
    "lipsync-delay": (0x40, "lipsync_ms"),
    "compression": (0x41, {"off": 0x00, "auto": 0x01, "on-auto": 0x01, "on": 0x02, "request": REQUEST}),
    "sub-stereo-trim": (0x45, "sub_stereo_trim"),
    "brightness": (0x46, "signed_eq_step"),
    "contrast": (0x47, "signed_eq_step"),
    "colour": (0x48, "signed_eq_step"),
    "picture-mode": (0x49, {"auto": 0x00, "video": 0x01, "film": 0x02, **STEP_CONTROL}),
    "edge-enhancement": (0x4A, {"off": 0x00, "low": 0x01, "medium": 0x02, "high": 0x03, **STEP_CONTROL}),
    "mosquito-nr": (0x4B, {"off": 0x00, "low": 0x01, "medium": 0x02, "high": 0x03, **STEP_CONTROL}),
    "noise-reduction": (0x4C, {"off": 0x00, "low": 0x01, "medium": 0x02, "high": 0x03, **STEP_CONTROL}),
    "block-nr": (0x4D, {"off": 0x00, "low": 0x01, "medium": 0x02, "high": 0x03, **STEP_CONTROL}),
    "zone1-osd": (0x4E, {"request": REQUEST, "on": 0xF1, "off": 0xF2}),
    "video-output-switching": (0x4F, {"hdmi1-auto": 0x00, "hdmi2-auto": 0x01, "hdmi1": 0x02, "hdmi2": 0x03, "hdmi1-and-2": 0x04, **STEP_CONTROL}),
    "output-frame-rate": (0x50, {"auto": 0x00, "follow-source": 0x01, "50hz": 0x02, "60hz": 0x03, **STEP_CONTROL}),
}

DIRECT_VALUE_HELP = {
    "int": "integer byte: 0..255",
    "signed_eq": "signed EQ value: -10..10",
    "signed_eq_step": "signed EQ value: -10..10, or request/up/down/inc/dec",
    "signed_offset": "signed offset value: -15..15",
    "dolby_leveller": "0..9, or off",
    "quarter_db": "trim in 0.25 dB steps: -10.0..10.0",
    "sub_stereo_trim": "trim in 0.25 dB steps: -10.0..0.0",
    "lipsync_ms": "delay in milliseconds, 5 ms steps",
}

DIRECT_GET_COMMANDS = {
    "power": 0x00,
    "display-brightness": 0x01,
    "headphones": 0x02,
    "fm-genre": 0x03,
    "software-version": 0x04,
    "video-selection": 0x0A,
    "audio-input": 0x0B,
    "video-input": 0x0C,
    "volume": 0x0D,
    "mute": 0x0E,
    "direct": 0x0F,
    "decode-2ch": 0x10,
    "decode-mch": 0x11,
    "rds": 0x12,
    "video-output": 0x13,
    "menu": 0x14,
    "tuner-preset": 0x15,
    "tuner-frequency": 0x16,
    "station": 0x18,
    "programme-type": 0x19,
    "dls-pdt": 0x1A,
    "preset-details": 0x1B,
    "network": 0x1C,
    "source": 0x1D,
    "headphone-override": 0x1F,
    "treble": 0x35,
    "bass": 0x36,
    "room-eq": 0x37,
    "dolby-volume": 0x38,
    "dolby-leveller": 0x39,
    "dolby-calibration-offset": 0x3A,
    "balance": 0x3B,
    "dplii-dimension": 0x3C,
    "dplii-centre-width": 0x3D,
    "dplii-panorama": 0x3E,
    "subwoofer-trim": 0x3F,
    "lipsync-delay": 0x40,
    "compression": 0x41,
    "incoming-video": 0x42,
    "incoming-audio": 0x43,
    "sample-rate": 0x44,
    "sub-stereo-trim": 0x45,
    "brightness": 0x46,
    "contrast": 0x47,
    "colour": 0x48,
    "picture-mode": 0x49,
    "edge-enhancement": 0x4A,
    "mosquito-nr": 0x4B,
    "noise-reduction": 0x4C,
    "block-nr": 0x4D,
    "zone1-osd": 0x4E,
    "video-output-switching": 0x4F,
    "output-frame-rate": 0x50,
    "bypass-mode": 0x53,
}


def hex_bytes(data):
    return " ".join(f"0x{b:02X}" for b in data)


def ascii_safe(data):
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in data)


def signed_offset_byte(b):
    return -(b - 0x80) if 0x80 <= b <= 0x8F else b


def signed_eq_byte(b):
    return -(b - 0x80) if 0x81 <= b <= 0x8A else b


def signed_quarter_db_byte(b):
    if b == 0:
        return "0 dB"
    if 0x01 <= b <= 0x28:
        return f"+{b * 0.25:g} dB"
    if 0x81 <= b <= 0xA8:
        return f"-{(b - 0x80) * 0.25:g} dB"
    return f"0x{b:02X}"


def sub_stereo_trim_byte(b):
    if b == 0:
        return "0 dB"
    if 0x80 <= b <= 0xA7:
        return f"-{(b - 0x7F) * 0.25:g} dB"
    return f"0x{b:02X}"


def format_half_value(a, b):
    return f"{a}.5" if b == 5 else str(a)


def command_label(cmd):
    return COMMAND_NAME_MAP.get(cmd, f"cmd 0x{cmd:02X}")


def build_frame(zone, command, data):
    return bytes([START, zone, command, len(data), *data, END])


def build_rc5_frame(zone, system, command):
    return build_frame(zone, 0x08, [system, command])


def request_frame(zone, command):
    return build_frame(zone, command, [REQUEST])


def volume_to_byte(zone, value):
    v = float(value)
    if zone == 0x01:
        doubled = round(v * 2)
        if abs(v * 2 - doubled) > 0.001:
            raise ValueError("Zone 1 volume must use 0.5 dB steps")
        if not 0 <= doubled <= 0xC6:
            raise ValueError("Zone 1 volume must be in range 0.0..99.0")
        return doubled
    integer = round(v)
    if abs(v - integer) > 0.001:
        raise ValueError("Zone 2/3 volume must use 1 dB steps")
    if not 0 <= integer <= 0x63:
        raise ValueError("Zone 2/3 volume must be in range 0..99")
    return integer


def int_byte(value, min_value=0x00, max_value=0xFF):
    n = int(value, 0)
    if not min_value <= n <= max_value:
        raise ValueError(f"value must be in range {min_value}..{max_value}")
    return n


def signed_byte(value, minimum, maximum):
    n = int(value, 0)
    if not minimum <= n <= maximum:
        raise ValueError(f"value must be in range {minimum}..{maximum}")
    return n if n >= 0 else 0x80 + abs(n)


def quarter_db_to_byte(value):
    v = float(value)
    steps = round(v / 0.25)
    if abs(v / 0.25 - steps) > 0.001:
        raise ValueError("value must use 0.25 dB steps")
    if not -10 <= v <= 10:
        raise ValueError("value must be in range -10.0..10.0 dB")
    return steps if steps >= 0 else 0x80 + abs(steps)


def sub_stereo_trim_to_byte(value):
    v = float(value)
    steps = round(abs(v) / 0.25)
    if abs(abs(v) / 0.25 - steps) > 0.001:
        raise ValueError("value must use 0.25 dB steps")
    if not -10 <= v <= 0:
        raise ValueError("sub stereo trim must be in range -10.0..0.0 dB")
    return 0 if steps == 0 else 0x7F + steps


def parse_direct_value(kind, value):
    text = value.strip().lower()
    if isinstance(kind, dict):
        if text not in kind:
            choices = ", ".join(sorted(kind.keys()))
            raise ValueError(f"unknown value {value!r}; choices: {choices}")
        return kind[text]
    if text == "request":
        return REQUEST
    if kind == "int":
        return int_byte(text)
    if kind == "signed_eq":
        return signed_byte(text, -10, 10)
    if kind == "signed_eq_step":
        if text in STEP_CONTROL:
            return STEP_CONTROL[text]
        return signed_byte(text, -10, 10)
    if kind == "signed_offset":
        return signed_byte(text, -15, 15)
    if kind == "dolby_leveller":
        if text == "off":
            return 0xFF
        return int_byte(text, 0, 9)
    if kind == "quarter_db":
        return quarter_db_to_byte(text)
    if kind == "sub_stereo_trim":
        return sub_stereo_trim_to_byte(text)
    if kind == "lipsync_ms":
        milliseconds = int(text, 0)
        if milliseconds % 5 != 0:
            raise ValueError("lipsync delay must use 5 ms steps")
        if not 0 <= milliseconds <= 255 * 5:
            raise ValueError("lipsync delay is out of range")
        return milliseconds // 5
    raise ValueError(f"unsupported value parser: {kind}")


def normalize_name(value):
    return value.strip().lower().replace("_", "-").replace(" ", "-")


def source_to_rc5_alias(zone, source):
    name = normalize_name(source)
    aliases = {"tuner-am": "am", "tuner-fm": "fm", "tuner-digital": "dab", "aux": "aux"}
    source_name = aliases.get(name, name)
    if zone == 0x01:
        return f"source-{source_name}"
    if zone == 0x02:
        if source_name == "mch":
            raise ValueError("Zone 2 does not have an MCH source RC5 command in the documentation")
        return f"zone2-source-{source_name}"
    raise ValueError("The documentation does not define source selection RC5 commands for Zone 3")


def zone_rc5_alias(zone, action):
    if zone == 0x01:
        return action
    return f"zone{zone}-{action}"


def rc5_frame_from_alias(zone, alias):
    key = normalize_name(alias)
    if key not in RC5_COMMANDS:
        raise ValueError(f"unknown RC5 command {alias!r}")
    system, command = RC5_COMMANDS[key]
    return build_rc5_frame(zone, system, command)


@dataclass
class Frame:
    raw: bytes
    zone: int
    command: int
    answer: int
    data: bytes


class ArcamDecoder:
    def decode_frame(self, raw: bytes):
        if len(raw) < 6:
            return {"type": "ignored", "reason": "Short sequence skipped", "raw_hex": hex_bytes(raw)}
        if raw[0] != START or raw[-1] != END:
            return {"type": "invalid", "reason": "Invalid start/end markers", "raw_hex": hex_bytes(raw)}
        zone, command, answer, dl = raw[1], raw[2], raw[3], raw[4]
        data = raw[5:-1]
        if len(data) != dl:
            return {"type": "invalid", "reason": f"Data length mismatch: DL={dl}, bytes={len(data)}", "raw_hex": hex_bytes(raw)}
        frame = Frame(raw=raw, zone=zone, command=command, answer=answer, data=data)
        return {
            "type": "frame",
            "raw_hex": hex_bytes(raw),
            "zone": ZONE_MAP.get(zone, f"Unknown zone 0x{zone:02X}"),
            "command": f"0x{command:02X}",
            "command_name": command_label(command),
            "answer_code": f"0x{answer:02X}",
            "answer": ANSWER_MAP.get(answer, "Unknown"),
            "data_hex": hex_bytes(data),
            "data_ascii": ascii_safe(data),
            "parsed": self._parsed(frame),
            "summary": self._summary(frame),
        }

    @staticmethod
    def _parsed(frame: Frame):
        c = frame.command
        d = frame.data

        if c == 0x42 and len(d) == 7:
            width = (d[0] << 8) | d[1]
            height = (d[2] << 8) | d[3]
            return {
                "type": "incoming_video_parameters",
                "width": width,
                "height": height,
                "refresh_rate_hz": d[4],
                "scan": INTERLACED_FLAG.get(d[5], f"0x{d[5]:02X}"),
                "aspect_ratio": ASPECT_RATIO.get(d[6], f"0x{d[6]:02X}"),
            }

        if c == 0x43 and len(d) == 2:
            return {
                "type": "incoming_audio_format",
                "format_code": f"0x{d[0]:02X}",
                "channel_config_code": f"0x{d[1]:02X}",
                "format": AUDIO_FORMAT.get(d[0]),
                "channel_config": AUDIO_CHANNEL_CONFIG.get(d[1]),
            }

        if c == 0x44 and len(d) == 1:
            return {
                "type": "incoming_audio_sample_rate",
                "code": f"0x{d[0]:02X}",
                "value": SAMPLE_RATE_MAP.get(d[0]),
            }

        if c == 0x52 and len(d) == 1:
            return {
                "type": "unknown_status_0x52",
                "value": f"0x{d[0]:02X}",
            }

        return None

    @staticmethod
    def _summary(frame: Frame):
        c = frame.command
        d = frame.data
        ac = ANSWER_MAP.get(frame.answer, f"0x{frame.answer:02X}")
        prefix = f"{ZONE_MAP.get(frame.zone, f'Zone 0x{frame.zone:02X}')} | {command_label(c)} | {ac}"
        if frame.answer != 0x00:
            return f"{prefix} | error, data={hex_bytes(d)}"
        if c == 0x00 and len(d) == 1:
            return f"{prefix} | Power: {'On' if d[0] == 0x01 else 'Standby'}"
        if c == 0x01 and len(d) == 1:
            return f"{prefix} | Display brightness: {DISPLAY_BRIGHTNESS.get(d[0], f'0x{d[0]:02X}') }"
        if c == 0x02 and len(d) == 1:
            return f"{prefix} | Headphones: {'Connected' if d[0] == 0x01 else 'Not connected'}"
        if c == 0x03 and len(d) >= 1:
            return f"{prefix} | FM genre: {ascii_safe(d)}"
        if c == 0x04 and len(d) == 3:
            return f"{prefix} | Software version request 0x{d[0]:02X}: {d[1]}.{d[2]}"
        if c == 0x08 and len(d) == 2:
            return f"{prefix} | RC5 echo: system=0x{d[0]:02X}, command=0x{d[1]:02X}"
        if c == 0x09 and len(d) == 1:
            return f"{prefix} | Display info type: 0x{d[0]:02X}"
        if c == 0x0A and len(d) == 1:
            return f"{prefix} | Video selection: {VIDEO_SELECTION.get(d[0], f'0x{d[0]:02X}') }"
        if c == 0x0B and len(d) == 1:
            return f"{prefix} | Audio input type: {AUDIO_INPUT_TYPE.get(d[0], f'0x{d[0]:02X}')}"
        if c == 0x0C and len(d) == 1:
            return f"{prefix} | Video input type: {VIDEO_INPUT_TYPE.get(d[0], f'0x{d[0]:02X}') }"
        if c == 0x0D and len(d) == 2:
            return f"{prefix} | Volume: {format_half_value(d[0], d[1])} dB"
        if c == 0x0E and len(d) == 1:
            return f"{prefix} | Mute: {'Muted' if d[0] == 0x00 else 'Not muted'}"
        if c == 0x0F and len(d) == 1:
            return f"{prefix} | Direct mode: {DIRECT_MODE.get(d[0], f'0x{d[0]:02X}') }"
        if c == 0x10 and len(d) == 1:
            return f"{prefix} | Decode 2ch: {DECODE_2CH.get(d[0], f'0x{d[0]:02X}') }"
        if c == 0x11 and len(d) == 1:
            return f"{prefix} | Decode MCH: {DECODE_MCH.get(d[0], f'0x{d[0]:02X}') }"
        if c == 0x12 and len(d) >= 1:
            return f"{prefix} | RDS: {ascii_safe(d)}"
        if c == 0x13 and len(d) == 1:
            return f"{prefix} | Video output: {VIDEO_RESOLUTION.get(d[0], f'0x{d[0]:02X}') }"
        if c == 0x14 and len(d) == 1:
            return f"{prefix} | Menu: {MENU_STATUS.get(d[0], f'0x{d[0]:02X}') }"
        if c == 0x15 and len(d) == 1:
            return f"{prefix} | Tuner preset: {'none' if d[0] == 0xFF else d[0]}"
        if c == 0x16 and len(d) == 2:
            return f"{prefix} | Tuner freq raw: {d[0]}.{d[1]:02X}"
        if c == 0x18 and len(d) >= 1:
            return f"{prefix} | DAB/Sirius station: {ascii_safe(d)}"
        if c == 0x19 and len(d) >= 1:
            return f"{prefix} | Programme type: {ascii_safe(d)}"
        if c == 0x1A and len(d) >= 1:
            return f"{prefix} | DLS/PDT: {ascii_safe(d)}"
        if c == 0x1B and len(d) >= 3:
            return f"{prefix} | Preset {d[0]}, type=0x{d[1]:02X}, value={ascii_safe(d[2:])}"
        if c == 0x1C and len(d) >= 1:
            return f"{prefix} | Network: {NETWORK_STATUS.get(d[0], f'0x{d[0]:02X}')}, text={ascii_safe(d[1:])}"
        if c == 0x1D and len(d) == 1:
            return f"{prefix} | Source: {SOURCE_MAP.get(d[0], f'0x{d[0]:02X}') }"
        if c == 0x1F and len(d) == 1:
            return f"{prefix} | Headphone override relay: {'Set' if d[0] == 0x01 else 'Clear'}"
        if c in (0x35, 0x36) and len(d) == 1:
            return f"{prefix} | {'Treble' if c == 0x35 else 'Bass'}: {signed_eq_byte(d[0])} dB"
        if c == 0x37 and len(d) == 1:
            return f"{prefix} | Room EQ: {ROOM_EQ.get(d[0], f'0x{d[0]:02X}') }"
        if c == 0x38 and len(d) == 1:
            return f"{prefix} | Dolby Volume: {DOLBY_VOLUME.get(d[0], f'0x{d[0]:02X}') }"
        if c == 0x39 and len(d) == 1:
            return f"{prefix} | Dolby Leveller: {'Off' if d[0] == 0xFF else d[0]}"
        if c == 0x3A and len(d) == 1:
            return f"{prefix} | Dolby calibration offset: {signed_offset_byte(d[0])} dB"
        if c == 0x3B and len(d) == 1:
            return f"{prefix} | Balance: {signed_offset_byte(d[0])}"
        if c == 0x3C and len(d) == 1:
            return f"{prefix} | DPLII Dimension: {signed_offset_byte(d[0])}"
        if c == 0x3D and len(d) == 1:
            return f"{prefix} | DPLII Centre Width: {d[0]}"
        if c == 0x3E and len(d) == 1:
            return f"{prefix} | DPLII Panorama: {'On' if d[0] == 0x01 else 'Off'}"
        if c == 0x3F and len(d) == 1:
            return f"{prefix} | Subwoofer trim: {signed_quarter_db_byte(d[0])}"
        if c == 0x40 and len(d) == 1:
            return f"{prefix} | Lipsync delay: {d[0] * 5} ms"
        if c == 0x41 and len(d) == 1:
            return f"{prefix} | Compression: {COMPRESSION.get(d[0], f'0x{d[0]:02X}')}"
        if c == 0x42 and len(d) == 7:
            width = (d[0] << 8) | d[1]
            height = (d[2] << 8) | d[3]
            scan = INTERLACED_FLAG.get(d[5], f"0x{d[5]:02X}")
            ratio = ASPECT_RATIO.get(d[6], f"0x{d[6]:02X}")
            return f"{prefix} | Video input: {width}x{height} {d[4]}Hz {scan}, aspect={ratio}"
        if c == 0x43 and len(d) == 2:
            audio_format = AUDIO_FORMAT.get(d[0], f"0x{d[0]:02X}")
            channel_config = AUDIO_CHANNEL_CONFIG.get(d[1], f"0x{d[1]:02X}")
            return f"{prefix} | {audio_format}, {channel_config}"
        if c == 0x44 and len(d) == 1:
            return f"{prefix} | {SAMPLE_RATE_MAP.get(d[0], f'Unknown code 0x{d[0]:02X}')}"
        if c == 0x45 and len(d) == 1:
            return f"{prefix} | Sub stereo trim: {sub_stereo_trim_byte(d[0])}"
        if c in (0x46, 0x47, 0x48) and len(d) == 1:
            labels = {0x46: "Brightness", 0x47: "Contrast", 0x48: "Colour"}
            return f"{prefix} | {labels[c]}: {signed_eq_byte(d[0])}"
        if c == 0x49 and len(d) == 1:
            return f"{prefix} | Picture mode: {PICTURE_MODE.get(d[0], f'0x{d[0]:02X}')}"
        if c in (0x4A, 0x4B, 0x4C, 0x4D) and len(d) == 1:
            labels = {
                0x4A: "Edge enhancement",
                0x4B: "Mosquito noise reduction",
                0x4C: "Noise reduction",
                0x4D: "Block noise reduction",
            }
            return f"{prefix} | {labels[c]}: {LOW_MEDIUM_HIGH.get(d[0], f'0x{d[0]:02X}')}"
        if c == 0x4E and len(d) == 1:
            return f"{prefix} | Zone 1 OSD: {ZONE1_OSD.get(d[0], f'0x{d[0]:02X}')}"
        if c == 0x4F and len(d) == 1:
            return f"{prefix} | Video output switching: {VIDEO_OUTPUT_SWITCHING.get(d[0], f'0x{d[0]:02X}')}"
        if c == 0x50 and len(d) == 1:
            return f"{prefix} | Output frame rate: {OUTPUT_FRAME_RATE.get(d[0], f'0x{d[0]:02X}')}"
        if c == 0x52 and len(d) == 1:
            return f"{prefix} | value=0x{d[0]:02X}"
        if c == 0x53 and len(d) == 1:
            return f"{prefix} | Bypass mode: {BYPASS_MODE.get(d[0], f'0x{d[0]:02X}')}"
        return f"{prefix} | data={hex_bytes(d)} ascii='{ascii_safe(d)}'"


class FrameReader:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, chunk: bytes):
        self.buffer.extend(chunk)
        frames = []
        while True:
            if not self.buffer:
                break
            try:
                start = self.buffer.index(START)
            except ValueError:
                self.buffer.clear()
                break
            if start > 0:
                del self.buffer[:start]
            if len(self.buffer) < 6:
                break
            if self.buffer[1] not in (0x01, 0x02, 0x03):
                del self.buffer[0]
                continue
            dl = self.buffer[4]
            frame_len = 6 + dl
            if len(self.buffer) < frame_len:
                break
            raw = bytes(self.buffer[:frame_len])
            if raw[-1] != END:
                del self.buffer[0]
                continue
            del self.buffer[:frame_len]
            frames.append(raw)
        return frames


