"""
Screen Time Agent — polls the active window every 60 seconds,
batches samples, and POSTs them to the backend.
"""
import os, sys, time, logging, ctypes, threading
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("agent")

BACKEND     = "https://burnout-n9p9.onrender.com"
SAMPLE_SECS = int(os.getenv("SAMPLE_INTERVAL_SECONDS", 60))
FLUSH_MINS  = int(os.getenv("FLUSH_INTERVAL_MINUTES",   1))
IDLE_THRESH = int(os.getenv("IDLE_THRESHOLD_SECONDS",  30))


def keep_alive():
    """Ping backend every 10 minutes so Render never sleeps."""
    while True:
        try:
            requests.get(BACKEND, timeout=5)
            log.info("Keep-alive ping sent")
        except Exception:
            pass
        time.sleep(600)


def _win_active_window():
    try:
        import psutil
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf    = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            proc     = psutil.Process(pid.value)
            exe_name = proc.name()
            app      = exe_name.replace(".exe", "").replace(".app", "")
            if app.lower() in ("chrome", "msedge", "firefox", "brave", "opera"):
                if " - " in title:
                    app = title.split(" - ")[-1].strip()
        except Exception:
            app = title.split(" - ")[-1].strip() if " - " in title else title
        return app[:80], title[:200]
    except Exception as exc:
        log.debug("win_active_window failed: %s", exc)
        return None, None


def _cross_active_window():
    try:
        import pywinctl as pw
        win = pw.getActiveWindow()
        if not win:
            return None, None
        title = win.title or ""
        app   = (title.split(" — ")[-1] if " — " in title
                 else title.split(" - ")[-1] if " - " in title
                 else title)
        return app[:80], title[:200]
    except Exception as exc:
        log.debug("cross_active_window failed: %s", exc)
        return None, None


def get_active_window():
    if sys.platform == "win32":
        return _win_active_window()
    return _cross_active_window()


def get_idle_seconds() -> float:
    try:
        if sys.platform == "win32":
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            info = LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(LASTINPUTINFO)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
            millis = ctypes.windll.kernel32.GetTickCount() - info.dwTime
            return millis / 1000.0
        elif sys.platform == "darwin":
            import subprocess
            out = subprocess.check_output(["ioreg", "-c", "IOHIDSystem"], text=True)
            for line in out.splitlines():
                if "HIDIdleTime" in line:
                    return int(line.split("=")[-1].strip()) / 1_000_000_000
        else:
            import subprocess
            return int(subprocess.check_output(["xprintidle"], text=True).strip()) / 1000
    except Exception:
        pass
    return 0.0


def sample() -> dict:
    app, title = get_active_window()
    idle       = get_idle_seconds()
    return {
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "app_name":         app,
        "window_title":     title,
        "idle_seconds":     round(idle, 1),
        "duration_seconds": SAMPLE_SECS,
    }


def flush(buffer: list) -> None:
    if not buffer:
        return
    try:
        r = requests.post(
            f"{BACKEND}/api/events",
            json={"events": buffer},
            timeout=30,
        )
        r.raise_for_status()
        active = sum(1 for e in buffer if e["idle_seconds"] < IDLE_THRESH)
        log.info("Sent %d events (%d active, %d idle)", len(buffer), active, len(buffer)-active)
    except requests.RequestException as exc:
        log.warning("Failed to send batch — will retry: %s", exc)


def run() -> None:
    log.info("Screen time agent started  →  %s", BACKEND)
    log.info("Sampling every %ds, flushing every %dm", SAMPLE_SECS, FLUSH_MINS)

    # start keep-alive thread
    threading.Thread(target=keep_alive, daemon=True).start()
    log.info("Keep-alive thread started")

    # wake up Render with longer timeout
    log.info("Waking up backend (may take 60s on free tier)...")
    for attempt in range(6):
        try:
            requests.get(BACKEND, timeout=30)
            log.info("Backend reachable ✓")
            break
        except Exception:
            log.info("Waiting for backend... attempt %d/6", attempt + 1)
            time.sleep(15)

    buf        = []
    last_flush = time.monotonic()

    while True:
        buf.append(sample())
        elapsed = time.monotonic() - last_flush
        if elapsed >= FLUSH_MINS * 60:
            flush(buf)
            buf        = []
            last_flush = time.monotonic()
        time.sleep(SAMPLE_SECS)


if __name__ == "__main__":
    run()