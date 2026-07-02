"""
Screen Time Agent — sends every sample immediately to the backend.
No batching = no data loss on shutdown. Each 60-second sample is
written to the database the moment it is collected.
"""
import os, sys, time, logging, ctypes, threading, json
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
IDLE_THRESH = int(os.getenv("IDLE_THRESHOLD_SECONDS",  30))
BUFFER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "buffer.json")


# ── disk buffer — only used when backend is unreachable ───────────────────────

def save_buffer(buf):
    try:
        with open(BUFFER_FILE, "w") as f:
            json.dump(buf, f)
    except Exception:
        pass

def load_buffer():
    try:
        if os.path.exists(BUFFER_FILE):
            with open(BUFFER_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                log.info("Recovered %d unsent events from last session", len(data))
                return data
    except Exception:
        pass
    return []

def clear_buffer():
    try:
        with open(BUFFER_FILE, "w") as f:
            json.dump([], f)
    except Exception:
        pass


# ── keep-alive ────────────────────────────────────────────────────────────────

def keep_alive():
    while True:
        try:
            requests.get(BACKEND, timeout=5)
        except Exception:
            pass
        time.sleep(600)


# ── platform helpers ──────────────────────────────────────────────────────────

def _win_active_window():
    try:
        import psutil
        hwnd   = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf    = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        title  = buf.value
        pid    = ctypes.c_ulong()
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


# ── send ──────────────────────────────────────────────────────────────────────

def send(events: list) -> bool:
    """Send a list of events. Returns True on success."""
    if not events:
        return True
    try:
        r = requests.post(
            f"{BACKEND}/api/events",
            json={"events": events},
            timeout=15,
        )
        r.raise_for_status()
        return True
    except requests.RequestException as exc:
        log.warning("Send failed — buffering to disk: %s", exc)
        return False


# ── main loop ─────────────────────────────────────────────────────────────────

def run():
    log.info("Screen time agent started  →  %s", BACKEND)
    log.info("Sending every sample immediately — no data lost on shutdown")

    # keep Render awake
    threading.Thread(target=keep_alive, daemon=True).start()

    # wake up Render
    log.info("Waking up backend...")
    for attempt in range(6):
        try:
            requests.get(BACKEND, timeout=30)
            log.info("Backend reachable")
            break
        except Exception:
            log.info("Waiting... attempt %d/6", attempt + 1)
            time.sleep(15)

    # send any events buffered from previous session
    pending = load_buffer()
    if pending:
        log.info("Sending %d recovered events from last session...", len(pending))
        if send(pending):
            log.info("Recovered events sent successfully")
            clear_buffer()
        else:
            log.warning("Could not send recovered events — will retry next startup")

    # offline buffer for current session
    offline_buf = []

    while True:
        app, title = get_active_window()
        idle       = get_idle_seconds()

        event = {
            "timestamp":        datetime.now(timezone.utc).isoformat(),
            "app_name":         app,
            "window_title":     title,
            "idle_seconds":     round(idle, 1),
            "duration_seconds": SAMPLE_SECS,
        }

        # try to send immediately
        if send([event]):
            # if we had offline events, try to flush them too
            if offline_buf:
                if send(offline_buf):
                    log.info("Flushed %d offline events", len(offline_buf))
                    offline_buf = []
                    clear_buffer()
        else:
            # backend unreachable — save to disk
            offline_buf.append(event)
            save_buffer(offline_buf)
            log.info("Offline — buffered %d events to disk", len(offline_buf))

        active = "active" if idle < IDLE_THRESH else "idle"
        log.info("Sampled: %s (%s) — %s", app or "Unknown", active, "sent" if not offline_buf else f"offline ({len(offline_buf)} buffered)")

        time.sleep(SAMPLE_SECS)


if __name__ == "__main__":
    run()