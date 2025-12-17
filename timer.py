#!/usr/bin/env python3
"""
Terminal Rubik's Cube timer (scramble feature removed).

Features:
 - Space: start / stop (when stopping, append the solve to `solves.json`)
 - i: 15s inspection (press Space during inspection to start early)
 - r: reset in-memory solves
 - s: save solves to CSV (export)
 - a: stats (best/worst/mean/Ao5)
 - q: quit

Behavior:
 - Every completed solve is appended to `solves.json` stored next to this script.
 - The main UI shows a live clock and elapsed time on a single status line.
"""

from __future__ import annotations, print_function

import csv
import json
import os
import sys
import time
from statistics import mean
from typing import List, Optional

try:
    from colorama import Fore, Style
    from colorama import init as colorama_init

    colorama_init(autoreset=True)
    COLOR_AVAILABLE = True
except Exception:
    # colorama not available -> fall back to no-color
    COLOR_AVAILABLE = False

# Color helpers (safe without colorama)
if COLOR_AVAILABLE:
    C = Fore.LIGHTCYAN_EX
    ERR = Fore.LIGHTRED_EX
    Y = Fore.LIGHTYELLOW_EX
    B = Fore.LIGHTBLUE_EX
    RESET = Fore.RESET
    GREEN = Fore.LIGHTGREEN_EX
    MAGENTA = Fore.LIGHTMAGENTA_EX
else:
    C = ERR = Y = B = RESET = ""


def colored(text: str, color: str) -> str:
    return f"{color}{text}{RESET}" if COLOR_AVAILABLE else text


def colored_output(text: str, typ: str = "info") -> None:
    """Small consistent output helper."""
    symbol = ""
    if typ == "info":
        symbol = f"{C}[*]{RESET}"
    elif typ == "input":
        symbol = f"{Y}[+]{RESET}"
    elif typ == "error":
        symbol = f"{ERR}[!]{RESET}"
    elif typ == "title":
        symbol = f"{C}[*]{RESET}"
        print(f"{symbol} {C}{text}{RESET}")
        return
    elif typ == "command":
        # expects text like "k = desc"
        parts = text.split(" = ", 1)
        left = parts[0] if parts else text
        right = parts[1] if len(parts) > 1 else ""
        print(f"{Y}[{left}]{RESET} {right}")
        return

    print(f"{symbol} {text}")


# Cross-platform single-key reader with timeout
if os.name == "nt":
    import msvcrt

    def getkey(timeout: Optional[float] = None) -> Optional[str]:
        """Return a single character string or None on timeout."""
        start = time.time()
        while True:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                # handle special two-byte sequences
                if ch in (b"\x00", b"\xe0"):
                    # consume next and ignore (arrow keys, etc.)
                    _ = msvcrt.getch()
                    continue
                try:
                    return ch.decode("utf-8", errors="ignore")
                except Exception:
                    return ""
            if timeout is not None and (time.time() - start) >= timeout:
                return None
            time.sleep(0.01)

else:
    import select
    import termios
    import tty

    def getkey(timeout: Optional[float] = None) -> Optional[str]:
        """Return a single character string or None on timeout (Unix)."""
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            if timeout is None:
                rlist, _, _ = select.select([fd], [], [])
            else:
                rlist, _, _ = select.select([fd], [], [], timeout)
            if rlist:
                ch = sys.stdin.read(1)
                return ch
            return None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


# Utilities
def format_time(t: float) -> str:
    minutes = int(t // 60)
    seconds = t % 60
    if minutes:
        return f"{minutes}:{seconds:06.3f}"
    else:
        return f"{seconds:06.3f}"


def ao5():
    if os.path.exists("solves.json"):
        with open("solves.json", "r") as solves_json:
            solves = json.load(solves_json)

        last5 = solves[-5:]

        mean_value = 0.0

        for solve in last5:
            mean_value += float(solve["seconds"])

        mean_value = mean_value / 5

        return mean_value


def print_stats(times: List[float]) -> None:
    if not os.path.exists("solves.json"):
        colored_output("No solves yet.", "info")
        return

    else:
        times = []

        with open("solves.json", "r") as solves_json:
            solves = json.load(solves_json)

        for solve in solves:
            times.append(solve["seconds"])

    best = min(times)
    worst = max(times)
    avg_all = mean(times)
    ao5_val = ao5()

    # colored_output(
    #    f"Solves: {len(times)} | Best: {format_time(best)} | Worst: {format_time(worst)} | Mean(all): {format_time(avg_all)}",
    #    "info",
    # )

    colored_output(f"Solves:       {'{:>8}'.format(len(times))}", "info")
    colored_output(
        f"{GREEN}Best:{RESET}         {'{:>8}'.format(format_time(best))}", "info"
    )
    colored_output(
        f"{ERR}Worst:{RESET}        {'{:>8}'.format(format_time(worst))}", "info"
    )
    colored_output(f"Mean (all):   {'{:>8}'.format(format_time(avg_all))}", "info")

    if ao5_val is not None:
        colored_output(f"Ao5 (last 5): {'{:>8}'.format(format_time(ao5_val))}", "info")
    else:
        colored_output("Ao5: need at least 5 solves.", "info")

    # print("")


# JSON append helper
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
SOLVES_JSON = os.path.join(SCRIPT_DIR, "solves.json")


def append_solve_json(
    seconds: float, formatted: str, filename: str = SOLVES_JSON
) -> None:
    """
    Append a solve record to a JSON array stored in `filename`.

    A record:
      {"timestamp": "2025-11-29T12:34:56Z", "seconds": 12.345678, "formatted": "12.345"}

    If the file doesn't exist it will be created. If it contains invalid JSON, it's overwritten.
    """
    record = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seconds": seconds,
        "formatted": formatted,
    }

    solves: List[dict] = []
    try:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    solves = data
                else:
                    # unexpected content -> start fresh
                    solves = []
    except Exception:
        # on any read/parse error, start fresh
        solves = []

    solves.append(record)

    # write atomically
    tmp = filename + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(solves, f, indent=2, ensure_ascii=False)
        os.replace(tmp, filename)
    except Exception as e:
        # final fallback: try direct write
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(solves, f, indent=2, ensure_ascii=False)
        except Exception:
            colored_output(f"Failed to save solve to JSON: {e}", "error")


# Status line helpers
def shutil_terminal_width() -> Optional[int]:
    try:
        import shutil

        return shutil.get_terminal_size().columns
    except Exception:
        return None


def clear_status_line() -> None:
    width = shutil_terminal_width() or 120
    sys.stdout.write("\r" + " " * width + "\r")
    sys.stdout.flush()


def write_status_line(running: bool, elapsed_display: str, extra: str = "") -> None:
    if running:
        status_seg = colored("RUNNING", ERR)
    else:
        status_seg = colored("READY  ", C)
    elapsed_seg = colored(elapsed_display, RESET)
    line = f"{C}[*]{RESET} {status_seg} | {elapsed_seg} {extra}"
    width = shutil_terminal_width() or 120
    sys.stdout.write("\r" + " " * width + "\r")
    sys.stdout.write(line)
    sys.stdout.flush()


def list_solves():
    if os.path.exists("solves.json"):
        with open("solves.json", "r") as solves_json:
            solves = json.load(solves_json)

        worst = max(solve["seconds"] for solve in solves)
        best = min(solve["seconds"] for solve in solves)

        print("")
        print("")

        for index, solve in enumerate(solves, 1):
            color = RESET

            if worst == solve["seconds"]:
                color = ERR

            if best == solve["seconds"]:
                color = GREEN

            line = f"{C}{'{:03d}'.format(index)}{RESET} {Style.DIM}{solve['timestamp']}{Style.RESET_ALL} {color}{'{:>8}'.format(solve['formatted'])}{RESET}"

            colored_output(line, "info")

        print("")

    else:
        print("")
        print("")

        colored_output("No solves.json file found!", "error")

        print("")


def help():
    print("")
    print("")
    colored_output("  = start", "command")
    colored_output("i = inspection (15s)", "command")
    colored_output("r = reset", "command")
    colored_output("s = save", "command")
    colored_output("a = stats", "command")
    colored_output("q = quit", "command")
    colored_output("l = list", "command")
    print("")


# Main loop
def main() -> None:
    os.system("clear")

    times: List[float] = []
    running = False
    start_time: Optional[float] = None
    last_elapsed = 0.0

    colored_output("Simple Rubik's Cube Timer", "title")
    colored_output("-------------------------", "title")
    print("")
    # colored_output("Press Space to start...", "input")
    # print("")

    try:
        while True:
            if running and start_time is not None:
                elapsed = time.time() - start_time
                elapsed_display = format_time(elapsed)
            else:
                elapsed_display = (
                    format_time(last_elapsed) if last_elapsed else "00.000"
                )

            write_status_line(running, elapsed_display)

            key = getkey(timeout=0.12)
            if key is None:
                continue

            # Normalize keys
            if key == " ":
                if not running:
                    # start timer
                    running = True
                    start_time = time.time()
                    write_status_line(running, "00.000")
                else:
                    # stop timer
                    elapsed = (
                        time.time() - start_time if start_time is not None else 0.0
                    )
                    running = False
                    start_time = None
                    last_elapsed = elapsed
                    times.append(elapsed)

                    # Append this solve to the JSON file immediately
                    append_solve_json(elapsed, format_time(elapsed))

                    clear_status_line()
                    colored_output(f"Stopped > {format_time(elapsed)}", "info")

                    print("")

                    print_stats(times)

                    # colored_output("Press Space to start...", "input")

                    print("")

            elif key in ("i", "I"):
                # Inspection: 15s countdown, auto-start after (or Space to start early)
                inspect_start = time.time()
                remaining = 15.0
                started_early = False
                while remaining > 0:
                    remaining = 15.0 - (time.time() - inspect_start)
                    if remaining < 0:
                        remaining = 0.0
                    extra = colored(f"[{remaining:04.2f}s]", Y)
                    write_status_line(False, "00.000", extra=extra)
                    k = getkey(timeout=0.12)
                    if k == " ":
                        started_early = True
                        break

                clear_status_line()
                if started_early:
                    running = True
                    start_time = time.time()
                    write_status_line(running, "00.000")
                    continue

                running = True
                start_time = time.time()
                write_status_line(running, "00.000")

            elif key in ("r", "R"):
                times = []
                last_elapsed = 0.0
                clear_status_line()
                colored_output("All in-memory solves cleared.", "info")
                print("")
                # colored_output("Press Space to start...", "input")

            elif key in ("s", "S"):
                # Export to CSV (snapshot of current in-memory solves)
                fname = os.path.join(SCRIPT_DIR, f"solves_{int(time.time())}.csv")
                try:
                    with open(fname, "w", newline="", encoding="utf-8") as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(["index", "seconds", "formatted"])
                        for i, t in enumerate(times, 1):
                            writer.writerow([i, f"{t:.6f}", format_time(t)])
                    clear_status_line()
                    colored_output(f"Saved {len(times)} solves to {fname}", "info")
                except Exception as e:
                    clear_status_line()
                    colored_output(f"Failed to save: {e}", "error")

            elif key in ("a", "A"):
                clear_status_line()
                print_stats(times)

            elif key in ("q", "Q", "\x03", "\x04"):
                clear_status_line()
                colored_output("Quitting.", "info")
                break

            elif key in ("l", "L"):
                list_solves()

            elif key in ("h", "H"):
                help()

            else:
                # ignore other keys
                continue

    except KeyboardInterrupt:
        clear_status_line()
        colored_output("\nInterrupted; exiting.", "error")


if __name__ == "__main__":
    main()
