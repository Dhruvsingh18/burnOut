"""
Screen Time Tracker — backend with Chrome tab analysis.
"""
import os, re
from datetime import date, datetime, timedelta
from collections import defaultdict
from typing import List, Optional
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./screentime.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── ORM models ────────────────────────────────────────────────────────────────

class AppEvent(Base):
    __tablename__ = "app_events"
    id               = Column(Integer, primary_key=True, index=True)
    timestamp        = Column(DateTime, default=datetime.utcnow, index=True)
    raw_name         = Column(String)
    app_name         = Column(String, index=True)
    category         = Column(String, default="other")
    window_title     = Column(String, nullable=True)
    idle_seconds     = Column(Float, default=0.0)
    duration_seconds = Column(Float, default=60.0)


class AppLimit(Base):
    __tablename__ = "app_limits"
    id            = Column(Integer, primary_key=True)
    app_name      = Column(String, unique=True, index=True)
    limit_minutes = Column(Integer)


class ChromeTabEvent(Base):
    """Stores tab snapshots sent from the Chrome extension."""
    __tablename__ = "chrome_tab_events"
    id        = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    url       = Column(String)
    title     = Column(String)
    domain    = Column(String, index=True)
    category  = Column(String, default="other")
    active    = Column(Integer, default=0)  # 1 = active tab


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Chrome site classification ─────────────────────────────────────────────────

PRODUCTIVE_PATTERNS = [
    "github", "gitlab", "stackoverflow", "stack overflow",
    "mdn", "developer.mozilla", "docs.", "documentation",
    "coursera", "udemy", "khanacademy", "edx", "pluralsight",
    "leetcode", "hackerrank", "codewars", "replit",
    "wikipedia", "britannica", "scholar.google", "arxiv",
    "google docs", "google sheets", "google slides", "notion",
    "figma", "linear", "jira", "confluence", "trello",
    "chatgpt", "claude", "anthropic", "openai",
    "vercel", "netlify", "heroku", "railway", "render",
    "aws", "azure", "cloud.google", "firebase",
    "npm", "pypi", "crates.io", "packagist",
    "w3schools", "tutorialspoint", "geeksforgeeks",
    "medium", "dev.to", "hashnode", "substack",
    "canvas", "blackboard", "moodle", "schoology",
    "quizlet", "anki", "duolingo", "brilliant",
    "google classroom", "classroom.google",
    "zoom", "meet.google", "teams.microsoft",
    "overleaf", "wolfram", "desmos", "symbolab",
    "pubmed", "jstor", "semanticscholar",
    "codecademy", "freecodecamp", "theodinproject", "khanacademy", "khan academy", "mit", "stanford", "harvard", "yale", "ocw", "opencourseware",
    "exercism", "codepen", "jsfiddle", "codesandbox",
]

UNPRODUCTIVE_PATTERNS = [
    "youtube", "netflix", "hulu", "disney", "hbomax", "primevideo",
    "twitch", "tiktok", "instagram", "facebook", "twitter", "x.com",
    "reddit", "9gag", "buzzfeed", "tumblr", "pinterest",
    "snapchat", "whatsapp", "telegram", "discord",
    "espn", "bleacherreport", "nfl", "nba",
    "ebay", "amazon", "etsy", "shopify", "walmart",
    "buzzfeed", "dailymail", "tmz", "perez",
    "spotify", "soundcloud", "pandora",
    "candy", "game", "play", "roblox", "minecraft",
    "pornhub", "onlyfans",
]

NEUTRAL_PATTERNS = [
    "google.com/search", "bing.com/search", "duckduckgo",
    "gmail", "outlook", "yahoo mail",
    "maps.google", "weather",
    "bank", "chase", "wellsfargo", "paypal", "venmo",
    "news", "cnn", "bbc", "nytimes", "washingtonpost",
]


def classify_chrome_site(url: str, title: str) -> str:
    text = (url + " " + title).lower()
    for p in PRODUCTIVE_PATTERNS:
        if p in text:
            return "productive"
    for p in UNPRODUCTIVE_PATTERNS:
        if p in text:
            return "unproductive"
    for p in NEUTRAL_PATTERNS:
        if p in text:
            return "neutral"
    return "other"


def extract_domain(url: str) -> str:
    try:
        url = url.replace("https://", "").replace("http://", "").replace("www.", "")
        return url.split("/")[0].split("?")[0][:60]
    except Exception:
        return url[:60]


def classify_title_only(title: str) -> str:
    """Classify based on window title alone (no URL) — used for agent events."""
    t = title.lower()
    # strip browser suffix
    for suffix in [" - google chrome", " - microsoft edge", " - firefox", " | google chrome"]:
        t = t.replace(suffix, "")
    t = t.strip()

    for p in PRODUCTIVE_PATTERNS:
        if p in t:
            return "productive"
    for p in UNPRODUCTIVE_PATTERNS:
        if p in t:
            return "unproductive"
    for p in NEUTRAL_PATTERNS:
        if p in t:
            return "neutral"
    return "other"


def clean_title(title: str) -> str:
    """Extract readable site/page name from a window title."""
    if not title:
        return "Unknown"
    t = title
    for suffix in [" - Google Chrome", " - Microsoft Edge", " - Firefox",
                   " | Google Chrome", " — Google Chrome"]:
        t = t.replace(suffix, "")
    # take last segment after " - " or " | "
    for sep in [" - ", " | ", " — "]:
        if sep in t:
            parts = t.split(sep)
            # prefer last non-empty part as site name
            site = parts[-1].strip()
            if len(site) > 2:
                return site
    return t.strip()[:60]


# ── App name normalisation ─────────────────────────────────────────────────────

_NAME_MAP = [
    ("visual studio code", "VS Code"), ("vscode", "VS Code"),
    ("code", "VS Code"), ("code.exe", "VS Code"),
    ("cursor", "Cursor"), ("pycharm", "PyCharm"),
    ("intellij", "IntelliJ"), ("webstorm", "WebStorm"),
    ("android studio", "Android Studio"), ("sublime", "Sublime Text"),
    ("notepad++", "Notepad++"), ("notepad", "Notepad"), ("vim", "Vim"),
    ("windows terminal", "Terminal"), ("powershell", "Terminal"),
    ("cmd.exe", "Terminal"), ("bash", "Terminal"), ("zsh", "Terminal"),
    ("terminal", "Terminal"), ("hyper", "Terminal"), ("alacritty", "Terminal"),
    ("google chrome", "Chrome"), ("chrome", "Chrome"),
    ("firefox", "Firefox"), ("msedge", "Edge"), ("microsoft edge", "Edge"),
    ("safari", "Safari"), ("brave", "Brave"), ("opera", "Opera"),
    ("slack", "Slack"), ("microsoft teams", "Teams"), ("teams", "Teams"),
    ("discord", "Discord"), ("zoom", "Zoom"), ("skype", "Skype"),
    ("outlook", "Outlook"), ("thunderbird", "Thunderbird"),
    ("figma", "Figma"), ("sketch", "Sketch"),
    ("photoshop", "Photoshop"), ("illustrator", "Illustrator"),
    ("spotify", "Spotify"), ("youtube", "YouTube"), ("netflix", "Netflix"),
    ("twitch", "Twitch"), ("notion", "Notion"), ("obsidian", "Obsidian"),
    ("excel", "Excel"), ("word", "Word"), ("powerpoint", "PowerPoint"),
    ("postman", "Postman"), ("datagrip", "DataGrip"),
]

_CATEGORIES = {
    "VS Code": "productive", "Cursor": "productive", "PyCharm": "productive",
    "IntelliJ": "productive", "WebStorm": "productive",
    "Android Studio": "productive", "Sublime Text": "productive",
    "Notepad++": "productive", "Vim": "productive", "Terminal": "productive",
    "Postman": "productive", "DataGrip": "productive",
    "Figma": "productive", "Sketch": "productive",
    "Photoshop": "productive", "Illustrator": "productive",
    "Excel": "productive", "Word": "productive", "PowerPoint": "productive",
    "Notion": "productive", "Obsidian": "productive",
    "Slack": "comms", "Teams": "comms", "Discord": "comms",
    "Zoom": "comms", "Skype": "comms", "Outlook": "comms",
    "Thunderbird": "comms",
    "YouTube": "distract", "Netflix": "distract", "Twitch": "distract",
    "Spotify": "other",
    "Chrome": "other", "Firefox": "other", "Edge": "other",
    "Safari": "other", "Brave": "other", "Opera": "other",
}

BROWSER_APPS = {"Chrome", "Firefox", "Edge", "Safari", "Brave", "Opera"}


def normalize(raw: str, window_title: str = "") -> tuple:
    if not raw:
        return "Unknown", "other"
    lower = re.sub(r"\.exe$", "", raw.lower().strip())
    for key, clean in _NAME_MAP:
        if key in lower:
            cat = _CATEGORIES.get(clean, "other")
            # For browsers, try to refine category from window title
            if clean in BROWSER_APPS and window_title:
                title_cat = classify_title_only(window_title)
                if title_cat in ("productive", "unproductive"):
                    cat = title_cat if title_cat != "unproductive" else "distract"
            return clean, cat
    return raw.strip()[:50], "other"


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="Screen Time Tracker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class EventBatch(BaseModel):
    events: List[dict]


class LimitIn(BaseModel):
    app_name: str
    limit_minutes: int


class ChromeTabBatch(BaseModel):
    """Payload from the Chrome extension."""
    tabs: List[dict]  # [{url, title, active}]


# ── Ingest ─────────────────────────────────────────────────────────────────────

@app.post("/api/events")
def ingest(batch: EventBatch, db: Session = Depends(get_db)):
    rows = []
    for e in batch.events:
        raw = e.get("app_name") or ""
        title = e.get("window_title") or ""
        clean, cat = normalize(raw, title)
        rows.append(AppEvent(
            timestamp=datetime.fromisoformat(
                e["timestamp"].replace("Z", "+00:00")
            ).replace(tzinfo=None),
            raw_name=raw,
            app_name=clean,
            category=cat,
            window_title=title,
            idle_seconds=float(e.get("idle_seconds", 0)),
            duration_seconds=float(e.get("duration_seconds", 60)),
        ))
    db.add_all(rows)
    db.commit()
    return {"inserted": len(rows)}


@app.post("/api/chrome-tabs")
def ingest_chrome_tabs(batch: ChromeTabBatch, db: Session = Depends(get_db)):
    """Receives tab data from the Chrome extension every minute."""
    rows = []
    for t in batch.tabs:
        url   = t.get("url", "")
        title = t.get("title", "")
        if not url or url.startswith("chrome://"):
            continue
        domain = extract_domain(url)
        cat    = classify_chrome_site(url, title)
        rows.append(ChromeTabEvent(
            timestamp=datetime.utcnow(),
            url=url[:500],
            title=title[:200],
            domain=domain,
            category=cat,
            active=1 if t.get("active") else 0,
        ))
    db.add_all(rows)
    db.commit()
    return {"inserted": len(rows)}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _limits_map(db: Session) -> dict:
    return {r.app_name: r.limit_minutes for r in db.query(AppLimit).all()}


def _aggregate(events: list, limits: dict) -> dict:
    app_mins   = defaultdict(float)
    app_cat    = {}
    app_hour   = defaultdict(lambda: [0.0] * 24)
    hourly     = [0.0] * 24
    switches   = 0
    prev_app   = None

    for e in events:
        if e.idle_seconds >= 30:
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
    total       = sum(app_mins.values())
    productive  = sum(m for a, m in app_mins.items() if app_cat.get(a) == "productive")
    prod_pct    = round(productive / total * 100) if total else 0

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
        "total_minutes":  round(total),
        "productive_pct": prod_pct,
        "switch_count":   switches,
        "first_app":      apps_sorted[0][0] if apps_sorted else None,
        "apps":           apps_out,
        "hourly":         [round(v) for v in hourly],
    }


def _avg_daily(db: Session) -> int:
    end    = datetime.combine(date.today(), datetime.min.time())
    start  = end - timedelta(days=14)
    events = db.query(AppEvent).filter(
        AppEvent.timestamp >= start,
        AppEvent.timestamp < end,
        AppEvent.idle_seconds < 30,
    ).all()
    by_day = defaultdict(float)
    for e in events:
        by_day[e.timestamp.date()] += e.duration_seconds / 60
    if not by_day:
        return 0
    return round(sum(by_day.values()) / len(by_day))


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/api/today")
def today(db: Session = Depends(get_db)):
    start  = datetime.combine(date.today(), datetime.min.time())
    events = db.query(AppEvent).filter(AppEvent.timestamp >= start).all()
    lims   = _limits_map(db)
    result = _aggregate(events, lims)
    result["date"]              = date.today().isoformat()
    result["avg_daily_minutes"] = _avg_daily(db)
    return result


@app.get("/api/chrome-analysis")
def chrome_analysis(db: Session = Depends(get_db)):
    """
    Returns two sub-analyses:
    1. title_analysis — built from agent window title data (always available)
    2. tab_analysis   — built from Chrome extension tab data (richer, if installed)
    """
    start = datetime.combine(date.today(), datetime.min.time())

    # ── 1. Title-based analysis from agent events ──────────────────────────
    browser_events = db.query(AppEvent).filter(
        AppEvent.timestamp >= start,
        AppEvent.app_name.in_(list(BROWSER_APPS)),
        AppEvent.idle_seconds < 30,
    ).all()

    title_sites: dict = defaultdict(lambda: {"minutes": 0.0, "category": "other", "raw_titles": []})
    for e in browser_events:
        if not e.window_title:
            continue
        site = clean_title(e.window_title)
        cat  = classify_title_only(e.window_title)
        title_sites[site]["minutes"]   += e.duration_seconds / 60
        title_sites[site]["category"]   = cat
        title_sites[site]["raw_titles"].append(e.window_title)

    title_out = sorted(
        [{"site": k, "minutes": round(v["minutes"]), "category": v["category"]}
         for k, v in title_sites.items() if v["minutes"] > 0.5],
        key=lambda x: -x["minutes"],
    )[:20]

    # ── 2. Extension tab analysis ──────────────────────────────────────────
    tab_events = db.query(ChromeTabEvent).filter(
        ChromeTabEvent.timestamp >= start
    ).all()

    domain_data: dict = defaultdict(lambda: {"count": 0, "category": "other", "titles": set()})
    for t in tab_events:
        domain_data[t.domain]["count"]   += 1
        domain_data[t.domain]["category"] = t.category
        if t.title:
            domain_data[t.domain]["titles"].add(t.title[:60])

    tab_out = sorted(
        [{"domain": k, "snapshots": v["count"], "category": v["category"],
          "sample_titles": list(v["titles"])[:3]}
         for k, v in domain_data.items()],
        key=lambda x: -x["snapshots"],
    )[:20]

    # ── summary ───────────────────────────────────────────────────────────
    prod_min  = sum(s["minutes"] for s in title_out if s["category"] == "productive")
    unprod_min = sum(s["minutes"] for s in title_out if s["category"] == "unproductive")
    neut_min  = sum(s["minutes"] for s in title_out if s["category"] not in ("productive","unproductive"))
    total_min = prod_min + unprod_min + neut_min

    return {
        "extension_installed": len(tab_events) > 0,
        "summary": {
            "productive_minutes":   round(prod_min),
            "unproductive_minutes": round(unprod_min),
            "neutral_minutes":      round(neut_min),
            "total_minutes":        round(total_min),
            "productive_pct":       round(prod_min / total_min * 100) if total_min else 0,
        },
        "title_analysis": title_out,
        "tab_analysis":   tab_out,
    }


@app.get("/api/week")
def week(db: Session = Depends(get_db)):
    today_start = datetime.combine(date.today(), datetime.min.time())
    week_start  = today_start - timedelta(days=6)
    events = db.query(AppEvent).filter(
        AppEvent.timestamp >= week_start,
        AppEvent.idle_seconds < 30,
    ).all()
    lims = _limits_map(db)
    by_day: dict = defaultdict(list)
    for e in events:
        by_day[e.timestamp.date()].append(e)

    days_out = []
    for i in range(7):
        d    = date.today() - timedelta(days=6 - i)
        evts = by_day.get(d, [])
        total     = sum(e.duration_seconds / 60 for e in evts)
        productive = sum(e.duration_seconds / 60 for e in evts if e.category == "productive")
        days_out.append({
            "date":               d.isoformat(),
            "day":                d.strftime("%a"),
            "total_minutes":      round(total),
            "productive_minutes": round(productive),
            "today":              d == date.today(),
        })

    all_mins = [d["total_minutes"] for d in days_out]
    total_w  = sum(all_mins)
    longest  = max(days_out, key=lambda x: x["total_minutes"], default=None)
    return {
        "days":          days_out,
        "total_minutes": total_w,
        "avg_minutes":   round(total_w / 7) if total_w else 0,
        "longest_day":   longest["day"] if longest and longest["total_minutes"] > 0 else "—",
    }


@app.get("/api/history")
def history(days: int = 30, db: Session = Depends(get_db)):
    start = datetime.combine(
        date.today() - timedelta(days=days - 1), datetime.min.time()
    )
    events = db.query(AppEvent).filter(
        AppEvent.timestamp >= start, AppEvent.idle_seconds < 30
    ).all()
    by_day: dict = defaultdict(float)
    for e in events:
        by_day[e.timestamp.date()] += e.duration_seconds / 60
    return [
        {"date": (date.today() - timedelta(days=days - 1 - i)).isoformat(),
         "total_minutes": round(by_day.get(date.today() - timedelta(days=days - 1 - i), 0)),
         "today": (date.today() - timedelta(days=days - 1 - i)) == date.today()}
        for i in range(days)
    ]


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
    return {"status": "ok", "service": "burnout-tracker"}