# BC250-Phosphor theme generator: renders background.png and writes theme.yaml from a single layout,
# so static art and live widgets always line up. Edit the settings below (or pass them as options), then run:
#     python3 res/themes/BC250-Phosphor/make_theme.py --help
# Turing 3.5": landscape 480x320 (default) or portrait 320x480 (--portrait). All geometry is in set_layout().
#
# Alignment rules used throughout:
#   - every text is placed by its BASELINE, so mixed font sizes on one row sit on the same line
#   - every live text gets a fixed box (WIDTH/HEIGHT) sized for its longest value: the app repaints the whole box on
#     each refresh, so a shorter value never leaves characters of the previous one behind
#   - left-aligned values have no padding (MIN_SIZE 1) so they start exactly under their label; right-side values
#     and labels end on the same edge as the bars and graphs below them

import argparse
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

THEME_DIR = Path(__file__).resolve().parent
FONTS_DIR = THEME_DIR.parent.parent / "fonts"

# --- Settings (overridable from the command line) ---------------------------------------------------------------------
PROMPT_USER = "steam"  # steam@bc250:~$
PROMPT_HOST = "bc250"
TITLE = None  # header text; None = "<LOGO>::<USER>"
LOGO = "BC-250"  # big 3D title of the boot splash
SUBTITLE = "STEAM MACHINE"  # under it, letter-spaced
TEMP_COLD = 40  # °C at or below which temperatures are fully green
TEMP_HOT = 70  # °C at or above which temperatures are fully orange
TEMP_ALERT = 80  # °C from which temperatures turn red and flash "HOT!"
POWER_LOW = 100  # W at or below which APU power is fully green
POWER_HIGH = 200  # W at or above which APU power is fully red (orange half way)
POWER_BAR_MAX = 250  # W for a full bar
TEMP_GRAPH_MIN, TEMP_GRAPH_MAX = 30, 90
DIM_AFTER = 10  # minutes without game or download before dimming (0 = never)
DIM_BRIGHTNESS = 5  # % when dimmed
NIGHT = ""  # e.g. "23:30-08:00": screen off (or dimmed) during these hours unless a game is running
NIGHT_MODE = "off"  # "off" or "dim"
SPLASH = True  # BIOS-style boot screen played before the dashboard

# P1 phosphor palette
BG = (2, 9, 4)
DIM = (18, 78, 38)
MID = (46, 170, 88)
BRIGHT = (125, 255, 165)
AMBER = (255, 176, 40)
HOT = (255, 140, 30)
ALERT = (255, 60, 40)
INK = (2, 14, 6)  # dark text on the lit header band
GRID_DOT = (8, 34, 16)

FONT = "fusion-pixel/fusion-pixel-12px-monospaced-zh_hans.otf"  # pixel font: use multiples of 12 only
S, M, L = 12, 24, 36  # 1x / 2x / 3x
CH = {S: 6, M: 12, L: 18}  # monospace advance per size
ASCENT = {S: 10, M: 20, L: 30}  # font ascent per size (ImageFont.getmetrics)

HEADER_H = 16
HEADER_BL = 12
CLOCK_CHARS = 8  # "HH:mm:ss"


# ---------------------------------------------------------------------------------------------------------------------
# Layout: every position lives here, one block per orientation
# ---------------------------------------------------------------------------------------------------------------------
def panel(x1, y1, x2, y2, col_a_offset):
    """A CPU/GPU panel: frame box and everything inside, relative to its top-left corner."""
    x0, xr = x1 + 10, x2 - 10
    return {
        "box": (x1, y1, x2, y2),
        "x0": x0,
        "xr": xr,  # right edge shared by bar, graph and right column
        "col_a": x0 + col_a_offset,  # left-anchored middle column (TEMP)
        "label_bl": y1 + 18,  # small labels above values
        "value_bl": y1 + 40,  # big number and side values share this baseline
        "bar": (x0, y1 + 48, xr - x0, 8),
        "graph": (x0, y1 + 66, xr - x0, (y2 - y1) - 74),
    }


def cell(x0, y0, width):
    """A system-grid cell: label row, value row, then a bar or a sparkline."""
    return {"x0": x0, "xr": x0 + width, "y0": y0,
            "label_bl": y0 + 10, "value_bl": y0 + 32,
            "bar": (x0, y0 + 37, width, 6),
            "spark": (x0, y0 + 37, width, 9)}


def set_layout(portrait: bool):
    global PORTRAIT, W, H, CLOCK_XR, DATE_XR, cpu, gpu, GRID, GRID_COLS, CELL_W, CELL_GAP, cells
    global PROMPT_Y, PROMPT_LABEL_BL, PROMPT_VALUE_BL, PROMPT_COLS_BL, PROMPT_X, PROMPT_XR, PROMPT_AREA
    global PROMPT_COL1_XR, PROMPT_COLS, SPLASH_LAYOUT
    PORTRAIT = portrait
    if not portrait:  # 480x320: CPU and GPU side by side, 3x2 grid, one-line prompt
        W, H = 480, 320
        DATE_XR = W - 6 - CLOCK_CHARS * CH[S] - 12
        cpu = panel(4, 26, 237, 162, col_a_offset=100)
        gpu = panel(243, 26, 476, 162, col_a_offset=100)
        GRID, CELL_W, CELL_GAP, grid_cols, grid_rows = (4, 170, 476, 274), 142, 13, 3, 2
        order = (("ram", 0, 0), ("ssd", 1, 0), ("pwr", 2, 0), ("rx", 0, 1), ("tx", 1, 1), ("ping", 2, 1))
        PROMPT_Y, PROMPT_LABEL_BL, PROMPT_VALUE_BL, PROMPT_COLS_BL = 278, 290, 314, None
        PROMPT_COL1_XR = 380  # right edge of the first right-hand column (FPS / DONE / TIME)
        SPLASH_LAYOUT = dict(
            logo_box=(96, 21, 288, 75), logo_center_y=60, sub_bl=104, sep_y=114,
            row_bl=132, row_step=15, label_x=14, value_x=86, status_xr=466,
            progress_bl=254, bar=(214, 246, 466 - 214, 8), status_bl=284,
            footer=((14, 312, "left", "press"), (466, 312, "right", "prompt")))
    else:  # 320x480: panels stacked, 2x3 grid, prompt with its values on a row of their own
        W, H = 320, 480
        DATE_XR = None  # no room for the date in the header
        cpu = panel(4, 26, 316, 138, col_a_offset=130)
        gpu = panel(4, 146, 316, 258, col_a_offset=130)
        GRID, CELL_W, CELL_GAP, grid_cols, grid_rows = (4, 266, 316, 418), 140, 12, 2, 3
        order = (("ram", 0, 0), ("ssd", 1, 0), ("pwr", 0, 1), ("ping", 1, 1), ("rx", 0, 2), ("tx", 1, 2))
        PROMPT_Y, PROMPT_LABEL_BL, PROMPT_VALUE_BL, PROMPT_COLS_BL = 422, 434, 455, 476
        PROMPT_COL1_XR = None
        SPLASH_LAYOUT = dict(
            logo_box=(16, 26, 288, 90), logo_center_y=71, sub_bl=132, sep_y=142,
            row_bl=166, row_step=20, label_x=14, value_x=70, status_xr=306,
            progress_bl=324, bar=(14, 334, 292, 8), status_bl=372,
            footer=((14, 454, "left", "press"), (14, 470, "left", "prompt")))
    CLOCK_XR = W - 6
    GRID_COLS = [GRID[0] + 10 + i * (CELL_W + CELL_GAP) for i in range(grid_cols)]
    grid_rows_y = [GRID[1] + 8 + i * 48 for i in range(grid_rows)]
    cells = {name: cell(GRID_COLS[col], grid_rows_y[row], CELL_W) for name, col, row in order}
    PROMPT_X, PROMPT_XR = 14, W - 14
    PROMPT_AREA = (6, PROMPT_Y + 2, W - 12, H - PROMPT_Y - 2)  # redrawn as a whole by Bc250Prompt
    # portrait: values on their own row, in two half-width columns (small label left, value right)
    half = (PROMPT_XR - PROMPT_X - CELL_GAP) // 2
    PROMPT_COLS = [[PROMPT_X, PROMPT_X + half], [PROMPT_XR - half, PROMPT_XR]] if portrait else None
    SPLASH_LAYOUT["logo_max_w"] = 256  # leaves room in the logo box for the 3D sway and perspective
    SPLASH_LAYOUT["value_chars"] = (SPLASH_LAYOUT["status_xr"] - 6 * CH[S] - 8 - SPLASH_LAYOUT["value_x"]) // CH[S]


set_layout(portrait=False)


def logo_size(text):
    """Largest crisp size (a multiple of the pixel font's 12 px) at which the logo fits its box."""
    for size in (72, 60, 48, 36, 24):
        if len(text) * size // 2 <= SPLASH_LAYOUT["logo_max_w"]:
            return size
    return 24


def logo_baseline(size):
    return SPLASH_LAYOUT["logo_center_y"] + size * 8 // 12 // 2  # cap height is 8/12 of the size


def spaced(text):
    """S T E A M   M A C H I N E"""
    return "   ".join(" ".join(word) for word in text.split())


def rgb(c):
    return f"{c[0]}, {c[1]}, {c[2]}"


# ---------------------------------------------------------------------------------------------------------------------
# theme.yaml helpers
# ---------------------------------------------------------------------------------------------------------------------
def text(x, baseline, size, chars, color=BRIGHT, unit=True, right=False, extra_height=0, **extra):
    """A live text in a fixed box. x is the left edge, or the right edge when right=True."""
    width = chars * CH[size]
    t = {"SHOW": True, "SHOW_UNIT": unit,
         "X": x - width if right else x, "Y": baseline - ASCENT[size],
         "WIDTH": width, "HEIGHT": size + extra_height,
         "FONT": FONT, "FONT_SIZE": size, "FONT_COLOR": rgb(color), "BACKGROUND_IMAGE": "background.png",
         "ALIGN": "right" if right else "left", "ANCHOR": "ra" if right else "la"}
    if not right:
        t["MIN_SIZE"] = 1  # no left padding: value starts exactly at X
    t.update(extra)
    return t


def bar(x, y, w, h, color=BRIGHT, max_value=100):
    return {"SHOW": True, "X": x, "Y": y, "WIDTH": w, "HEIGHT": h, "MIN_VALUE": 0, "MAX_VALUE": max_value,
            "BAR_COLOR": rgb(color), "BAR_OUTLINE": False, "BACKGROUND_IMAGE": "background.png"}


def line(x, y, w, h, max_value=100, history=48, autoscale=False, color=BRIGHT):
    return {"SHOW": True, "X": x, "Y": y, "WIDTH": w, "HEIGHT": h, "MIN_VALUE": 0, "MAX_VALUE": max_value,
            "HISTORY_SIZE": history, "AUTOSCALE": autoscale, "LINE_COLOR": rgb(color), "LINE_WIDTH": 1,
            "AXIS": False, "BACKGROUND_IMAGE": "background.png"}


def heat_widget(p):
    """Temperature drawn by sensors_bc250: value and history coloured green -> orange -> red, flashing from ALERT."""
    x1, y1 = p["box"][:2]
    graph = p["graph"]
    return {
        "COLD": TEMP_COLD, "HOT": TEMP_HOT, "ALERT": TEMP_ALERT,
        "COLD_COLOR": rgb(BRIGHT), "HOT_COLOR": rgb(HOT), "ALERT_COLOR": rgb(ALERT), "INK": rgb(INK),
        "HEAT_TEXT": text(p["col_a"], p["value_bl"], M, 5),
        "ALERT_TAG": {"X": x1 + 8, "Y": y1 - 6, "WIDTH": 32, "HEIGHT": 13, "FONT": FONT, "FONT_SIZE": S,
                      "BACKGROUND_IMAGE": "background.png"},
        "HEAT_GRAPH": {"X": graph[0], "Y": graph[1], "WIDTH": graph[2], "HEIGHT": graph[3],
                       "MIN_VALUE": TEMP_GRAPH_MIN, "MAX_VALUE": TEMP_GRAPH_MAX, "AXIS_COLOR": rgb(MID),
                       "FONT": FONT, "FONT_SIZE": S, "BACKGROUND_IMAGE": "background.png"},
    }


def to_yaml(data, indent=0):
    out = []
    for k, v in data.items():
        pad = "  " * indent
        if isinstance(v, dict):
            out.append(f"{pad}{k}:")
            out.append(to_yaml(v, indent + 1))
        elif isinstance(v, bool):
            out.append(f"{pad}{k}: {v}")
        elif isinstance(v, str) and (any(c in v for c in ':#"@') or v != v.strip() or v == ""
                                     or v.lower() in ("on", "off", "yes", "no", "true", "false", "null")):
            out.append(f'{pad}{k}: "{v}"' if '"' not in v else f"{pad}{k}: '{v}'")
        else:
            out.append(f"{pad}{k}: {v}")
    return "\n".join(out)


def header_layout(title):
    """x of the "UP" label, x of the uptime value and its width in characters (0 = no room for it)."""
    up_x = 6 + len(title) * CH[S] + 12
    uptime_x = up_x + 3 * CH[S]
    room_right = (DATE_XR - 14 * CH[S]) if DATE_XR else (CLOCK_XR - CLOCK_CHARS * CH[S])
    chars = min(20, (room_right - 8 - uptime_x) // CH[S])
    return up_x, uptime_x, (chars if chars >= 8 else 0)


def build_theme(title, prompt):
    _, uptime_x, uptime_chars = header_layout(title)
    net_spark = dict(max_value=10_000_000_000, autoscale=True)
    ram, ssd, pwr, rx, tx, ping = (cells[k] for k in ("ram", "ssd", "pwr", "rx", "tx", "ping"))
    sl = SPLASH_LAYOUT
    date = {"INTERVAL": 1}
    if DATE_XR:
        date["DAY"] = {"TEXT": text(DATE_XR, HEADER_BL, S, 14, INK, right=True, FORMAT="EEE dd MMM")}
    date["HOUR"] = {"TEXT": text(CLOCK_XR, HEADER_BL, S, CLOCK_CHARS, INK, right=True, FORMAT="HH:mm:ss")}
    prompt_spec = {
        "AREA": {"X": PROMPT_AREA[0], "Y": PROMPT_AREA[1], "WIDTH": PROMPT_AREA[2],
                 "HEIGHT": PROMPT_AREA[3], "BACKGROUND_IMAGE": "background.png"},
        "FONT": FONT, "BRIGHT": rgb(BRIGHT), "MID": rgb(MID), "DIM": rgb(DIM), "AMBER": rgb(AMBER),
        "LABEL_BL": PROMPT_LABEL_BL, "VALUE_BL": PROMPT_VALUE_BL,
        "CMD_X": PROMPT_X + (len(prompt) + 1) * CH[S], "TEXT_X": PROMPT_X,
    }
    if PROMPT_COLS:  # portrait: the name gets the whole row, values go on the row below
        prompt_spec.update({"COLS_BL": PROMPT_COLS_BL, "COLS": PROMPT_COLS,
                            "MAX_CHARS": (PROMPT_XR - PROMPT_X) // CH[M] - 1,
                            "MAX_CHARS_WIDE": (PROMPT_XR - PROMPT_X) // CH[M] - 1})
    else:
        prompt_spec.update({"COL1_XR": PROMPT_COL1_XR, "COL2_XR": PROMPT_XR,
                            "MAX_CHARS": (PROMPT_COL1_XR - 4 * CH[M] - 12 - PROMPT_X) // CH[M] - 1,
                            "MAX_CHARS_WIDE": (PROMPT_XR - 5 * CH[M] - 12 - PROMPT_X) // CH[M] - 1})
    theme = {
        "author": "BC-250 Steam Machine",
        # read by sensors_bc250 (not by the app itself): the boot sequence played before the dashboard
        "bc250_splash": {
            "ENABLED": SPLASH, "IMAGE": "splash.png", "FONT": FONT, "ALERT": TEMP_ALERT,
            "BRIGHT": rgb(BRIGHT), "MID": rgb(MID), "DIM": rgb(DIM), "AMBER": rgb(AMBER), "ALERT_COLOR": rgb(ALERT),
            "BG": rgb(BG), "ROW_BL": sl["row_bl"], "ROW_STEP": sl["row_step"], "ROWS": 7,
            "LABEL_X": sl["label_x"], "VALUE_X": sl["value_x"], "STATUS_XR": sl["status_xr"],
            "VALUE_CHARS": sl["value_chars"],
            "PROGRESS_BL": sl["progress_bl"], "STATUS_BL": sl["status_bl"], "BAR_X": sl["bar"][0],
            "BAR_Y": sl["bar"][1], "BAR_W": sl["bar"][2], "BAR_H": sl["bar"][3],
            "IMAGE_NOLOGO": "splash_nologo.png", "LOGO_TEXT": LOGO, "LOGO_SIZE": logo_size(LOGO),
            "LOGO_BL": logo_baseline(logo_size(LOGO)), "LOGO_BOX": list(sl["logo_box"]),
        },
        "display": {"DISPLAY_SIZE": '3.5"', "DISPLAY_ORIENTATION": "portrait" if PORTRAIT else "landscape",
                    "DISPLAY_RGB_LED": rgb(MID)},
        "static_images": {"BACKGROUND": {"PATH": "background.png", "X": 0, "Y": 0, "WIDTH": W, "HEIGHT": H}},
        "STATS": {
            "CPU": {
                "PERCENTAGE": {
                    "INTERVAL": 1,
                    "TEXT": text(cpu["x0"], cpu["value_bl"], L, 4),
                    "GRAPH": bar(*cpu["bar"]),
                },
                "FREQUENCY": {"INTERVAL": 2, "TEXT": text(cpu["xr"], cpu["value_bl"], M, 4, unit=False, right=True)},
            },
            "MEMORY": {
                "INTERVAL": 2,
                "VIRTUAL": {
                    "PERCENT_TEXT": text(ram["x0"], ram["value_bl"], M, 4),
                    "USED": text(ram["xr"], ram["value_bl"], S, 8, MID, right=True),
                    "GRAPH": bar(*ram["bar"]),
                },
            },
            "NET": {
                "INTERVAL": 1,
                "ETH": {
                    "DOWNLOAD": {"TEXT": text(rx["x0"], rx["value_bl"], M, 11),
                                 "LINE_GRAPH": line(*rx["spark"], **net_spark)},
                    "UPLOAD": {"TEXT": text(tx["x0"], tx["value_bl"], M, 11),
                               "LINE_GRAPH": line(*tx["spark"], **net_spark)},
                },
            },
            "PING": {
                "INTERVAL": 5,
                "TEXT": text(ping["x0"], ping["value_bl"], M, 8),
                "LINE_GRAPH": line(*ping["spark"], max_value=200),
            },
            "DATE": date,
            "CUSTOM": {
                "INTERVAL": 1,
                "Bc250CpuTemp": heat_widget(cpu),
                "Bc250GpuLoad": {"TEXT": text(gpu["x0"], gpu["value_bl"], L, 4), "GRAPH": bar(*gpu["bar"])},
                "Bc250GpuTemp": heat_widget(gpu),
                "Bc250GpuClock": {"TEXT": text(gpu["xr"], gpu["value_bl"], M, 4, right=True)},
                "Bc250GameDisk": {"TEXT": text(ssd["x0"], ssd["value_bl"], M, 4), "GRAPH": bar(*ssd["bar"])},
                "Bc250GameDiskFree": {"TEXT": text(ssd["xr"], ssd["value_bl"], S, 7, MID, right=True)},
                "Bc250ApuPower": {
                    "COLD": POWER_LOW, "HOT": (POWER_LOW + POWER_HIGH) // 2, "ALERT": POWER_HIGH,
                    "COLD_COLOR": rgb(BRIGHT), "HOT_COLOR": rgb(HOT), "ALERT_COLOR": rgb(ALERT),
                    "HEAT_TEXT": text(pwr["x0"], pwr["value_bl"], M, 4),
                    "HEAT_BAR": {"X": pwr["bar"][0], "Y": pwr["bar"][1], "WIDTH": pwr["bar"][2],
                                 "HEIGHT": pwr["bar"][3], "MIN_VALUE": 0, "MAX_VALUE": POWER_BAR_MAX,
                                 "BACKGROUND_IMAGE": "background.png"},
                },
                "Bc250GpuMem": {"TEXT": text(pwr["xr"], pwr["value_bl"], S, 6, MID, right=True)},
                # after the temperature widgets: it records their peaks during a game session
                "Bc250Prompt": prompt_spec,
                "Bc250Screen": {"SCREEN": {"DIM_AFTER": DIM_AFTER, "DIM_BRIGHTNESS": DIM_BRIGHTNESS,
                                           "NIGHT": NIGHT, "NIGHT_MODE": NIGHT_MODE}},
            },
        },
    }
    if uptime_chars:
        theme["STATS"]["UPTIME"] = {"INTERVAL": 1,
                                    "FORMATTED": {"TEXT": text(uptime_x, HEADER_BL, S, uptime_chars, INK)}}
    # keep the original key order (STATS: CPU, MEMORY, NET, PING, DATE, UPTIME, CUSTOM)
    stats = theme["STATS"]
    theme["STATS"] = {k: stats[k] for k in ("CPU", "MEMORY", "NET", "PING", "DATE", "UPTIME", "CUSTOM") if k in stats}
    return theme


# ---------------------------------------------------------------------------------------------------------------------
# Background rendering
# ---------------------------------------------------------------------------------------------------------------------
def font(size):
    return ImageFont.truetype(str(FONTS_DIR / FONT), size)


class Canvas:
    def __init__(self):
        self.img = Image.new("RGB", (W, H), BG)
        self.glow = Image.new("RGB", (W, H), (0, 0, 0))  # what gets the phosphor bloom
        self.d, self.g = ImageDraw.Draw(self.img), ImageDraw.Draw(self.glow)

    def label(self, x, baseline, s, color=MID, anchor="ls", size=S, glow=True):
        self.d.text((x, baseline), s, font=font(size), fill=color, anchor=anchor)
        if glow:
            self.g.text((x, baseline), s, font=font(size), fill=color, anchor=anchor)

    def tag(self, x, y, title, subtitle=None):
        """Inverse-video tag centred on a frame's top line, e.g. [CPU] ZEN2 6C/12T"""
        w = len(title) * CH[S] + 8
        self.d.rectangle((x, y - 6, x + w - 1, y + 6), fill=MID)
        self.label(x + 4, y + 4, title, INK, glow=False)
        if subtitle:
            sx = x + w + 4
            self.d.rectangle((sx - 3, y - 6, sx + len(subtitle) * CH[S] + 2, y + 6), fill=BG)
            self.label(sx, y + 4, subtitle)

    def frame(self, box, title=None, subtitle=None):
        x1, y1, x2, y2 = box
        self.d.rectangle(box, outline=DIM)
        for cx, cy, sx, sy in ((x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)):
            self.d.line((cx, cy, cx + 8 * sx, cy), fill=MID)  # brighter HUD corners
            self.d.line((cx, cy, cx, cy + 8 * sy), fill=MID)
        if title:
            self.tag(x1 + 8, y1, title, subtitle)

    def bar_track(self, x, y, w, h, ticks=True):
        for px in range(x, x + w, 2):
            self.d.point((px, y + h // 2), fill=DIM)
        if ticks:
            for i in range(5):
                tx = x + round(i * (w - 1) / 4)
                self.d.line((tx, y + h + 1, tx, y + h + 2), fill=DIM)

    def graph_grid(self, x, y, w, h):
        for gy in range(y, y + h, 8):
            for gx in range(x, x + w, 4):
                self.d.point((gx, gy), fill=GRID_DOT)
        for gx in range(x, x + w, 32):
            for gy in range(y, y + h, 2):
                self.d.point((gx, gy), fill=GRID_DOT)

    def dotted_hline(self, x1, x2, y):
        for sx in range(x1, x2, 3):
            self.d.point((sx, y), fill=DIM)

    def dotted_vline(self, x, y1, y2):
        for sy in range(y1, y2, 3):
            self.d.point((x, sy), fill=DIM)

    def finish(self):
        bloom = self.glow.filter(ImageFilter.GaussianBlur(3))
        img = ImageChops.add(self.img, bloom.point(lambda v: int(v * 0.55)))
        # vignette + scanlines (dark rows are the odd ones: sensors_bc250 draws its chart fills on even rows)
        px = img.load()
        cx, cy = W / 2, H / 2
        max_r = math.hypot(cx, cy)
        for y in range(H):
            scan = 0.78 if y % 2 else 1.0
            for x in range(W):
                k = scan * (1.0 - 0.45 * (math.hypot(x - cx, y - cy) / max_r) ** 2.2)
                r, g, b = px[x, y]
                px[x, y] = (int(r * k), int(g * k), int(b * k))
        return img


def render_background(title, prompt):
    c = Canvas()
    up_x, _, uptime_chars = header_layout(title)

    # Header band (inverse video)
    c.d.rectangle((0, 0, W, HEADER_H), fill=MID)
    c.g.rectangle((0, 0, W, HEADER_H), fill=DIM)
    c.label(6, HEADER_BL, title, INK, glow=False)
    if uptime_chars:
        c.label(up_x, HEADER_BL, "UP", (14, 70, 34), glow=False)

    # CPU / GPU panels: same columns in both, LOAD % | TEMP | CLK
    for p, name, subtitle, clk in ((cpu, "CPU", "ZEN2 6C/12T", "CLK GHZ"), (gpu, "GPU", "RDNA2 24CU", "CLK MHZ")):
        c.frame(p["box"], name, subtitle)
        c.label(p["col_a"], p["label_bl"], "TEMP")
        c.label(p["xr"], p["label_bl"], clk, anchor="rs")
        c.bar_track(*p["bar"])
        c.graph_grid(*p["graph"])
        if p["graph"][3] >= 50:  # on short charts it would collide with the threshold labels
            c.label(p["xr"] - 2, p["graph"][1] + 10, "°C 60s", DIM, anchor="rs")

    # System grid
    c.frame(GRID, "SYS", "MEM / STORAGE / NET")
    labels = [("ram", "RAM", "USED", "bar"), ("ssd", "GAMES SSD", "FREE", "bar"), ("pwr", "APU PWR", "GPU MEM", "bar"),
              ("rx", "↓ DOWNLOAD", None, "spark"), ("tx", "↑ UPLOAD", None, "spark"), ("ping", "PING", None, "spark")]
    for key, label, sublabel, kind in labels:
        cl = cells[key]
        c.label(cl["x0"], cl["label_bl"], label)
        if sublabel:
            c.label(cl["xr"], cl["label_bl"], sublabel, DIM, anchor="rs")
        if kind == "bar":
            c.bar_track(*cl["bar"], ticks=False)
        else:
            c.graph_grid(*cl["spark"])
    for col in range(1, len(GRID_COLS)):
        c.dotted_vline(GRID_COLS[col] - (CELL_GAP + 1) // 2, GRID[1] + 8, GRID[3] - 4)

    # Now playing prompt
    c.dotted_hline(4, W - 4, PROMPT_Y)
    c.label(PROMPT_X, PROMPT_LABEL_BL, prompt)  # the command word and values are drawn live by Bc250Prompt

    return c.finish()


def render_splash(title, prompt, logo=True):
    sl = SPLASH_LAYOUT
    c = Canvas()
    bios = "PHOSPHOR BIOS v2.50"
    c.label(14, 14, bios, MID)
    if 14 + (len(bios) + 2 + len(title)) * CH[S] <= W - 14:  # the title only when it fits beside it
        c.label(W - 14, 14, title, DIM, anchor="rs")
    c.dotted_hline(6, W - 6, 20)

    # Logo: the pixel font at 6x, with a strong bloom (splash_nologo.png leaves it out for the 3D animation)
    if logo:
        size = logo_size(LOGO)
        c.label(W // 2, logo_baseline(size), LOGO, BRIGHT, anchor="ms", size=size)
        c.g.text((W // 2, logo_baseline(size)), LOGO, font=font(size), fill=BRIGHT, anchor="ms")
    c.label(W // 2, sl["sub_bl"], spaced(SUBTITLE), AMBER, anchor="ms")
    c.dotted_hline(6, W - 6, sl["sep_y"])

    c.dotted_hline(6, W - 6, sl["progress_bl"] - 18)
    c.label(14, sl["progress_bl"], "LOADING BC250-PHOSPHOR", MID)
    x, y, w, h = sl["bar"]
    c.d.rectangle((x - 2, y - 2, x + w + 1, y + h + 1), outline=DIM)

    for fx, fy, side, what in sl["footer"]:
        c.label(fx, fy, "Press DEL to enter SETUP" if what == "press" else prompt, DIM,
                anchor="rs" if side == "right" else "ls")
    return c.finish()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the BC250-Phosphor theme")
    parser.add_argument("--portrait", action="store_true", help="portrait 320x480 layout (default: landscape)")
    parser.add_argument("--user", default=PROMPT_USER, help="user shown in the prompt (default: %(default)s)")
    parser.add_argument("--host", default=PROMPT_HOST, help="host shown in the prompt (default: %(default)s)")
    parser.add_argument("--title", default=TITLE, help='header text (default: "<LOGO>::<USER>")')
    parser.add_argument("--logo", default=LOGO, help="big title of the boot splash (default: %(default)s)")
    parser.add_argument("--subtitle", default=SUBTITLE, help="line under it (default: %(default)s)")
    parser.add_argument("--cold", type=int, default=TEMP_COLD, help="fully green at/below this °C (default: %(default)s)")
    parser.add_argument("--hot", type=int, default=TEMP_HOT, help="fully orange at/above this °C (default: %(default)s)")
    parser.add_argument("--alert", type=int, default=TEMP_ALERT,
                        help="red + flashing HOT! from this °C (default: %(default)s)")
    parser.add_argument("--pwr-low", type=int, default=POWER_LOW,
                        help="APU power fully green at/below this W (default: %(default)s)")
    parser.add_argument("--pwr-high", type=int, default=POWER_HIGH,
                        help="APU power fully red at/above this W (default: %(default)s)")
    parser.add_argument("--dim-after", type=int, default=DIM_AFTER,
                        help="minutes without game/download before dimming, 0 = never (default: %(default)s)")
    parser.add_argument("--dim-brightness", type=int, default=DIM_BRIGHTNESS,
                        help="brightness %% when dimmed (default: %(default)s)")
    parser.add_argument("--night", default=NIGHT,
                        help='hours when the screen sleeps unless a game runs, e.g. "23:30-08:00" (default: off)')
    parser.add_argument("--no-splash", action="store_true", help="skip the BIOS-style boot screen")
    parser.add_argument("--night-mode", choices=("off", "dim"), default=NIGHT_MODE,
                        help="turn the screen off or just dim it at night (default: %(default)s)")
    args = parser.parse_args()
    set_layout(args.portrait)
    TEMP_COLD, TEMP_HOT, TEMP_ALERT = args.cold, args.hot, args.alert
    SPLASH = not args.no_splash
    # control characters would make theme.yaml unloadable
    printable = lambda text: "".join(ch for ch in (text or "") if ch.isprintable()).strip()
    args.user, args.host = printable(args.user) or PROMPT_USER, printable(args.host) or PROMPT_HOST
    args.title = printable(args.title) or None
    LOGO, SUBTITLE = printable(args.logo), printable(args.subtitle)
    if not LOGO:
        parser.error("--logo cannot be empty")
    max_w = SPLASH_LAYOUT["logo_max_w"]
    if len(LOGO) * logo_size(LOGO) // 2 > max_w:
        cut = LOGO[:max_w // 12]
        LOGO = cut.rsplit(" ", 1)[0] if " " in cut.strip() else cut  # at a word boundary when possible
        print(f"note: --logo shortened to '{LOGO}' to fit the splash")
    if len(spaced(SUBTITLE)) > (W - 12) // CH[S]:
        SUBTITLE = SUBTITLE[:(W - 12) // CH[S] // 2]
        print(f"note: --subtitle shortened to '{SUBTITLE}' to fit the splash")
    POWER_LOW, POWER_HIGH = args.pwr_low, args.pwr_high
    DIM_AFTER, DIM_BRIGHTNESS, NIGHT, NIGHT_MODE = args.dim_after, args.dim_brightness, args.night, args.night_mode

    title = (args.title or f"{LOGO}::{args.user.upper()}")[:28]
    prompt = f"{args.user}@{args.host}:~$"[:40]

    render_background(title, prompt).save(THEME_DIR / "background.png")
    render_splash(title, prompt).save(THEME_DIR / "splash.png")
    render_splash(title, prompt, logo=False).save(THEME_DIR / "splash_nologo.png")
    header = ("# BC250-Phosphor - retro P1 phosphor terminal for an AMD BC-250 Steam Machine\n"
              f"# Turing 3.5\" {'portrait' if PORTRAIT else 'landscape'}. GENERATED by make_theme.py: "
              "edit the script or its options and re-run it.\n"
              "# Needs library/sensors/sensors_bc250.py (GPU via amdgpu sysfs, no pyamdgpuinfo needed).\n---\n")
    (THEME_DIR / "theme.yaml").write_text(header + to_yaml(build_theme(title, prompt)) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote background.png and theme.yaml: {'portrait' if PORTRAIT else 'landscape'}, title '{title}', "
          f"prompt '{prompt}', logo '{LOGO}' / '{SUBTITLE}', temps {TEMP_COLD}/{TEMP_HOT}/{TEMP_ALERT}°C, "
          f"power {POWER_LOW}-{POWER_HIGH}W, dim after {DIM_AFTER} min, night '{NIGHT or 'off'}'")
