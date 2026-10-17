"""The whole app with a theme, on an emulated 3.5" rev A (simulated display; bitmaps queued and paid for at 160 KB/s
and ~1.5 ms a command), on a fake BC-250 playing Hades II:
- after the boot and some dashboard time, the screen shows pixel for pixel what every widget meant to draw;
- the dashboard takes over from the boot without the app repainting the whole screen;
- radar: the sweep starts as the boot ends and never stalls.
Usage (from the app's folder): python check_app.py THEME [--portrait] [--seconds S] [--screenshot OUT] [-- options]"""
import argparse
import os
import runpy
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RevA, patch_sensors, report  # noqa: E402
from check_boot import BC250_LINES, select_theme  # noqa: E402
from common import THEMES  # noqa: E402

PAUSES_PER_MINUTE = 20


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("theme", choices=sorted(THEMES))
    parser.add_argument("--portrait", action="store_true")
    parser.add_argument("--seconds", type=float, default=24, help="how long to run (boot included)")
    parser.add_argument("--screenshot", help="also save the final screen (README previews)")
    argv = sys.argv[1:]  # what follows "--" goes to make_theme.py
    extra = argv[argv.index("--") + 1:] if "--" in argv else []
    args = parser.parse_args(argv[:argv.index("--")] if "--" in argv else argv)
    args.extra = extra
    select_theme(args.theme, args.portrait, args.extra)
    name = f"{args.theme} {'portrait' if args.portrait else 'landscape'}"

    rev_a = RevA()
    rev_a.install()
    import library.lcd.lcd_simulated as simulated  # the app's repaint loads the background from its file
    repaints = [0]
    from_file = simulated.LcdSimulated.DisplayBitmap

    def counted(self, *args, **kwargs):
        repaints[0] += 1
        return from_file(self, *args, **kwargs)
    simulated.LcdSimulated.DisplayBitmap = counted
    import library.sensors.sensors_bc250 as b
    patch_sensors(b)
    rev_a.watch_screen(b)
    real_lines = b._Splash.post_lines
    b._Splash.post_lines = staticmethod(lambda spec: [
        (label,) + BC250_LINES.get(label, (value, status)) for label, value, status in real_lines(spec)])

    def verdict():
        time.sleep(args.seconds)
        ok = True
        try:
            differ = rev_a.settled_difference()
            ok &= report(differ == 0, f"{name}: the screen shows what every widget meant to draw"
                         + (f" ({differ} pixels differ)" if differ else ""))
            ok &= report(repaints[0] == 0, f"{name}: the dashboard took over from the boot without the app's full "
                                           f"repaint ({repaints[0]} repaints)")
            boot = [t for t, x, y, w, h, who in rev_a.log if who == "MainThread"]
            sweep = [t for t, x, y, w, h, who in rev_a.log if who == "BC250 radar"]
            if b._Draw.theme("Bc250Radar"):
                handoff_gap = (sweep[0] - boot[-1]) if sweep and boot else float("inf")
                ok &= report(handoff_gap < 0.5, f"{name}: the sweep starts as the boot ends ({handoff_gap:.2f} s later)")
                starts = [t for i, t in enumerate(sweep) if i == 0 or t - sweep[i - 1] > 0.04]
                gaps = [later - earlier for earlier, later in zip(starts, starts[1:])]
                worst = max(gaps) if gaps else float("inf")
                seconds = max(1e-3, starts[-1] - starts[0])
                per_minute = 60 * sum(1 for gap in gaps if gap > 0.2) / seconds
                # a smooth sweep: no regular pauses (the old once-a-second stall was ~60 a minute) and no long one
                ok &= report(per_minute <= PAUSES_PER_MINUTE and worst < 0.6,
                             f"{name}: sweep {len(starts) / seconds:.1f} frames/s, {per_minute:.0f} pauses over 200 ms a "
                             f"minute (limit {PAUSES_PER_MINUTE}), longest {worst * 1000:.0f} ms")
            if args.screenshot:
                with rev_a.lock:
                    rev_a.screen.save(args.screenshot)
        except Exception as e:
            ok = report(False, f"{name}: {e!r}")
        sys.stdout.flush()
        os._exit(0 if ok else 1)

    threading.Thread(target=verdict, name="verdict", daemon=True).start()
    sys.argv = ["main.py"]
    runpy.run_path("main.py", run_name="__main__")


if __name__ == "__main__":
    main()
