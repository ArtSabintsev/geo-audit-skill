#!/usr/bin/env python3
"""
Content freshness scorer for GEO audit.

Detects publication and modification dates from multiple on-page sources
and scores content freshness. Stale content is less likely to be cited
by AI models.

Sources checked:
  - Meta tags: article:published_time, article:modified_time, date
  - JSON-LD: datePublished, dateModified
  - <time> elements with datetime attributes
  - Visible text: "Published on...", "Updated...", "Last modified..."
  - HTTP headers: Last-Modified

Accepts a URL as argument or reads fetch_page.py JSON from stdin.
"""

import sys
import json
import re
from datetime import datetime, timezone

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: Missing dependencies. Run: pip install requests beautifulsoup4 lxml")
    sys.exit(1)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
}

# Month name to number
MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


def to_grade(score):
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    if score >= 35:
        return "D"
    return "F"


def parse_date(date_str):
    """Try to parse a date string into a datetime object."""
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()

    # ISO format: 2024-01-15, 2024-01-15T10:30:00Z, 2024-01-15T10:30:00+00:00
    iso_match = re.match(r"(\d{4})-(\d{2})-(\d{2})", date_str)
    if iso_match:
        try:
            return datetime(
                int(iso_match.group(1)),
                int(iso_match.group(2)),
                int(iso_match.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass

    # "January 15, 2024" or "Jan 15, 2024" or "15 January 2024"
    month_first = re.match(
        r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", date_str, re.I
    )
    if month_first:
        month = MONTH_MAP.get(month_first.group(1).lower())
        if month:
            try:
                return datetime(
                    int(month_first.group(3)), month,
                    int(month_first.group(2)), tzinfo=timezone.utc,
                )
            except ValueError:
                pass

    day_first = re.match(
        r"(\d{1,2})\s+(\w+)\s+(\d{4})", date_str, re.I
    )
    if day_first:
        month = MONTH_MAP.get(day_first.group(2).lower())
        if month:
            try:
                return datetime(
                    int(day_first.group(3)), month,
                    int(day_first.group(1)), tzinfo=timezone.utc,
                )
            except ValueError:
                pass

    # MM/DD/YYYY or DD/MM/YYYY (assume MM/DD/YYYY for US)
    slash_match = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", date_str)
    if slash_match:
        try:
            return datetime(
                int(slash_match.group(3)),
                int(slash_match.group(1)),
                int(slash_match.group(2)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass

    # HTTP date: "Mon, 15 Jan 2024 10:30:00 GMT"
    http_match = re.match(
        r"\w+,\s+(\d{1,2})\s+(\w+)\s+(\d{4})", date_str, re.I
    )
    if http_match:
        month = MONTH_MAP.get(http_match.group(2).lower())
        if month:
            try:
                return datetime(
                    int(http_match.group(3)), month,
                    int(http_match.group(1)), tzinfo=timezone.utc,
                )
            except ValueError:
                pass

    return None


def fetch_page_data(url, timeout=30):
    """Minimal page fetch for standalone usage."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        return {"error": str(e)}

    soup = BeautifulSoup(resp.text, "lxml")
    raw_soup = BeautifulSoup(resp.text, "lxml")

    meta_tags = {}
    for meta in soup.find_all("meta"):
        name = meta.get("name", meta.get("property", ""))
        content = meta.get("content", "")
        if name and content:
            meta_tags[name.lower()] = content

    structured_data = []
    for script in raw_soup.find_all("script", type="application/ld+json"):
        try:
            structured_data.append(json.loads(script.string))
        except (json.JSONDecodeError, TypeError):
            pass

    time_elements = []
    for time_el in raw_soup.find_all("time"):
        dt = time_el.get("datetime", "")
        text = time_el.get_text(strip=True)
        if dt or text:
            time_elements.append({"datetime": dt, "text": text})

    for el in soup.find_all(["script", "style", "nav", "footer", "header"]):
        el.decompose()
    text_content = soup.get_text(separator=" ", strip=True)

    return {
        "url": url,
        "meta_tags": meta_tags,
        "structured_data": structured_data,
        "time_elements": time_elements,
        "text_content": text_content,
        "response_headers": dict(resp.headers),
    }


def analyze_freshness(page_data):
    """Analyze content freshness from dates found on the page."""
    if "error" in page_data:
        return {"error": page_data["error"]}

    dates_found = []
    findings = []

    meta_tags = page_data.get("meta_tags", {})
    structured_data = page_data.get("structured_data", [])
    time_elements = page_data.get("time_elements", [])
    text = page_data.get("text_content", "")
    response_headers = page_data.get("response_headers", {})

    # --- 1. Meta tag dates ---
    date_meta_keys = [
        "article:published_time", "article:modified_time",
        "date", "dc.date", "dc.date.created", "dc.date.modified",
        "last-modified", "publish-date", "pubdate",
        "og:updated_time", "og:article:published_time",
        "og:article:modified_time",
    ]
    for key in date_meta_keys:
        val = meta_tags.get(key, "")
        dt = parse_date(val)
        if dt:
            date_type = "modified" if "modified" in key else "published"
            dates_found.append({
                "source": f"meta:{key}",
                "date": dt.isoformat(),
                "type": date_type,
                "confidence": "confirmed",
            })

    # --- 2. JSON-LD dates ---
    def extract_jsonld_dates(obj, path=""):
        if isinstance(obj, dict):
            for key in ("datePublished", "dateModified", "dateCreated", "uploadDate"):
                if key in obj:
                    dt = parse_date(obj[key])
                    if dt:
                        date_type = "modified" if "Modified" in key else "published"
                        dates_found.append({
                            "source": f"json-ld:{key}",
                            "date": dt.isoformat(),
                            "type": date_type,
                            "confidence": "confirmed",
                        })
            for v in obj.values():
                extract_jsonld_dates(v)
        elif isinstance(obj, list):
            for item in obj:
                extract_jsonld_dates(item)

    for sd in structured_data:
        extract_jsonld_dates(sd)

    # --- 3. <time> elements ---
    for te in time_elements:
        dt = parse_date(te.get("datetime", "")) or parse_date(te.get("text", ""))
        if dt:
            dates_found.append({
                "source": "time_element",
                "date": dt.isoformat(),
                "type": "published",
                "confidence": "confirmed",
            })

    # --- 4. Visible text date patterns ---
    text_date_patterns = [
        (r"(?:published|posted|written)\s+(?:on\s+)?(\w+\s+\d{1,2},?\s+\d{4})", "published"),
        (r"(?:published|posted|written)\s+(?:on\s+)?(\d{4}-\d{2}-\d{2})", "published"),
        (r"(?:updated|modified|edited|revised)\s+(?:on\s+)?(\w+\s+\d{1,2},?\s+\d{4})", "modified"),
        (r"(?:updated|modified|edited|revised)\s+(?:on\s+)?(\d{4}-\d{2}-\d{2})", "modified"),
        (r"(?:last\s+(?:updated|modified))\s*:?\s*(\w+\s+\d{1,2},?\s+\d{4})", "modified"),
        (r"(?:last\s+(?:updated|modified))\s*:?\s*(\d{4}-\d{2}-\d{2})", "modified"),
    ]
    for pattern, date_type in text_date_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            dt = parse_date(match.group(1))
            if dt:
                dates_found.append({
                    "source": "visible_text",
                    "date": dt.isoformat(),
                    "type": date_type,
                    "confidence": "likely",
                })

    # --- 5. HTTP Last-Modified header ---
    last_modified = response_headers.get("Last-Modified", "")
    if last_modified:
        dt = parse_date(last_modified)
        if dt:
            dates_found.append({
                "source": "http_header:Last-Modified",
                "date": dt.isoformat(),
                "type": "modified",
                "confidence": "confirmed",
            })

    # --- Determine freshness ---
    now = datetime.now(timezone.utc)

    if not dates_found:
        findings.append({
            "id": "freshness-no-dates",
            "dimension": "content_freshness",
            "severity": "medium",
            "confidence": "confirmed",
            "title": "No publication or modification dates detected",
            "description": (
                "No dates found in meta tags, JSON-LD, <time> elements, "
                "visible text, or HTTP headers. Content without dates is harder "
                "for AI models to assess for freshness and may be deprioritized "
                "in favor of dated content."
            ),
        })
        score = 30
    else:
        # Find the most recent published and modified dates
        published_dates = [d for d in dates_found if d["type"] == "published"]
        modified_dates = [d for d in dates_found if d["type"] == "modified"]

        newest_published = None
        if published_dates:
            newest_published = max(
                published_dates,
                key=lambda d: d["date"],
            )

        newest_modified = None
        if modified_dates:
            newest_modified = max(
                modified_dates,
                key=lambda d: d["date"],
            )

        # The most recent date overall
        most_recent = newest_modified or newest_published
        most_recent_dt = parse_date(most_recent["date"])

        if most_recent_dt:
            age_days = (now - most_recent_dt).days
        else:
            age_days = None

        # Score based on age
        if age_days is not None:
            if age_days < 0:
                # Future date (likely a mistake)
                score = 50
                findings.append({
                    "id": "freshness-future-date",
                    "dimension": "content_freshness",
                    "severity": "low",
                    "confidence": "confirmed",
                    "title": "Content date is in the future",
                    "description": (
                        f"The most recent date ({most_recent['date'][:10]}) is in "
                        "the future. This may be a scheduling artifact or an error."
                    ),
                })
            elif age_days <= 30:
                score = 100
            elif age_days <= 90:
                score = 85
            elif age_days <= 180:
                score = 70
            elif age_days <= 365:
                score = 55
            elif age_days <= 730:
                score = 35
            else:
                score = 15
        else:
            score = 30

        # Freshness findings
        if age_days is not None and age_days >= 0:
            if age_days <= 90:
                findings.append({
                    "id": "freshness-recent",
                    "dimension": "content_freshness",
                    "severity": "pass",
                    "confidence": "confirmed" if most_recent["confidence"] == "confirmed" else "likely",
                    "title": f"Content is fresh ({age_days} days old)",
                    "description": (
                        f"Most recent date: {most_recent['date'][:10]} "
                        f"(source: {most_recent['source']}). Fresh content is "
                        "more likely to be cited by AI models."
                    ),
                })
            elif age_days <= 365:
                findings.append({
                    "id": "freshness-aging",
                    "dimension": "content_freshness",
                    "severity": "low",
                    "confidence": "confirmed" if most_recent["confidence"] == "confirmed" else "likely",
                    "title": f"Content is aging ({age_days} days since last update)",
                    "description": (
                        f"Most recent date: {most_recent['date'][:10]} "
                        f"(source: {most_recent['source']}). Consider updating "
                        "the content to maintain relevance. AI models may prefer "
                        "fresher sources for time-sensitive topics."
                    ),
                })
            else:
                years = age_days / 365
                findings.append({
                    "id": "freshness-stale",
                    "dimension": "content_freshness",
                    "severity": "high" if age_days > 730 else "medium",
                    "confidence": "confirmed" if most_recent["confidence"] == "confirmed" else "likely",
                    "title": f"Content appears stale ({years:.1f} years since last update)",
                    "description": (
                        f"Most recent date: {most_recent['date'][:10]} "
                        f"(source: {most_recent['source']}). Stale content is "
                        "significantly less likely to be cited by AI models. "
                        "Update the content and add a visible 'Last updated' date."
                    ),
                })

        # Check: has published date but no modified date
        if newest_published and not newest_modified:
            findings.append({
                "id": "freshness-no-modified-date",
                "dimension": "content_freshness",
                "severity": "low",
                "confidence": "confirmed",
                "title": "Published date found but no modification date",
                "description": (
                    "The page has a publication date but no last-modified date. "
                    "Adding a visible 'Last updated' date and article:modified_time "
                    "meta tag signals ongoing content maintenance to AI models."
                ),
            })

        # Check: dates only in HTTP headers (not visible)
        visible_sources = {"visible_text", "time_element"}
        has_visible_date = any(d["source"] in visible_sources for d in dates_found)
        if not has_visible_date:
            findings.append({
                "id": "freshness-no-visible-date",
                "dimension": "content_freshness",
                "severity": "low",
                "confidence": "confirmed",
                "title": "No visible date on the page",
                "description": (
                    "Dates were found in metadata or HTTP headers but not in "
                    "visible page content. A visible publication or update date "
                    "helps both users and AI models assess content freshness."
                ),
            })

    grade = to_grade(score)

    date_count = len(dates_found)
    if date_count == 0:
        summary = "No dates detected. Content freshness cannot be assessed."
    else:
        most_recent_date = max(d["date"] for d in dates_found)[:10]
        summary = (
            f"{date_count} date(s) found. Most recent: {most_recent_date}. "
            f"Freshness score: {score}/100."
        )

    return {
        "dimension": "content_freshness",
        "url": page_data.get("url", ""),
        "score": score,
        "grade": grade,
        "summary": summary,
        "dates_found": dates_found,
        "findings": findings,
    }


if __name__ == "__main__":
    if not sys.stdin.isatty():
        try:
            raw = json.load(sys.stdin)
            if "page" in raw:
                page_data = raw["page"]
            else:
                page_data = raw
            print(json.dumps(analyze_freshness(page_data), indent=2, default=str))
            sys.exit(0)
        except (json.JSONDecodeError, KeyError):
            pass

    if len(sys.argv) < 2:
        print("Usage: python3 content_freshness.py <url>")
        print("   or: python3 fetch_page.py <url> full | python3 content_freshness.py")
        sys.exit(1)

    page_data = fetch_page_data(sys.argv[1])
    print(json.dumps(analyze_freshness(page_data), indent=2, default=str))
