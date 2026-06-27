"""
Screen Time Tracker — backend.

Stores raw activity events from the agent, normalises app names,
aggregates into per-app / per-hour totals, and serves a JSON API
the dashboard reads.

Run from the project root:
    uvicorn backend.main:app --reload
"""
import os, re
from datetime import date, datetime, timedelta
from collections import defaultdict
from typing import List, Optional
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./screentime.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ── ORM models ──────────────────────────────────────────────────────────────

class AppEvent(Base):
    __tablename__ = "app_events"
    id               = Column(Integer, primary_key=True, index=True)
    timestamp        = Column(DateTime, default=datetime.utcnow, index=True)
    raw_name         = Column(String)           # exactly what the agent sent
    app_name         = Column(String, index=True)  # normalised
    category         = Column(String, default="other")
    window_title     = Column(String, nullable=True)
    idle_seconds     = Column(Float, default=0.0)
    duration_seconds = Column(Float, default=60.0)


class AppLimit(Base):
    __tablename__ = "app_limits"
    id            = Column(Integer, primary_key=True)
    app_name      = Column(String, unique=True, index=True)
    limit_minutes = Column(Integer)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── App-name normalisation ────────────────────────────────────────────────

# Keyword → canonical name.  Checked in order; first match wins.
_NAME_MAP = [
    ("visual studio code",  "VS Code"),
    ("vscode",              "VS Code"),
    ("code",               "VS Code"),
    ("code.exe",            "VS Code"),
    ("cursor",              "Cursor"),
    ("pycharm",             "PyCharm"),
    ("intellij",            "IntelliJ"),
    ("webstorm",            "WebStorm"),
    ("android studio",      "Android Studio"),
    ("sublime",             "Sublime Text"),
    ("notepad++",           "Notepad++"),
    ("notepad",             "Notepad"),
    ("vim",                 "Vim"),
    ("windows terminal",    "Terminal"),
    ("powershell",          "Terminal"),
    ("cmd.exe",             "Terminal"),
    ("bash",                "Terminal"),
    ("zsh",                 "Terminal"),
    ("terminal",            "Terminal"),
    ("hyper",               "Terminal"),
    ("wezterm",             "Terminal"),
    ("alacritty",           "Terminal"),
    ("google chrome",       "Chrome"),
    ("chrome",              "Chrome"),
    ("firefox",             "Firefox"),
    ("msedge",              "Edge"),
    ("microsoft edge",      "Edge"),
    ("safari",              "Safari"),
    ("brave",               "Brave"),
    ("opera",               "Opera"),
    ("slack",               "Slack"),
    ("microsoft teams",     "Teams"),
    ("teams",               "Teams"),
    ("discord",             "Discord"),
    ("zoom",                "Zoom"),
    ("skype",               "Skype"),
    ("outlook",             "Outlook"),
    ("thunderbird",         "Thunderbird"),
    ("figma",               "Figma"),
    ("sketch",              "Sketch"),
    ("photoshop",           "Photoshop"),
    ("illustrator",         "Illustrator"),
    ("xd",                  "Adobe XD"),
    ("spotify",             "Spotify"),
    ("youtube",             "YouTube"),
    ("netflix",             "Netflix"),
    ("twitch",              "Twitch"),
    ("reddit",              "Reddit"),
    ("twitter",             "Twitter"),
    ("x.com",               "Twitter"),
    ("instagram",           "Instagram"),
    ("facebook",            "Facebook"),
    ("notion",              "Notion"),
    ("obsidian",            "Obsidian"),
    ("excel",               "Excel"),
    ("word",                "Word"),
    ("powerpoint",          "PowerPoint"),
    ("pages",               "Pages"),
    ("numbers",             "Numbers"),
    ("keynote",             "Keynote"),
    ("finder",              "Finder"),
    ("explorer",            "Explorer"),
    ("postman",             "Postman"),
    ("insomnia",            "Insomnia"),
    ("datagrip",            "DataGrip"),
    ("tableplus",           "TablePlus"),
]

_CATEGORIES = {
    "VS Code":         "productive",
    "Cursor":          "productive",
    "PyCharm":         "productive",
    "IntelliJ":        "productive",
    "WebStorm":        "productive",
    "Android Studio":  "productive",
    "Sublime Text":    "productive",
    "Notepad++":       "productive",
    "Vim":             "productive",
    "Terminal":        "productive",
    "Postman":         "productive",
    "Insomnia":        "productive",
    "DataGrip":        "productive",
    "TablePlus":       "productive",
    "Figma":           "productive",
    "Sketch":          "productive",
    "Photoshop":       "productive",
    "Illustrator":     "productive",
    "Adobe XD":        "productive",
    "Excel":           "productive",
    "Word":            "productive",
    "PowerPoint":      "productive",
    "Pages":           "productive",
    "Numbers":         "productive",
    "Keynote":         "productive",
    "Notion":          "productive",
    "Obsidian":        "productive",
    "Slack":           "comms",
    "Teams":           "comms",
    "Discord":         "comms",
    "Zoom":            "comms",
    "Skype":           "comms",
    "Outlook":         "comms",
    "Thunderbird":     "comms",
    "YouTube":         "distract",
    "Netflix":         "distract",
    "Twitch":          "distract",
    "Reddit":          "distract",
    "Twitter":         "distract",
    "Instagram":       "distract",
    "Facebook":        "distract",
    "Spotify":         "other",
    "Chrome":          "other",
    "Firefox":         "other",
    "Edge":            "other",
    "Safari":          "other",
    "Brave":           "other",
    "Opera":           "other",
}


def normalize(raw: str) -> tuple[str, str]:
    """Return (clean_app_name, category) from a raw window-derived string."""
    if not raw:
        return "Unknown", "other"
    lower = raw.lower().strip()
    lower = re.sub(r"\.exe$", "", lower)
    for key, clean in _NAME_MAP:
        if key in lower:
            return clean, _CATEGORIES.get(clean, "other")
    # Fall back: title-case the raw value, truncated
    clean = raw.strip()[:50]
    return clean, "other"


# ── FastAPI app ───────────────────────────────────────────────────────────

app = FastAPI(title="Screen Time Tracker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class EventBatch(BaseModel):
    events: List[dict]


class LimitIn(BaseModel):
    app_name: str
    limit_minutes: int


# ── Ingest ────────────────────────────────────────────────────────────────

@app.post("/api/events")
def ingest(batch: EventBatch, db: Session = Depends(get_db)):
    rows = []
    for e in batch.events:
        raw = e.get("app_name") or ""
        clean, cat = normalize(raw)
        rows.append(AppEvent(
            timestamp        = datetime.fromisoformat(
                                   e["timestamp"].replace("Z", "+00:00")
                               ).replace(tzinfo=None),
            raw_name         = raw,
            app_name         = clean,
            category         = cat,
            window_title     = e.get("window_title"),
            idle_seconds     = float(e.get("idle_seconds", 0)),
            duration_seconds = float(e.get("duration_seconds", 60)),
        ))
    db.add_all(rows)
    db.commit()
    return {"inserted": len(rows)}


# ── Helpers ───────────────────────────────────────────────────────────────

def _limits_map(db: Session) -> dict:
    return {r.app_name: r.limit_minutes for r in db.query(AppLimit).all()}


def _aggregate(events: list, limits: dict) -> dict:
    """Turn a flat list of AppEvent rows into the JSON the dashboard needs."""
    # per-app totals and per-app per-hour
    app_mins: dict[str, float]        = defaultdict(float)
    app_cat:  dict[str, str]          = {}
    app_hour: dict[str, list[float]]  = defaultdict(lambda: [0.0]*24)
    hourly:   list[float]             = [0.0]*24
    switches  = 0
    prev_app  = None

    for e in events:
        if e.idle_seconds >= 30:   # skip idle samples
            continue
        mins = e.duration_seconds / 60
        app_mins[e.app_name] += mins
        app_cat[e.app_name]   = e.category
        app_hour[e.app_name][e.timestamp.hour] += mins
        hourly[e.timestamp.hour] += mins
        if e.app_name != prev_app:
            switches += 1
            prev_app  = e.app_name

    apps_sorted = sorted(app_mins.items(), key=lambda x: -x[1])
    total = sum(app_mins.values())
    productive = sum(m for a, m in app_mins.items() if app_cat.get(a) == "productive")
    productive_pct = round(productive / total * 100) if total else 0

    apps_out = []
    for name, mins in apps_sorted:
        lim = limits.get(name)
        apps_out.append({
            "app_name":      name,
            "minutes":       round(mins),
            "category":      app_cat.get(name, "other"),
            "limit_minutes": lim,
            "over_limit":    bool(lim and mins > lim),
            "hourly":        [round(v) for v in app_hour[name]],
        })

    return {
        "total_minutes":   round(total),
        "productive_pct":  productive_pct,
        "switch_count":    switches,
        "first_app":       apps_sorted[0][0] if apps_sorted else None,
        "apps":            apps_out,
        "hourly":          [round(v) for v in hourly],
    }


def _avg_daily(db: Session, exclude_today: bool = True) -> int:
    """Average daily minutes over the last 14 days (used for delta display)."""
    end   = datetime.combine(date.today(), datetime.min.time())
    start = end - timedelta(days=14)
    events = (
        db.query(AppEvent)
        .filter(AppEvent.timestamp >= start, AppEvent.timestamp < end,
                AppEvent.idle_seconds < 30)
        .all()
    )
    by_day: dict[date, float] = defaultdict(float)
    for e in events:
        by_day[e.timestamp.date()] += e.duration_seconds / 60
    if not by_day:
        return 0
    return round(sum(by_day.values()) / len(by_day))


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/today")
def today(db: Session = Depends(get_db)):
    start  = datetime.combine(date.today(), datetime.min.time())
    events = db.query(AppEvent).filter(AppEvent.timestamp >= start).all()
    lims   = _limits_map(db)
    result = _aggregate(events, lims)
    result["date"]              = date.today().isoformat()
    result["avg_daily_minutes"] = _avg_daily(db)
    return result


@app.get("/api/week")
def week(db: Session = Depends(get_db)):
    today_start = datetime.combine(date.today(), datetime.min.time())
    week_start  = today_start - timedelta(days=6)
    events = (
        db.query(AppEvent)
        .filter(AppEvent.timestamp >= week_start, AppEvent.idle_seconds < 30)
        .all()
    )
    lims = _limits_map(db)

    by_day: dict[date, list] = defaultdict(list)
    for e in events:
        by_day[e.timestamp.date()].append(e)

    days_out = []
    for i in range(7):
        d    = (date.today() - timedelta(days=6 - i))
        evts = by_day.get(d, [])
        total      = sum(e.duration_seconds / 60 for e in evts)
        productive = sum(e.duration_seconds / 60 for e in evts if e.category == "productive")
        days_out.append({
            "date":                d.isoformat(),
            "day":                 d.strftime("%a"),
            "total_minutes":       round(total),
            "productive_minutes":  round(productive),
            "today":               d == date.today(),
        })

    all_mins = [d["total_minutes"] for d in days_out]
    total_w  = sum(all_mins)
    avg_w    = round(total_w / 7) if total_w else 0
    longest  = max(days_out, key=lambda x: x["total_minutes"], default=None)

    return {
        "days":          days_out,
        "total_minutes": total_w,
        "avg_minutes":   avg_w,
        "longest_day":   longest["day"] if longest and longest["total_minutes"] > 0 else "—",
    }


@app.get("/api/history")
def history(days: int = 30, db: Session = Depends(get_db)):
    start = datetime.combine(date.today() - timedelta(days=days - 1),
                             datetime.min.time())
    events = (
        db.query(AppEvent)
        .filter(AppEvent.timestamp >= start, AppEvent.idle_seconds < 30)
        .all()
    )
    by_day: dict[date, float] = defaultdict(float)
    for e in events:
        by_day[e.timestamp.date()] += e.duration_seconds / 60

    out = []
    for i in range(days):
        d = date.today() - timedelta(days=days - 1 - i)
        out.append({
            "date":          d.isoformat(),
            "total_minutes": round(by_day.get(d, 0)),
            "today":         d == date.today(),
        })
    return out


@app.get("/api/limits")
def get_limits(db: Session = Depends(get_db)):
    return [{"app_name": r.app_name, "limit_minutes": r.limit_minutes}
            for r in db.query(AppLimit).all()]


@app.post("/api/limits")
def set_limit(body: LimitIn, db: Session = Depends(get_db)):
    row = db.query(AppLimit).filter(AppLimit.app_name == body.app_name).first()
    if row:
        row.limit_minutes = body.limit_minutes
    else:
        db.add(AppLimit(app_name=body.app_name, limit_minutes=body.limit_minutes))
    db.commit()
    return {"app_name": body.app_name, "limit_minutes": body.limit_minutes}


@app.delete("/api/limits/{app_name}")
def delete_limit(app_name: str, db: Session = Depends(get_db)):
    db.query(AppLimit).filter(AppLimit.app_name == app_name).delete()
    db.commit()
    return {"deleted": app_name}


@app.get("/")
def root():
    return {"status": "ok"}
