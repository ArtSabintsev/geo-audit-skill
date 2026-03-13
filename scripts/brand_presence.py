#!/usr/bin/env python3
"""
Brand presence analyzer for GEO audit.

Checks for brand signals that AI models use to verify identity and authority:
- Social media profiles (10 platforms)
- Review site presence (5 platforms)
- Brand pages (/about, /press, /media, /newsroom, /news)
- Schema.org sameAs links in structured data

Accepts a URL as argument (fetches the page itself) or reads fetch_page.py
JSON from stdin.
"""

import sys
import json
from urllib.parse import urlparse

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

# Social platforms and their URL detection patterns
SOCIAL_PLATFORMS = [
    {"name": "Twitter/X", "patterns": ["twitter.com", "x.com"]},
    {"name": "LinkedIn", "patterns": ["linkedin.com"]},
    {"name": "GitHub", "patterns": ["github.com"]},
    {"name": "YouTube", "patterns": ["youtube.com"]},
    {"name": "Wikipedia", "patterns": ["wikipedia.org"]},
    {"name": "Instagram", "patterns": ["instagram.com"]},
    {"name": "Facebook", "patterns": ["facebook.com"]},
    {"name": "TikTok", "patterns": ["tiktok.com"]},
    {"name": "Reddit", "patterns": ["reddit.com"]},
    {"name": "Crunchbase", "patterns": ["crunchbase.com"]},
]

# Review platforms
REVIEW_PLATFORMS = [
    {"name": "G2", "patterns": ["g2.com"]},
    {"name": "Capterra", "patterns": ["capterra.com"]},
    {"name": "Trustpilot", "patterns": ["trustpilot.com"]},
    {"name": "Product Hunt", "patterns": ["producthunt.com"]},
    {"name": "Yelp", "patterns": ["yelp.com"]},
]

# Brand-related internal page paths
BRAND_PAGES = ["/about", "/press", "/media", "/newsroom", "/news"]


def to_grade(score):
    """Convert numeric score to letter grade."""
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    if score >= 35:
        return "D"
    return "F"


def fetch_page_data(url, timeout=30):
    """Minimal page fetch for standalone usage."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        return {"error": str(e)}

    soup = BeautifulSoup(resp.text, "lxml")
    base_domain = urlparse(url).netloc

    internal_links = []
    external_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        link_text = a.get_text(strip=True)
        try:
            parsed = urlparse(href)
            if parsed.netloc == base_domain or (not parsed.netloc and href.startswith("/")):
                internal_links.append({"url": href, "text": link_text})
            elif parsed.scheme in ("http", "https"):
                external_links.append({"url": href, "text": link_text})
        except Exception:
            pass

    structured_data = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            structured_data.append(json.loads(script.string))
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "url": url,
        "internal_links": internal_links,
        "external_links": external_links,
        "structured_data": structured_data,
    }


def analyze_brand_presence(page_data):
    """
    Analyze brand presence signals.

    page_data must have: external_links, internal_links, structured_data
    """
    if "error" in page_data:
        return {"error": page_data["error"]}

    findings = []
    external_urls = [
        link.get("url", "").lower() for link in page_data.get("external_links", [])
    ]
    internal_paths = []
    for link in page_data.get("internal_links", []):
        link_url = link.get("url", "")
        try:
            if "://" in link_url:
                internal_paths.append(urlparse(link_url).path.lower())
            else:
                internal_paths.append(link_url.lower())
        except Exception:
            pass

    # --- Social platform presence ---
    found_socials = []
    missing_socials = []

    for platform in SOCIAL_PLATFORMS:
        found = any(
            any(p in url for p in platform["patterns"])
            for url in external_urls
        )
        if found:
            found_socials.append(platform["name"])
        else:
            missing_socials.append(platform["name"])

    if found_socials:
        findings.append({
            "id": "brand-social-found",
            "dimension": "brand_presence",
            "severity": "pass",
            "title": f"Social profiles linked: {', '.join(found_socials)}",
            "description": (
                f"Found links to {len(found_socials)} social platform"
                f"{'s' if len(found_socials) != 1 else ''}. "
                "Social profiles help AI models verify your brand identity "
                "and extract consistent information."
            ),
        })

    if missing_socials:
        sev = "high" if not found_socials else "medium"
        findings.append({
            "id": "brand-social-missing",
            "dimension": "brand_presence",
            "severity": sev,
            "title": f"Missing social profile links: {', '.join(missing_socials)}",
            "description": (
                f"No links found to {', '.join(missing_socials)}. Adding links "
                "to active social profiles helps AI models build a complete "
                "picture of your brand."
            ),
        })

    # --- Review platform presence ---
    found_reviews = []
    missing_reviews = []

    for platform in REVIEW_PLATFORMS:
        found = any(
            any(p in url for p in platform["patterns"])
            for url in external_urls
        )
        if found:
            found_reviews.append(platform["name"])
        else:
            missing_reviews.append(platform["name"])

    if found_reviews:
        findings.append({
            "id": "brand-reviews-found",
            "dimension": "brand_presence",
            "severity": "pass",
            "title": f"Review platforms linked: {', '.join(found_reviews)}",
            "description": (
                f"Found links to {len(found_reviews)} review platform"
                f"{'s' if len(found_reviews) != 1 else ''}. "
                "Third-party reviews boost trust signals for AI models."
            ),
        })

    if len(missing_reviews) == len(REVIEW_PLATFORMS):
        names = ", ".join(p["name"] for p in REVIEW_PLATFORMS)
        findings.append({
            "id": "brand-reviews-missing",
            "dimension": "brand_presence",
            "severity": "medium",
            "title": "No review platform links found",
            "description": (
                f"No links to review platforms ({names}). Third-party reviews "
                "help AI models assess your brand's reputation and trustworthiness."
            ),
        })

    # --- Brand pages ---
    found_brand_pages = []
    for page in BRAND_PAGES:
        found = any(
            path == page or path == page + "/" or path.startswith(page + "/")
            for path in internal_paths
        )
        if found:
            found_brand_pages.append(page)

    if found_brand_pages:
        findings.append({
            "id": "brand-pages-found",
            "dimension": "brand_presence",
            "severity": "pass",
            "title": f"Brand pages found: {', '.join(found_brand_pages)}",
            "description": (
                f"Found internal links to {len(found_brand_pages)} brand-related page"
                f"{'s' if len(found_brand_pages) != 1 else ''}. "
                "These pages provide AI models with context about your organization."
            ),
        })

    if "/about" not in found_brand_pages:
        findings.append({
            "id": "brand-no-about",
            "dimension": "brand_presence",
            "severity": "medium",
            "title": "No link to About page",
            "description": (
                "No internal link to an /about page was found. An about page "
                "is a primary source for AI models to learn about your organization."
            ),
        })

    press_pages = {"/press", "/media", "/newsroom", "/news"}
    if not press_pages.intersection(found_brand_pages):
        findings.append({
            "id": "brand-no-press",
            "dimension": "brand_presence",
            "severity": "low",
            "title": "No press/media page linked",
            "description": (
                "No internal link to a press or media page was found. "
                "Press coverage helps AI models view your brand as noteworthy."
            ),
        })

    # --- Schema.org sameAs ---
    has_same_as = False
    for item in page_data.get("structured_data", []):
        if item and isinstance(item, dict):
            entries = item.get("@graph", [item]) if isinstance(item.get("@graph"), list) else [item]
            for entry in entries:
                if isinstance(entry, dict):
                    same_as = entry.get("sameAs")
                    if isinstance(same_as, list) and len(same_as) > 0:
                        has_same_as = True
                        break
                    elif isinstance(same_as, str) and same_as:
                        has_same_as = True
                        break
        if has_same_as:
            break

    if has_same_as:
        findings.append({
            "id": "brand-sameas-found",
            "dimension": "brand_presence",
            "severity": "pass",
            "title": "Schema.org sameAs links found",
            "description": (
                "Your structured data includes sameAs links, helping AI models "
                "connect your site to your profiles on other platforms."
            ),
        })
    elif found_socials:
        findings.append({
            "id": "brand-sameas-missing",
            "dimension": "brand_presence",
            "severity": "medium",
            "title": "No Schema.org sameAs links in structured data",
            "description": (
                'You link to social profiles but your JSON-LD structured data is '
                'missing "sameAs" links. Adding sameAs to your Organization schema '
                'helps AI models verify your brand across platforms.'
            ),
        })

    # --- Calculate score ---
    score = 0

    # Social presence: up to 35 points (exclude Wikipedia from ratio)
    socials_without_wiki = [s for s in found_socials if s != "Wikipedia"]
    social_platforms_without_wiki = len(SOCIAL_PLATFORMS) - 1
    social_ratio = len(socials_without_wiki) / social_platforms_without_wiki if social_platforms_without_wiki else 0
    score += round(social_ratio * 35)

    # Review presence: up to 25 points
    review_ratio = len(found_reviews) / len(REVIEW_PLATFORMS) if REVIEW_PLATFORMS else 0
    score += round(review_ratio * 25)

    # Brand pages: up to 20 points
    brand_page_ratio = len(found_brand_pages) / len(BRAND_PAGES) if BRAND_PAGES else 0
    score += round(brand_page_ratio * 20)

    # Bonus for Wikipedia (strong brand signal): 10 points
    if "Wikipedia" in found_socials:
        score += 10

    # Bonus for sameAs in structured data: 5 points
    if has_same_as:
        score += 5

    # Base points for having any external presence: 5 points
    if found_socials:
        score += 5

    score = max(0, min(100, score))
    grade = to_grade(score)

    total_signals = len(found_socials) + len(found_reviews) + len(found_brand_pages)
    if total_signals == 0:
        summary = "No brand presence signals found. AI models have little external context to verify your brand."
    else:
        summary = (
            f"Found {total_signals} brand signal{'s' if total_signals != 1 else ''}: "
            f"{len(found_socials)} social, {len(found_reviews)} review, "
            f"{len(found_brand_pages)} brand page{'s' if len(found_brand_pages) != 1 else ''}."
        )

    return {
        "dimension": "brand_presence",
        "url": page_data.get("url", ""),
        "score": score,
        "grade": grade,
        "summary": summary,
        "found_socials": found_socials,
        "missing_socials": missing_socials,
        "found_reviews": found_reviews,
        "found_brand_pages": found_brand_pages,
        "has_same_as": has_same_as,
        "findings": findings,
    }


if __name__ == "__main__":
    # If stdin has data, read it as JSON from fetch_page.py
    if not sys.stdin.isatty():
        try:
            raw = json.load(sys.stdin)
            if "page" in raw:
                page_data = raw["page"]
            else:
                page_data = raw
            print(json.dumps(analyze_brand_presence(page_data), indent=2, default=str))
            sys.exit(0)
        except (json.JSONDecodeError, KeyError):
            pass

    if len(sys.argv) < 2:
        print("Usage: python3 brand_presence.py <url>")
        print("   or: python3 fetch_page.py <url> full | python3 brand_presence.py")
        sys.exit(1)

    page_data = fetch_page_data(sys.argv[1])
    print(json.dumps(analyze_brand_presence(page_data), indent=2, default=str))
