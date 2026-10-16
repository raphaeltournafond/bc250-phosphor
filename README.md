# BC250 themes: Phosphor and Game Boy

Two themes for [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python), made for a **3.5" Turing screen** (landscape or portrait) on an **AMD BC-250 Steam Machine running Bazzite**. Both show the same live data; pick one with `--theme`.

**Phosphor** (default): a retro green-phosphor terminal, with a CRT warm-up and a 3D logo at boot.

![phosphor landscape](res/themes/BC250-Phosphor/preview.png) ![phosphor portrait](res/themes/BC250-Phosphor/preview_portrait.png)

**Game Boy** (`--theme gameboy`): the 4-shade DMG screen as a handheld-RPG status screen. CPU and GPU are party cards with HP bars, there's an ITEMS box, and a dialog box at the bottom ("RAFALE IS PLAYING"). At boot your logo drops in, then a SYSTEM CHECK menu runs.

![game boy landscape](res/themes/BC250-GameBoy/preview.png) ![game boy portrait](res/themes/BC250-GameBoy/preview_portrait.png)

*Game Boy-inspired fan theme, not affiliated with or endorsed by Nintendo; it uses no Nintendo logos.*

## Quick start

1. **Get the theme** in the folder that holds your `turing-smart-screen-python` folder (or in your home, if the app is at `~/turing-smart-screen-python…`):
   ```bash
   git clone https://github.com/raphaeltournafond/bc250-phosphor
   ```
   Don't have the app yet? Get it into your home folder first:
   ```bash
   git clone --depth 1 --branch 3.10.0 https://github.com/mathoudebine/turing-smart-screen-python ~/turing-smart-screen-python
   ```
2. **Run the setup** (plug the screen in first):
   ```bash
   bash bc250-phosphor/setup.sh
   ```
3. **For FPS in games**, paste this into each game's *Properties > Launch Options* in Steam:
   ```
   MANGOHUD_CONFIG=fps_only,alpha=0,autostart_log=1,log_interval=1000,output_folder=~/mangologs mangohud %command%
   ```

That's it: the screen now starts with the boot animation every time the BC-250 boots.

| To… | Run |
|---|---|
| update the theme | `git -C bc250-phosphor pull && bash bc250-phosphor/setup.sh` |
| switch to the Game Boy theme | `bash bc250-phosphor/setup.sh --theme gameboy` |
| change an option | `bash bc250-phosphor/setup.sh --night 23:30-08:00 --logo "MY RIG"` (remembered for next time) |
| go back to the defaults | `bash bc250-phosphor/setup.sh --reset-options` |
| remove it | `bash bc250-phosphor/setup.sh --uninstall` |

### What setup does

- **Finds the app:** it uses `--app PATH` if given, then the folder from last time, then a `turing-smart-screen-python*` folder next to this one or in your home.
- **Python libraries:** uses the Python that already has the app's libraries. If none does, it installs them into a private `.venv` inside the app folder (nothing system-wide).
- **Screen access:** checks your account can talk to the screen, and offers the fix if not (including the Bazzite/Fedora Atomic `dialout` group quirk).
- **Theme:** installs it and builds the artwork with your username, hostname and options. It also sets `THEME` and the network interface in the app's `config.yaml`.
- **Start at boot:** runs the monitor as a systemd user service, and restarts it after an update.
- **Health check:** finishes with `bc250_check.py`, which reports every data source and how to fix anything missing.

## Options

| Option | Default | Effect |
|---|---|---|
| `--theme NAME` | `phosphor` | `phosphor` (green terminal) or `gameboy` (4-shade RPG status screen) |
| `--portrait` | landscape | portrait layout (320×480): panels stacked, 2×3 grid |
| `--logo TEXT` / `--subtitle TEXT` | `BC-250` / `STEAM MACHINE` | boot splash title and the line under it |
| `--user NAME` / `--host NAME` | your login / hostname | the `user@host:~$` prompt |
| `--title TEXT` | `<LOGO>::<USER>` | header text |
| `--cold C` / `--hot C` / `--alert C` | `40` / `70` / `80` | temperature colours (shades on the Game Boy); flashing `HOT!` from the alert value |
| `--pwr-low W` / `--pwr-high W` | `100` / `200` | APU power colour scale |
| `--dim-after M` / `--dim-brightness P` | `10` / `5` | dim after M minutes without game or download (`0` = never), to P % |
| `--night HH:MM-HH:MM` / `--night-mode off\|dim` | off / `off` | screen sleeps (or dims) at night unless a game runs |
| `--no-splash` | | skip the boot animation |
| `--app PATH` / `--no-autostart` | | where the app is / don't start at boot |

## What's on screen

![phosphor boot](res/themes/BC250-Phosphor/splash_preview.gif) ![game boy boot](res/themes/BC250-GameBoy/splash_preview.gif)

- **Boot** (about 7 s): a self-test of real values (CPU, memory, GPU, temperatures, Steam library, network, Steam client).
  - **Phosphor:** a CRT warm-up, then the "Phosphor BIOS" with a 3D logo.
  - **Game Boy:** your logo drops in, then a SYSTEM CHECK menu with a ▶ cursor and an HP-style loading bar.
- **CPU / GPU panels:** load %, temperature, clock and a 60 s temperature chart. On Phosphor, colours go green → orange (70 °C) → red (80 °C). The Game Boy has only 4 shades, so it darkens instead. On both, `HOT!` flashes from 80 °C.
- **System grid:** RAM, games SSD (% used and free space), APU power (green → red, 100 → 200 W), GPU memory, download/upload speed and ping.
- **Bottom line** (the Game Boy's dialog box, in RPG wording such as "IS PLAYING" or "IS RESTING"): what the machine is doing:
  - **now-playing:** game, FPS and session time;
  - **downloading** / **installing** / **verifying:** a Steam download with its progress bar and ETA;
  - **fossilize_replay:** shader pre-caching, with `STALL` if it gets stuck;
  - **last-session:** the last game, how long it ran, and its peak CPU/GPU temperatures.
- **Screen power:** dims after 10 min idle, optional night sleep; a running game always keeps it on.

## Troubleshooting

| Problem | Fix |
|---|---|
| Something shows `--` | run `cd <app folder> && python3 bc250_check.py`: it says what's missing and how to fix it |
| No FPS | the launch option above is missing from that game. Don't use `no_display` in it: that stops MangoHud logging |
| Screen stuck on "Please visit www.turzx.com" | `journalctl --user -u turing-monitor -n 50` shows why the monitor isn't running |
| Screen briefly shows the TURZX message again before the boot animation | set `RESET_ON_STARTUP: false` in the app's `config.yaml` |
| GPU load shows `--%` | the monitor must run as the same user as Steam; setup's service does |

## How it works

| File | Role |
|---|---|
| `setup.sh` | the one command: finds the app, Python, screen access, then runs the two scripts below and the check |
| `install_bc250.sh` | copies the themes and sensors into the app, builds the chosen theme with your options and selects it |
| `install_autostart.sh` | the systemd user service (also `--remove`) |
| `bc250_check.py` | read-only health check of every data source |
| `library/sensors/sensors_bc250.py` | the data the app can't read on a BC-250, plus the self-drawn widgets and both boot animations |
| `make_theme.py` | generates a theme's `theme.yaml` and artwork: colours in `SKINS`, every position in `set_layout()` (one block per theme and orientation), the artwork in `render_*()` |
| `res/themes/BC250-*` | each theme's default files and previews |

Why the custom sensors:
- **GPU:** the BC-250 has no `gpu_busy_percent`, and the app's AMD library has no builds for Python above 3.12. Load comes from the kernel's per-process GPU counters (as in `nvtop`); clock, temperature, power and memory come from amdgpu sysfs.
- **Games SSD:** on Bazzite `/` is a read-only image that always reads 100% full, so the drive holding your Steam library is measured instead (override with `BC250_DISK_PATH`).
- **Steam:** state is read from Steam's own files:
  - **games:** only Steam's game launcher counts; install scripts and redistributables don't;
  - **downloads:** `logs/content_log.txt` plus appmanifest counters, smoothed by network traffic;
  - **shader pre-caching:** `logs/shader_log.txt`.

  Valve doesn't document these log formats, so a Steam update could change them. If that happens the line just stops showing; nothing crashes.
- **Old app versions:** every live text has a fixed-size box, so values that get shorter leave nothing behind, even on app versions older than its July 2026 anti-ghosting fix.
