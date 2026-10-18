"""External opportunity sources for the auto-refreshing Opportunity Radar.

Two free, keyless sources (verified working 2026-10-14):

1. DevpostSource — GET https://devpost.com/api/hackathons
   JSON {hackathons: [{id, title, url, submission_period_dates,
   open_state, prize_amount, organization_name, displayed_location}]}.
   Only open_state == "open" entries are used.

2. SimplifyJobsSource — GET
   https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/README.md
   HTML <table>s with columns Company | Role | Location | Application | Age.
   Rows older than 30 days (Age "31d"+ / "2mo"+) are skipped to keep the
   board fresh.

Every fetch() NEVER raises: network/parsing errors are caught, logged as
warnings, and [] is returned. Callers must be able to treat a source outage
as "no new data" rather than a crash.
"""

import logging
import re
from datetime import date

log = logging.getLogger(__name__)

DEVPOST_URL = "https://devpost.com/api/hackathons"
SIMPLIFYJOBS_URL = ("https://raw.githubusercontent.com/SimplifyJobs/"
                    "Summer2027-Internships/dev/README.md")
REQUEST_TIMEOUT = 15  # seconds
MAX_AGE_DAYS = 30

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"])}

# "Aug 31 - Oct 23, 2026" | "Oct 01 - Nov 12, 2026" |
# "Dec 15, 2026 - Jan 15, 2027" (year rollover) |
# "Oct 23, 2026" (single date)
_DATE_RANGE_RE = re.compile(
    r"(?P<m1>[A-Za-z]{3})\s+(?P<d1>\d{1,2})"
    r"(?:\s*,\s*(?P<y1>\d{4}))?"
    r"\s*-\s*"
    r"(?:(?P<m2>[A-Za-z]{3})\s+)?(?P<d2>\d{1,2})\s*,\s*(?P<y2>\d{4})"
)
_SINGLE_DATE_RE = re.compile(
    r"(?P<m>[A-Za-z]{3})\s+(?P<d>\d{1,2})\s*,\s*(?P<y>\d{4})")


def parse_devpost_deadline(dates_str):
    """Parse Devpost `submission_period_dates` -> end date (ISO string).

    Returns None when the string cannot be parsed. Handles cross-month
    ranges and year rollover ("Dec 15, 2026 - Jan 15, 2027").
    """
    if not dates_str or not isinstance(dates_str, str):
        return None
    s = dates_str.strip()
    m = _DATE_RANGE_RE.search(s)
    if m:
        mon2 = (m.group("m2") or m.group("m1")).lower()[:3]
        try:
            return date(int(m.group("y2")), _MONTHS[mon2],
                        int(m.group("d2"))).isoformat()
        except (KeyError, ValueError):
            return None
    m = _SINGLE_DATE_RE.search(s)
    if m:
        try:
            return date(int(m.group("y")), _MONTHS[m.group("m").lower()[:3]],
                        int(m.group("d"))).isoformat()
        except (KeyError, ValueError):
            return None
    return None


def _slugify(text, max_len=60):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:max_len] or "opp"


def parse_age_days(age_str):
    """Parse SimplifyJobs Age cell ("0d", "29d", "1mo") -> days int.

    Returns None for unparseable values (caller should skip the row).
    """
    if not age_str or not isinstance(age_str, str):
        return None
    m = re.fullmatch(r"\s*(\d+)\s*d\s*", age_str)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"\s*(\d+)\s*mo\s*", age_str)
    if m:
        return int(m.group(1)) * 30
    return None


def _http_get(url):
    """GET with timeout; raises on failure (callers catch)."""
    import requests
    resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={
        "User-Agent": "ACRA-OpportunityRadar/1.0 (+student career platform)",
        "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    })
    resp.raise_for_status()
    return resp


class DevpostSource:
    """Hackathons from the Devpost public API."""

    name = "devpost"

    def fetch(self):
        """Return opportunity dicts (type "hackathon"). Never raises."""
        try:
            return self._fetch_inner()
        except Exception as exc:  # never break the refresh loop
            log.warning("DevpostSource.fetch failed: %s", exc)
            return []

    def _fetch_inner(self):
        data = _http_get(DEVPOST_URL).json()
        out = []
        for h in data.get("hackathons", []) or []:
            if not isinstance(h, dict):
                continue
            if h.get("open_state") != "open":
                continue
            title = (h.get("title") or "").strip()
            url = (h.get("url") or "").strip()
            if not title or not url.startswith("http"):
                continue
            deadline = parse_devpost_deadline(h.get("submission_period_dates"))
            org = (h.get("organization_name") or "Devpost").strip() or "Devpost"
            prize = re.sub(r"<[^>]+>", "",
                           str(h.get("prize_amount") or "")).strip()
            loc_raw = h.get("displayed_location")
            if isinstance(loc_raw, dict):
                loc_raw = loc_raw.get("location") or ""
            location = str(loc_raw or "").strip()
            elig_bits = []
            if location:
                elig_bits.append(location)
            if prize:
                elig_bits.append(f"Prize pool {prize}")
            elig_bits.append("Open to student builders; see official page for "
                             "eligibility and team rules.")
            out.append({
                "id": f"devpost-{h.get('id')}-{_slugify(title, 40)}",
                "title": title[:120],
                "organization": org[:120],
                "type": "hackathon",
                "deadline": deadline,  # None = rolling/unknown
                "eligibility": "; ".join(elig_bits)[:300],
                "link": url,
                "curated": False,
                "source": self.name,
            })
        return out


class SimplifyJobsSource:
    """Summer internships from the SimplifyJobs/Pitt CSC public listing."""

    name = "simplifyjobs"

    def fetch(self):
        """Return opportunity dicts (type "internship"). Never raises."""
        try:
            return self._fetch_inner()
        except Exception as exc:  # never break the refresh loop
            log.warning("SimplifyJobsSource.fetch failed: %s", exc)
            return []

    def _fetch_inner(self):
        html = _http_get(SIMPLIFYJOBS_URL).text
        out = []
        for row in re.findall(r"<tr>(.*?)</tr>", html, re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if len(tds) < 5:
                continue
            text = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                    for c in tds]
            company, role, location = text[0], text[1], text[2]
            if not company or not role:
                continue
            company = re.sub(r"^[^\w]+", "", company).strip()  # strip 🔥 etc.
            age_days = parse_age_days(text[4])
            if age_days is None or age_days > MAX_AGE_DAYS:
                continue
            # Application cell: prefer the <a> wrapping the "Apply" image,
            # else the first non-company http(s) link in the row.
            apply_url = None
            for m in re.finditer(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*<img[^>]*alt="Apply"',
                    tds[3]):
                apply_url = m.group(1)
                break
            if not apply_url:
                for href in re.findall(r'href="([^"]+)"', row):
                    if href.startswith("http") and "simplify.jobs/c/" not in href:
                        apply_url = href
                        break
            if not apply_url or not apply_url.startswith("http"):
                continue
            elig = f"{role} — {location}" if location else role
            if age_days == 0:
                elig += " (posted today)"
            else:
                elig += f" (posted {age_days}d ago)"
            out.append({
                "id": f"simplify-{_slugify(company, 30)}-{_slugify(role, 30)}",
                "title": f"{role} @ {company}"[:120],
                "organization": company[:120],
                "type": "internship",
                "deadline": None,  # rolling applications
                "eligibility": elig[:300],
                "link": apply_url,
                "curated": False,
                "source": self.name,
                "posted_days_ago": age_days,
            })
        return out


SOURCES = (DevpostSource(), SimplifyJobsSource())


def fetch_all():
    """Fetch from every source; never raises. Returns list of dicts."""
    out = []
    for src in SOURCES:
        try:
            out.extend(src.fetch())
        except Exception as exc:  # belt and braces
            log.warning("Source %s failed: %s", src.name, exc)
    return out
