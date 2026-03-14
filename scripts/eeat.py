#!/usr/bin/env python3
"""
E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) analyzer.

Evaluates 9 signals that AI models use to assess content authority:
1. Author bylines
2. Publication/update dates
3. Citation language
4. Credentials
5. Contact information
6. About page link
7. Trust indicators
8. First-party expertise
9. Schema.org authorship

Accepts a URL as argument (fetches the page itself) or reads fetch_page.py
JSON from stdin.
"""

import sys
import json
import re
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
    """Minimal page fetch for standalone usage. Returns dict with needed fields."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        return {"error": str(e)}

    soup = BeautifulSoup(resp.text, "lxml")

    # Strip non-content elements for text extraction
    raw_soup = BeautifulSoup(resp.text, "lxml")

    # Text content (strip boilerplate)
    for el in soup.find_all(["script", "style", "nav", "footer", "header"]):
        el.decompose()
    text_content = soup.get_text(separator=" ", strip=True)

    # Internal links
    base_domain = urlparse(url).netloc
    internal_links = []
    for a in raw_soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/") or base_domain in href:
            internal_links.append({"url": href, "text": a.get_text(strip=True)})

    # Structured data
    structured_data = []
    for script in raw_soup.find_all("script", type="application/ld+json"):
        try:
            structured_data.append(json.loads(script.string))
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "url": url,
        "text_content": text_content,
        "internal_links": internal_links,
        "structured_data": structured_data,
    }


def analyze_eeat(page_data):
    """
    Analyze E-E-A-T signals in page data.

    page_data must have: text_content, internal_links, structured_data
    """
    if "error" in page_data:
        return {"error": page_data["error"]}

    text = page_data.get("text_content", "")
    internal_links = page_data.get("internal_links", [])
    structured_data = page_data.get("structured_data", [])

    findings = []
    signals = []

    # --- 1. Author bylines ---
    author_patterns = [
        r"\bby\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+",
        r"\bwritten\s+by\s+[A-Z][a-z]+",
        r"\bauthor:\s*[A-Z][a-z]+",
        r"\bposted\s+by\s+[A-Z][a-z]+",
    ]
    has_author = any(re.search(p, text, re.I) for p in author_patterns)
    signals.append({
        "name": "Author byline",
        "found": has_author,
        "weight": 15,
        "detail": (
            "Author attribution found on the page."
            if has_author else
            "No author byline detected. AI models favor content with clear author attribution."
        ),
    })

    # --- 2. Publication/update dates ---
    date_patterns = [
        r"\b(?:published|posted|updated|modified|date)\s*[:]\s*\w+",
        r"\b(?:published|posted|updated)\s+(?:on\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
    ]
    has_date = any(re.search(p, text, re.I) for p in date_patterns)
    signals.append({
        "name": "Publication date",
        "found": has_date,
        "weight": 12,
        "detail": (
            "Publication or update date found."
            if has_date else
            "No publication or update date detected. Dated content signals freshness and reliability."
        ),
    })

    # --- 3. Citation language ---
    citation_patterns = [
        r"\baccording\s+to\b",
        r"\bresearch\s+(?:shows?|suggests?|indicates?|finds?|found)\b",
        r"\bstudies?\s+(?:show|suggest|indicate|find|found|reveal)\b",
        r"\bdata\s+(?:shows?|suggests?|indicates?)\b",
        r"\b(?:source|cited|reference|bibliography)\b",
        r"\[\d+\]",
    ]
    has_citations = any(re.search(p, text, re.I) for p in citation_patterns)
    signals.append({
        "name": "Citation language",
        "found": has_citations,
        "weight": 12,
        "detail": (
            "Citation or research language detected."
            if has_citations else
            "No citation language found. Referencing sources increases perceived expertise."
        ),
    })

    # --- 4. Credential patterns ---
    credential_patterns = [
        r"\b(?:CEO|CTO|CFO|COO|CMO|VP|Director|Manager|Lead|Head\s+of)\b",
        r"\b(?:founder|co-founder|co founder)\b",
        r"\b\d+\+?\s*years?\s+(?:of\s+)?experience\b",
        r"\b(?:certified|certification|licensed|accredited|Ph\.?D|M\.?D|MBA|CPA)\b",
        r"\b(?:expert|specialist|professional|consultant)\b",
    ]
    has_credentials = any(re.search(p, text, re.I) for p in credential_patterns)
    signals.append({
        "name": "Credentials",
        "found": has_credentials,
        "weight": 12,
        "detail": (
            "Professional credentials or experience signals found."
            if has_credentials else
            "No credential signals detected. Showing expertise builds trust with AI models."
        ),
    })

    # --- 5. Contact information ---
    has_email = bool(re.search(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text
    ))
    has_phone = bool(re.search(
        r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text
    ))
    has_contact = has_email or has_phone
    contact_parts = []
    if has_email:
        contact_parts.append("email")
    if has_phone:
        contact_parts.append("phone")
    signals.append({
        "name": "Contact information",
        "found": has_contact,
        "weight": 10,
        "detail": (
            f"Contact information found ({', '.join(contact_parts)})."
            if has_contact else
            "No contact information detected. Visible contact info signals trustworthiness."
        ),
    })

    # --- 6. About page link ---
    has_about_link = False
    for link in internal_links:
        link_url = link.get("url", "")
        try:
            path = urlparse(link_url).pathname.lower() if "://" in link_url else link_url.lower()
        except Exception:
            path = link_url.lower()
        if path in ("/about", "/about-us", "/about/") or path.startswith("/about/"):
            has_about_link = True
            break
    signals.append({
        "name": "About page link",
        "found": has_about_link,
        "weight": 10,
        "detail": (
            "Link to an about page found."
            if has_about_link else
            "No link to an about page detected. An about page helps AI models understand who is behind the content."
        ),
    })

    # --- 7. Trust indicators ---
    trust_patterns = [
        r"\b(?:privacy\s+policy|terms\s+of\s+service|terms\s+and\s+conditions)\b",
        r"\b(?:guarantee|warranty|refund|money.back)\b",
        r"\b(?:award|recognized|featured\s+in|as\s+seen\s+on)\b",
        r"\b(?:testimonial|review|case\s+study)\b",
    ]
    has_trust = any(re.search(p, text, re.I) for p in trust_patterns)
    signals.append({
        "name": "Trust indicators",
        "found": has_trust,
        "weight": 10,
        "detail": (
            "Trust indicators found (policies, awards, testimonials, etc.)."
            if has_trust else
            "No trust indicators detected. Social proof and policies build credibility."
        ),
    })

    # --- 8. First-party expertise ---
    expertise_patterns = [
        r"\bwe\s+(?:built|created|developed|designed|researched|tested|analyzed)\b",
        r"\bour\s+(?:team|experts?|engineers?|researchers?)\b",
        r"\bin\s+our\s+experience\b",
        r"\bwe(?:'ve|\s+have)\s+(?:found|seen|observed|worked\s+with)\b",
    ]
    has_expertise = any(re.search(p, text, re.I) for p in expertise_patterns)
    signals.append({
        "name": "First-party expertise",
        "found": has_expertise,
        "weight": 9,
        "detail": (
            "First-party expertise language detected."
            if has_expertise else
            "No first-party expertise language found. Demonstrating direct experience strengthens E-E-A-T signals."
        ),
    })

    # --- 9. Structured data authorship ---
    has_schema_author = False
    for item in structured_data:
        if item and isinstance(item, dict):
            entries = item.get("@graph", [item]) if isinstance(item.get("@graph"), list) else [item]
            for entry in entries:
                if isinstance(entry, dict) and (
                    entry.get("author") or entry.get("publisher") or entry.get("creator")
                ):
                    has_schema_author = True
                    break
        if has_schema_author:
            break
    signals.append({
        "name": "Schema.org authorship",
        "found": has_schema_author,
        "weight": 10,
        "detail": (
            "Structured data includes author/publisher information, helping AI models attribute content."
            if has_schema_author else
            "No author or publisher found in structured data. Adding author/publisher to JSON-LD helps AI models verify content provenance."
        ),
    })

    # --- Calculate score ---
    total_weight = sum(s["weight"] for s in signals)
    earned_weight = sum(s["weight"] for s in signals if s["found"])
    score = round((earned_weight / total_weight) * 100) if total_weight else 0

    # Generate findings
    for signal in signals:
        severity_map = {True: "pass"}
        if not signal["found"]:
            if signal["weight"] >= 15:
                sev = "high"
            elif signal["weight"] >= 12:
                sev = "medium"
            else:
                sev = "low"
        else:
            sev = "pass"

        slug = signal["name"].lower().replace(" ", "-").replace(".", "")
        findings.append({
            "id": f"eeat-{'found' if signal['found'] else 'missing'}-{slug}",
            "dimension": "eeat",
            "severity": sev,
            "title": f"{'E-E-A-T signal present' if signal['found'] else 'Missing E-E-A-T signal'}: {signal['name']}",
            "description": signal["detail"],
        })

    # Add confidence labels
    for f in findings:
        if any(s in f["id"] for s in ("contact-information", "about-page-link", "schemaorg-authorship")):
            f["confidence"] = "confirmed"
        else:
            f["confidence"] = "likely"

    grade = to_grade(score)
    found_count = sum(1 for s in signals if s["found"])
    total_count = len(signals)

    if score >= 65:
        summary_suffix = "Good expertise and trust signals for AI models."
    elif score >= 35:
        summary_suffix = "Some expertise signals found, but significant gaps remain."
    else:
        summary_suffix = "Weak E-E-A-T signals. AI models may not view this content as authoritative."

    summary = f"{found_count}/{total_count} E-E-A-T signals detected. {summary_suffix}"

    return {
        "dimension": "eeat",
        "url": page_data.get("url", ""),
        "score": score,
        "grade": grade,
        "summary": summary,
        "signals": signals,
        "findings": findings,
    }


if __name__ == "__main__":
    # If stdin has data, read it as JSON from fetch_page.py
    if not sys.stdin.isatty():
        try:
            raw = json.load(sys.stdin)
            # Handle both "full" mode (nested under "page") and direct page data
            if "page" in raw:
                page_data = raw["page"]
            else:
                page_data = raw
            print(json.dumps(analyze_eeat(page_data), indent=2, default=str))
            sys.exit(0)
        except (json.JSONDecodeError, KeyError):
            pass  # Fall through to URL mode

    if len(sys.argv) < 2:
        print("Usage: python3 eeat.py <url>")
        print("   or: python3 fetch_page.py <url> full | python3 eeat.py")
        sys.exit(1)

    page_data = fetch_page_data(sys.argv[1])
    print(json.dumps(analyze_eeat(page_data), indent=2, default=str))
