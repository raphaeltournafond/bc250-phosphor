# BC250-Phosphor theme generator: renders background.png and writes theme.yaml from a single layout,
# so static art and live widgets always line up. Edit the settings below (or pass them as options), then run:
#     python3 res/themes/BC250-Phosphor/make_theme.py --help
# Turing 3.5" (rev A/B/...) in landscape: 480x320.
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

W, H = 480, 320

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

# Header
HEADER_H = 16
HEADER_BL = 12

# CPU / GPU panels
PANEL_TOP, PANEL_BOTTOM = 26, 162
CPU_X, GPU_X, PANEL_W = 4, 243, 233
PAD = 10
LABEL_BL = 44  # small labels above values
VALUE_BL = 66  # big number and side values share this baseline
BAR_Y, BAR_H = 74, 8
GRAPH_Y, GRAPH_H = 92, 62

# System grid: 3 columns x 2 rows of cells
GRID = (4, 170, 476, 274)
CELL_W, CELL_GAP = 142, 13
GRID_COLS = [GRID[0] + PAD + i * (CELL_W + CELL_GAP) for i in range(3)]
GRID_ROWS = [178, 226]
CELL_LABEL_BL, CELL_VALUE_BL = 10, 32  # relative to row top
CELL_BAR_Y, CELL_BAR_H = 37, 6
CELL_SPARK_Y, CELL_SPARK_H = 37, 9

# Boot splash (splash.png): static art here, POST lines and progress drawn live by sensors_bc250
SPLASH_LOGO_BL, SPLASH_SUB_BL, SPLASH_SEP_Y = 84, 104, 114
SPLASH_ROW_BL, SPLASH_ROW_STEP, SPLASH_ROWS = 132, 15, 7
SPLASH_PROGRESS_BL, SPLASH_FOOTER_BL = 254, 312
SPLASH_BAR = (214, 246, 466 - 214, 8)  # x, y, w, h of the loading bar
SPLASH_LOGO_BOX = (96, 21, 288, 75)  # area redrawn by the 3D logo animation (clear of header and subtitle)
SPLASH_LOGO_CENTER_Y = 60  # the logo is centred here whatever its size
SPLASH_LOGO_MAX_W = 256  # leaves room in the box for the 3D sway and perspective


def logo_size(text):
    """Largest crisp size (a multiple of the pixel font's 12 px) at which the logo fits its box."""
    for size in (72, 60, 48, 36, 24):
        if len(text) * size // 2 <= SPLASH_LOGO_MAX_W:
            return size
    return 24


def logo_baseline(size):
    return SPLASH_LOGO_CENTER_Y + size * 8 // 12 // 2  # cap height is 8/12 of the size


def spaced(text):
    """S T E A M   M A C H I N E"""
    return "   ".join(" ".join(word) for word in text.split())

# Now playing prompt
PROMPT_Y = 278
PROMPT_LABEL_BL, PROMPT_VALUE_BL = 290, 314
PROMPT_X, PROMPT_XR = 14, 466
PROMPT_AREA = (6, PROMPT_Y + 2, W - 12, H - PROMPT_Y - 2)  # redrawn as a whole by Bc250Prompt
PROMPT_COL1_XR = 380  # right edge of the first right-hand column (FPS / DONE / TIME)


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


def heat_widget(temp_x, graph, panel_x):
    """Temperature drawn by sensors_bc250: value and history coloured green -> orange -> red, flashing from ALERT."""
    return {
        "COLD": TEMP_COLD, "HOT": TEMP_HOT, "ALERT": TEMP_ALERT,
        "COLD_COLOR": rgb(BRIGHT), "HOT_COLOR": rgb(HOT), "ALERT_COLOR": rgb(ALERT), "INK": rgb(INK),
        "HEAT_TEXT": text(temp_x, VALUE_BL, M, 5),
        "ALERT_TAG": {"X": panel_x + 8, "Y": PANEL_TOP - 6, "WIDTH": 32, "HEIGHT": 13, "FONT": FONT, "FONT_SIZE": S,
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


# ---------------------------------------------------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------------------------------------------------
def panel(px):
    x0, xr = px + PAD, px + PANEL_W - PAD
    return {
        "x0": x0,
        "xr": xr,  # right edge shared by bar, graph and right column
        "col_a": x0 + 100,  # left-anchored middle column
        "bar": (x0, BAR_Y, xr - x0, BAR_H),
        "graph": (x0, GRAPH_Y, xr - x0, GRAPH_H),
    }


cpu, gpu = panel(CPU_X), panel(GPU_X)


def cell(col, row):
    x0, y0 = GRID_COLS[col], GRID_ROWS[row]
    return {"x0": x0, "xr": x0 + CELL_W, "y0": y0,
            "label_bl": y0 + CELL_LABEL_BL, "value_bl": y0 + CELL_VALUE_BL,
            "bar": (x0, y0 + CELL_BAR_Y, CELL_W, CELL_BAR_H),
            "spark": (x0, y0 + CELL_SPARK_Y, CELL_W, CELL_SPARK_H)}


ram, ssd, pwr = cell(0, 0), cell(1, 0), cell(2, 0)
rx, tx, ping = cell(0, 1), cell(1, 1), cell(2, 1)

CLOCK_XR = W - 6
DATE_XR = CLOCK_XR - 8 * CH[S] - 12  # "HH:mm:ss" is 8 chars


def header_layout(title):
    up_x = 6 + len(title) * CH[S] + 12
    return up_x, up_x + 3 * CH[S]


def build_theme(title, prompt):
    _, uptime_x = header_layout(title)
    net_spark = dict(max_value=10_000_000_000, autoscale=True)
    return {
        "author": "BC-250 Steam Machine",
        # read by sensors_bc250 (not by the app itself): the boot sequence played before the dashboard
        "bc250_splash": {
            "ENABLED": SPLASH, "IMAGE": "splash.png", "FONT": FONT, "ALERT": TEMP_ALERT,
            "BRIGHT": rgb(BRIGHT), "MID": rgb(MID), "DIM": rgb(DIM), "AMBER": rgb(AMBER), "ALERT_COLOR": rgb(ALERT),
            "BG": rgb(BG), "ROW_BL": SPLASH_ROW_BL, "ROW_STEP": SPLASH_ROW_STEP, "ROWS": SPLASH_ROWS,
            "LABEL_X": 14, "VALUE_X": 86, "STATUS_XR": 466,
            "PROGRESS_BL": SPLASH_PROGRESS_BL, "STATUS_BL": 284, "BAR_X": SPLASH_BAR[0], "BAR_Y": SPLASH_BAR[1],
            "BAR_W": SPLASH_BAR[2], "BAR_H": SPLASH_BAR[3],
            "IMAGE_NOLOGO": "splash_nologo.png", "LOGO_TEXT": LOGO, "LOGO_SIZE": logo_size(LOGO),
            "LOGO_BL": logo_baseline(logo_size(LOGO)), "LOGO_BOX": list(SPLASH_LOGO_BOX),
        },
        "display": {"DISPLAY_SIZE": '3.5"', "DISPLAY_ORIENTATION": "landscape", "DISPLAY_RGB_LED": rgb(MID)},
        "static_images": {"BACKGROUND": {"PATH": "background.png", "X": 0, "Y": 0, "WIDTH": W, "HEIGHT": H}},
        "STATS": {
            "CPU": {
                "PERCENTAGE": {
                    "INTERVAL": 1,
                    "TEXT": text(cpu["x0"], VALUE_BL, L, 4),
                    "GRAPH": bar(*cpu["bar"]),
                },
                "FREQUENCY": {"INTERVAL": 2, "TEXT": text(cpu["xr"], VALUE_BL, M, 4, unit=False, right=True)},
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
            "DATE": {
                "INTERVAL": 1,
                "DAY": {"TEXT": text(DATE_XR, HEADER_BL, S, 14, INK, right=True, FORMAT="EEE dd MMM")},
                "HOUR": {"TEXT": text(CLOCK_XR, HEADER_BL, S, 8, INK, right=True, FORMAT="HH:mm:ss")},
            },
            "UPTIME": {"INTERVAL": 1, "FORMATTED": {"TEXT": text(uptime_x, HEADER_BL, S, 20, INK)}},
            "CUSTOM": {
                "INTERVAL": 1,
                "Bc250CpuTemp": heat_widget(cpu["col_a"], cpu["graph"], CPU_X),
                "Bc250GpuLoad": {"TEXT": text(gpu["x0"], VALUE_BL, L, 4), "GRAPH": bar(*gpu["bar"])},
                "Bc250GpuTemp": heat_widget(gpu["col_a"], gpu["graph"], GPU_X),
                "Bc250GpuClock": {"TEXT": text(gpu["xr"], VALUE_BL, M, 4, right=True)},
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
                "Bc250Prompt": {
                    "AREA": {"X": PROMPT_AREA[0], "Y": PROMPT_AREA[1], "WIDTH": PROMPT_AREA[2],
                             "HEIGHT": PROMPT_AREA[3], "BACKGROUND_IMAGE": "background.png"},
                    "FONT": FONT, "BRIGHT": rgb(BRIGHT), "MID": rgb(MID), "DIM": rgb(DIM), "AMBER": rgb(AMBER),
                    "LABEL_BL": PROMPT_LABEL_BL, "VALUE_BL": PROMPT_VALUE_BL,
                    "CMD_X": PROMPT_X + (len(prompt) + 1) * CH[S], "TEXT_X": PROMPT_X,
                    "COL1_XR": PROMPT_COL1_XR, "COL2_XR": PROMPT_XR,
                    "MAX_CHARS": (PROMPT_COL1_XR - 4 * CH[M] - 12 - PROMPT_X) // CH[M] - 1,
                    "MAX_CHARS_WIDE": (PROMPT_XR - 5 * CH[M] - 12 - PROMPT_X) // CH[M] - 1,
                },
                "Bc250Screen": {"SCREEN": {"DIM_AFTER": DIM_AFTER, "DIM_BRIGHTNESS": DIM_BRIGHTNESS,
                                           "NIGHT": NIGHT, "NIGHT_MODE": NIGHT_MODE}},
            },
        },
    }


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
    up_x, _ = header_layout(title)

    # Header band (inverse video)
    c.d.rectangle((0, 0, W, HEADER_H), fill=MID)
    c.g.rectangle((0, 0, W, HEADER_H), fill=DIM)
    c.label(6, HEADER_BL, title, INK, glow=False)
    c.label(up_x, HEADER_BL, "UP", (14, 70, 34), glow=False)

    # CPU / GPU panels: same columns in both, LOAD % | TEMP | CLK
    for px, name, subtitle, p, clk in ((CPU_X, "CPU", "ZEN2 6C/12T", cpu, "CLK GHZ"),
                                       (GPU_X, "GPU", "RDNA2 24CU", gpu, "CLK MHZ")):
        c.frame((px, PANEL_TOP, px + PANEL_W, PANEL_BOTTOM), name, subtitle)
        c.label(p["col_a"], LABEL_BL, "TEMP")
        c.label(p["xr"], LABEL_BL, clk, anchor="rs")
        c.bar_track(*p["bar"])
        c.graph_grid(*p["graph"])
        c.label(p["xr"] - 2, GRAPH_Y + 10, "°C 60s", DIM, anchor="rs")

    # System grid
    c.frame(GRID, "SYS", "MEM / STORAGE / NET")
    cells = [
        (ram, "RAM", "USED", "bar"), (ssd, "GAMES SSD", "FREE", "bar"), (pwr, "APU PWR", "GPU MEM", "bar"),
        (rx, "↓ DOWNLOAD", None, "spark"), (tx, "↑ UPLOAD", None, "spark"), (ping, "PING", None, "spark"),
    ]
    for cl, label, sublabel, kind in cells:
        c.label(cl["x0"], cl["label_bl"], label)
        if sublabel:
            c.label(cl["xr"], cl["label_bl"], sublabel, DIM, anchor="rs")
        if kind == "bar":
            c.bar_track(*cl["bar"], ticks=False)
        else:
            c.graph_grid(*cl["spark"])
    for col in (1, 2):
        c.dotted_vline(GRID_COLS[col] - (CELL_GAP + 1) // 2, GRID[1] + 8, GRID[3] - 4)

    # Now playing prompt
    c.dotted_hline(4, W - 4, PROMPT_Y)
    c.label(PROMPT_X, PROMPT_LABEL_BL, prompt)  # the command word and values are drawn live by Bc250Prompt

    return c.finish()


def render_splash(title, prompt, logo=True):
    c = Canvas()
    c.label(14, 14, "PHOSPHOR BIOS v2.50", MID)
    c.label(466, 14, title, DIM, anchor="rs")
    c.dotted_hline(6, W - 6, 20)

    # Logo: the pixel font at 6x, with a strong bloom (splash_nologo.png leaves it out for the 3D animation)
    if logo:
        size = logo_size(LOGO)
        c.label(W // 2, logo_baseline(size), LOGO, BRIGHT, anchor="ms", size=size)
        c.g.text((W // 2, logo_baseline(size)), LOGO, font=font(size), fill=BRIGHT, anchor="ms")
    c.label(W // 2, SPLASH_SUB_BL, spaced(SUBTITLE), AMBER, anchor="ms")
    c.dotted_hline(6, W - 6, SPLASH_SEP_Y)

    c.dotted_hline(6, W - 6, SPLASH_PROGRESS_BL - 18)
    c.label(14, SPLASH_PROGRESS_BL, "LOADING BC250-PHOSPHOR", MID)
    x, y, w, h = SPLASH_BAR
    c.d.rectangle((x - 2, y - 2, x + w + 1, y + h + 1), outline=DIM)

    c.label(14, SPLASH_FOOTER_BL, "Press DEL to enter SETUP", DIM)
    c.label(466, SPLASH_FOOTER_BL, prompt, DIM, anchor="rs")
    return c.finish()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the BC250-Phosphor theme")
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
    TEMP_COLD, TEMP_HOT, TEMP_ALERT = args.cold, args.hot, args.alert
    SPLASH = not args.no_splash
    # control characters would make theme.yaml unloadable
    printable = lambda text: "".join(ch for ch in (text or "") if ch.isprintable()).strip()
    args.user, args.host = printable(args.user) or PROMPT_USER, printable(args.host) or PROMPT_HOST
    args.title = printable(args.title) or None
    LOGO, SUBTITLE = printable(args.logo), printable(args.subtitle)
    if not LOGO:
        parser.error("--logo cannot be empty")
    if len(LOGO) * logo_size(LOGO) // 2 > SPLASH_LOGO_MAX_W:
        cut = LOGO[:SPLASH_LOGO_MAX_W // 12]
        LOGO = cut.rsplit(" ", 1)[0] if " " in cut.strip() else cut  # at a word boundary when possible
        print(f"note: --logo shortened to '{LOGO}' to fit the splash")
    if len(spaced(SUBTITLE)) > 76:
        SUBTITLE = SUBTITLE[:38]
        print(f"note: --subtitle shortened to '{SUBTITLE}' to fit the splash")
    POWER_LOW, POWER_HIGH = args.pwr_low, args.pwr_high
    DIM_AFTER, DIM_BRIGHTNESS, NIGHT, NIGHT_MODE = args.dim_after, args.dim_brightness, args.night, args.night_mode

    title = (args.title or f"{LOGO}::{args.user.upper()}")[:28]
    prompt = f"{args.user}@{args.host}:~$"[:40]

    render_background(title, prompt).save(THEME_DIR / "background.png")
    render_splash(title, prompt).save(THEME_DIR / "splash.png")
    render_splash(title, prompt, logo=False).save(THEME_DIR / "splash_nologo.png")
    header = ("# BC250-Phosphor - retro P1 phosphor terminal for an AMD BC-250 Steam Machine\n"
              "# Turing 3.5\" landscape. GENERATED by make_theme.py: edit the script or its options and re-run it.\n"
              "# Needs library/sensors/sensors_bc250.py (GPU via amdgpu sysfs, no pyamdgpuinfo needed).\n---\n")
    (THEME_DIR / "theme.yaml").write_text(header + to_yaml(build_theme(title, prompt)) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote background.png and theme.yaml: title '{title}', prompt '{prompt}', "
          f"logo '{LOGO}' / '{SUBTITLE}', temps {TEMP_COLD}/{TEMP_HOT}/{TEMP_ALERT}°C, power {POWER_LOW}-{POWER_HIGH}W, dim after {DIM_AFTER} min, night '{NIGHT or 'off'}'")
