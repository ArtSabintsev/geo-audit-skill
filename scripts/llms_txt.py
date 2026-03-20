#!/usr/bin/env python3
"""
llms.txt quality scorer for GEO audit.

Checks llms.txt and llms-full.txt for quality and spec compliance:
- Existence
- Minimum content length (100 chars)
- Markdown structure (# title, > description, ## sections)
- Key pages section
- About section
- Markdown link format [label](url)
- llms-full.txt bonus

Accepts a URL as argument (fetches llms.txt itself) or reads fetch_page.py
JSON from stdin (expecting the "llms" key from full mode).
"""

import sys
import json
import re
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("ERROR: Missing dependencies. Run: pip install requests")
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


def fetch_llms_data(url, timeout=15):
    """Fetch llms.txt and llms-full.txt for standalone usage."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    result = {
        "llms_txt": {"url": f"{base}/llms.txt", "exists": False, "content": ""},
        "llms_full_txt": {"url": f"{base}/llms-full.txt", "exists": False, "content": ""},
        "errors": [],
    }

    for key, path in [("llms_txt", "/llms.txt"), ("llms_full_txt", "/llms-full.txt")]:
        try:
            resp = requests.get(f"{base}{path}", headers=HEADERS, timeout=timeout)
            if resp.status_code == 200 and not resp.headers.get(
                "content-type", ""
            ).startswith("text/html"):
                result[key]["exists"] = True
                result[key]["content"] = resp.text
        except Exception as e:
            result["errors"].append(f"Error checking {path}: {e}")

    return result


def fetch_rsl_data(url, timeout=15):
    """Fetch /.well-known/rsl.json for RSL 1.0 licensing check."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    rsl_url = f"{base}/.well-known/rsl.json"

    result = {"url": rsl_url, "exists": False, "content": ""}

    try:
        resp = requests.get(rsl_url, headers=HEADERS, timeout=timeout)
        if resp.status_code == 200:
            result["exists"] = True
            result["content"] = resp.text
    except Exception:
        pass

    return result


def analyze_llms_txt(llms_data, page_data=None, rsl_data=None):
    """
    Score llms.txt quality and spec compliance.

    llms_data must have: llms_txt.exists, llms_txt.content, llms_full_txt.exists
    page_data (optional) is used to generate a draft if llms.txt is missing.
    """
    findings = []
    score = 0

    has_llms_txt = llms_data.get("llms_txt", {}).get("exists", False)
    has_llms_full_txt = llms_data.get("llms_full_txt", {}).get("exists", False)
    content = llms_data.get("llms_txt", {}).get("content", "")

    if not has_llms_txt and not has_llms_full_txt:
        # Neither file exists
        score = 0
        findings.append({
            "id": "llms-txt-missing",
            "dimension": "llms_txt",
            "severity": "critical",
            "title": "No llms.txt file found",
            "description": (
                "Your site does not have an llms.txt file. This file helps AI "
                "models understand your site's purpose, key pages, and how to "
                "represent your content accurately. It is the robots.txt "
                "equivalent for AI comprehension."
            ),
        })

    elif has_llms_txt:
        # Check quality of llms.txt
        if len(content) < 100:
            score = 30
            findings.append({
                "id": "llms-txt-minimal",
                "dimension": "llms_txt",
                "severity": "high",
                "title": "llms.txt is too short",
                "description": (
                    f"Your llms.txt is only {len(content)} characters long. "
                    "A useful llms.txt should include a site description, key "
                    "pages, and structured sections to guide AI models."
                ),
            })
        else:
            # Check for section headings (## style)
            has_sections = bool(re.search(r"^##\s+", content, re.MULTILINE))
            has_title = bool(re.search(r"^#\s+", content, re.MULTILINE))
            has_description = bool(re.search(r"^>", content, re.MULTILINE))
            has_links = bool(re.search(r"https?://", content, re.MULTILINE))
            has_markdown_links = bool(re.search(r"\[.+?\]\(.+?\)", content))

            if has_sections:
                score = 60

                # Count section headings
                section_count = len(re.findall(r"^##\s+", content, re.MULTILINE))
                if section_count >= 3:
                    score = 70

                # Check for key pages section
                has_key_pages = bool(re.search(
                    r"key\s*pages?|important\s*pages?|main\s*pages?", content, re.I
                ))
                if has_key_pages and has_links:
                    score = 80

                # Check for about section
                has_about = bool(re.search(
                    r"about|overview|description", content, re.I
                ))
                if has_about and has_title and has_description:
                    score = max(score, 85)

                # Bonus for following spec closely
                if has_title and has_description and has_markdown_links:
                    score = max(score, 90)
            else:
                # Has content but no structure
                score = 40
                findings.append({
                    "id": "llms-txt-no-structure",
                    "dimension": "llms_txt",
                    "severity": "medium",
                    "title": "llms.txt lacks section structure",
                    "description": (
                        "Your llms.txt does not use ## headings to organize "
                        "content. The llms.txt specification uses markdown with "
                        "# for title, > for description, and ## for sections."
                    ),
                })

            # Check for common spec compliance issues
            if not has_title:
                score = max(score - 10, 0)
                findings.append({
                    "id": "llms-txt-no-title",
                    "dimension": "llms_txt",
                    "severity": "medium",
                    "title": "llms.txt missing title heading",
                    "description": (
                        "The llms.txt file should start with a # title heading "
                        "per the specification. This is the first thing AI models "
                        "read to understand your site."
                    ),
                })

            if not has_description and len(content) > 200:
                findings.append({
                    "id": "llms-txt-no-description",
                    "dimension": "llms_txt",
                    "severity": "low",
                    "title": "llms.txt missing blockquote description",
                    "description": (
                        "The llms.txt specification recommends a > blockquote "
                        "description after the title to provide a brief site summary."
                    ),
                })

            if has_links and not has_markdown_links:
                findings.append({
                    "id": "llms-txt-raw-links",
                    "dimension": "llms_txt",
                    "severity": "low",
                    "title": "Links in llms.txt are not in markdown format",
                    "description": (
                        "The llms.txt specification recommends using markdown link "
                        "format [Label](URL) instead of raw URLs, so AI models "
                        "have context for each link."
                    ),
                })

        # Bonus for llms-full.txt
        if has_llms_full_txt:
            score = min(100, score + 20)
            findings.append({
                "id": "llms-full-txt-found",
                "dimension": "llms_txt",
                "severity": "pass",
                "title": "llms-full.txt is present",
                "description": (
                    "Your site provides an llms-full.txt file for extended content. "
                    "This gives AI models comprehensive context about your site."
                ),
            })
        elif score >= 60:
            findings.append({
                "id": "llms-full-txt-missing",
                "dimension": "llms_txt",
                "severity": "low",
                "title": "Consider adding llms-full.txt",
                "description": (
                    "An llms-full.txt file provides extended detail beyond the "
                    "summary in llms.txt. This is recommended for sites with "
                    "complex product offerings or extensive documentation."
                ),
            })

    # RSL 1.0 licensing check
    if rsl_data is not None:
        if rsl_data.get("exists"):
            score = min(100, score + 5)
            findings.append({
                "id": "llms-rsl-found",
                "dimension": "llms_txt",
                "severity": "pass",
                "title": "RSL 1.0 licensing file found",
                "description": (
                    "Your site provides a /.well-known/rsl.json file. "
                    "RSL 1.0 (Really Simple Licensing) is a machine-readable AI "
                    "licensing standard backed by Reddit, Yahoo, Medium, Quora, "
                    "Cloudflare, Akamai, and Creative Commons. It tells AI systems "
                    "how they are permitted to use your content."
                ),
                "confidence": "confirmed",
            })
        else:
            findings.append({
                "id": "llms-rsl-missing",
                "dimension": "llms_txt",
                "severity": "low",
                "title": "No RSL 1.0 licensing file",
                "description": (
                    "Consider adding a /.well-known/rsl.json file. RSL 1.0 "
                    "(Really Simple Licensing) is a machine-readable AI licensing "
                    "standard backed by Reddit, Yahoo, Medium, and others. It lets "
                    "you specify how AI systems can use your content."
                ),
                "confidence": "confirmed",
            })

    # Add confidence labels
    for f in findings:
        f["confidence"] = "confirmed"

    score = max(0, min(100, score))
    grade = to_grade(score)

    if not has_llms_txt:
        summary = "No llms.txt file found. AI models have no structured guide to your site content."
    elif score >= 80:
        extra = " with llms-full.txt companion." if has_llms_full_txt else "."
        summary = f"Well-structured llms.txt found{extra}"
    elif score >= 50:
        summary = "llms.txt exists but could be improved with better structure and more detail."
    else:
        summary = "llms.txt exists but is minimal or poorly structured."

    return {
        "dimension": "llms_txt",
        "url": llms_data.get("llms_txt", {}).get("url", ""),
        "score": score,
        "grade": grade,
        "summary": summary,
        "has_llms_txt": has_llms_txt,
        "has_llms_full_txt": has_llms_full_txt,
        "content_length": len(content),
        "findings": findings,
    }


if __name__ == "__main__":
    # If stdin has data, read it as JSON from fetch_page.py
    if not sys.stdin.isatty():
        try:
            raw = json.load(sys.stdin)
            # Handle full mode output (has "llms" key)
            if "llms" in raw:
                llms_data = raw["llms"]
                page_data = raw.get("page")
            elif "llms_txt" in raw:
                # Direct llms data
                llms_data = raw
                page_data = None
            else:
                llms_data = raw
                page_data = None
            rsl_data = raw.get("rsl")
            print(json.dumps(
                analyze_llms_txt(llms_data, page_data, rsl_data=rsl_data), indent=2, default=str
            ))
            sys.exit(0)
        except (json.JSONDecodeError, KeyError):
            pass

    if len(sys.argv) < 2:
        print("Usage: python3 llms_txt.py <url>")
        print("   or: python3 fetch_page.py <url> full | python3 llms_txt.py")
        sys.exit(1)

    llms_data = fetch_llms_data(sys.argv[1])
    rsl_data = fetch_rsl_data(sys.argv[1])
    print(json.dumps(analyze_llms_txt(llms_data, rsl_data=rsl_data), indent=2, default=str))
