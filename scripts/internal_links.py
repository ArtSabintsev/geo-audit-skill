#!/usr/bin/env python3
"""
Internal link structure analyzer for GEO audit.

Analyzes the internal linking patterns of a page to assess:
  - Link density: are there enough internal links for the content length?
  - Anchor text quality: descriptive vs generic ("click here")
  - Orphan risk: sections of content with no outgoing links
  - Hub pattern: does the page link to related content?
  - Sitemap coverage: how many sitemap pages are linked from this page?

Accepts a URL as argument or reads fetch_page.py JSON from stdin.
"""

import sys
import json
import re
from urllib.parse import urlparse, urljoin
from collections import Counter

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

GENERIC_ANCHORS = {
    "click here", "here", "read more", "learn more", "more",
    "link", "this", "see more", "details", "go", "click",
    "continue", "next", "previous", "view", "visit",
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


def fetch_page_data(url, timeout=30):
    """Minimal page fetch for standalone usage."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        return {"error": str(e)}

    soup = BeautifulSoup(resp.text, "lxml")
    raw_soup = BeautifulSoup(resp.text, "lxml")

    base_domain = urlparse(url).netloc

    heading_structure = []
    for level in range(1, 7):
        for h in raw_soup.find_all(f"h{level}"):
            heading_structure.append({"level": level, "text": h.get_text(strip=True)})

    internal_links = []
    external_links = []
    for a in raw_soup.find_all("a", href=True):
        href = urljoin(url, a["href"])
        link_text = a.get_text(strip=True)
        parsed = urlparse(href)
        if parsed.netloc == base_domain:
            internal_links.append({"url": href, "text": link_text})
        elif parsed.scheme in ("http", "https"):
            external_links.append({"url": href, "text": link_text})

    for el in soup.find_all(["script", "style", "nav", "footer", "header"]):
        el.decompose()
    text_content = soup.get_text(separator=" ", strip=True)

    return {
        "url": url,
        "word_count": len(text_content.split()),
        "heading_structure": heading_structure,
        "internal_links": internal_links,
        "external_links": external_links,
        "text_content": text_content,
    }


def analyze_internal_links(page_data, sitemap_pages=None):
    """Analyze internal link structure of a page."""
    if "error" in page_data:
        return {"error": page_data["error"]}

    findings = []
    internal_links = page_data.get("internal_links", [])
    external_links = page_data.get("external_links", [])
    word_count = page_data.get("word_count", 0)
    headings = page_data.get("heading_structure", [])
    url = page_data.get("url", "")

    total_internal = len(internal_links)
    total_external = len(external_links)
    total_links = total_internal + total_external

    # Deduplicate internal links by URL
    unique_internal_urls = set()
    unique_internal = []
    for link in internal_links:
        normalized = link["url"].rstrip("/").lower()
        if normalized not in unique_internal_urls:
            unique_internal_urls.add(normalized)
            unique_internal.append(link)

    unique_count = len(unique_internal)

    # --- 1. Link density ---
    if word_count > 0:
        links_per_1000_words = round((total_internal / word_count) * 1000, 1)
    else:
        links_per_1000_words = 0

    density_score = 0
    if word_count >= 300:
        if total_internal == 0:
            findings.append({
                "id": "links-no-internal",
                "dimension": "internal_links",
                "severity": "high",
                "confidence": "confirmed",
                "title": "No internal links found in page content",
                "description": (
                    f"This {word_count}-word page has zero internal links. "
                    "Internal links help AI crawlers discover and understand the "
                    "relationship between your pages. Add links to related content."
                ),
            })
        elif total_internal < 3:
            findings.append({
                "id": "links-too-few",
                "dimension": "internal_links",
                "severity": "medium",
                "confidence": "confirmed",
                "title": f"Very few internal links ({total_internal} found)",
                "description": (
                    f"Only {total_internal} internal link(s) on a {word_count}-word page. "
                    "Content pages should have at least 3-5 contextual internal links "
                    "to related pages. This helps AI models understand your site's "
                    "topical structure."
                ),
            })
            density_score = 10
        elif links_per_1000_words < 5:
            findings.append({
                "id": "links-low-density",
                "dimension": "internal_links",
                "severity": "low",
                "confidence": "likely",
                "title": f"Low internal link density ({links_per_1000_words} per 1000 words)",
                "description": (
                    f"{total_internal} internal links in {word_count} words. "
                    "Aim for 5-15 internal links per 1000 words to create a "
                    "well-connected content network."
                ),
            })
            density_score = 20
        elif links_per_1000_words <= 30:
            density_score = 30
            findings.append({
                "id": "links-good-density",
                "dimension": "internal_links",
                "severity": "pass",
                "confidence": "confirmed",
                "title": f"Good internal link density ({links_per_1000_words} per 1000 words)",
                "description": (
                    f"{total_internal} internal links in {word_count} words — "
                    "well-connected for AI crawlers."
                ),
            })
        else:
            density_score = 20
            findings.append({
                "id": "links-excessive-density",
                "dimension": "internal_links",
                "severity": "low",
                "confidence": "likely",
                "title": f"Very high link density ({links_per_1000_words} per 1000 words)",
                "description": (
                    f"{total_internal} internal links in {word_count} words may "
                    "dilute link equity. Consider whether all links add genuine value."
                ),
            })
    else:
        density_score = 15  # short pages get a pass

    # --- 2. Anchor text quality ---
    anchor_texts = [l.get("text", "").strip().lower() for l in internal_links if l.get("text", "").strip()]
    generic_count = sum(1 for a in anchor_texts if a in GENERIC_ANCHORS)
    empty_count = sum(1 for l in internal_links if not l.get("text", "").strip())

    anchor_score = 0
    if total_internal > 0:
        generic_ratio = (generic_count + empty_count) / total_internal
        if generic_ratio > 0.5:
            findings.append({
                "id": "links-generic-anchors",
                "dimension": "internal_links",
                "severity": "medium",
                "confidence": "confirmed",
                "title": f"Over half of internal links use generic anchor text",
                "description": (
                    f"{generic_count} generic ('click here', 'read more') and "
                    f"{empty_count} empty anchor texts out of {total_internal} "
                    "internal links. Descriptive anchor text helps AI models "
                    "understand what the linked page is about before following the link."
                ),
            })
        elif generic_ratio > 0.25:
            findings.append({
                "id": "links-some-generic-anchors",
                "dimension": "internal_links",
                "severity": "low",
                "confidence": "confirmed",
                "title": f"{generic_count + empty_count} internal links have generic or empty anchor text",
                "description": (
                    "Some internal links use non-descriptive anchor text. "
                    "Replace 'click here' and 'read more' with descriptive "
                    "text that describes the linked content."
                ),
            })
            anchor_score = 15
        else:
            anchor_score = 25
            findings.append({
                "id": "links-good-anchors",
                "dimension": "internal_links",
                "severity": "pass",
                "confidence": "confirmed",
                "title": "Internal links use descriptive anchor text",
                "description": (
                    "Most internal links have descriptive, contextual anchor text "
                    "that helps AI models understand page relationships."
                ),
            })
    else:
        anchor_score = 0

    # --- 3. Link diversity (unique destinations) ---
    diversity_score = 0
    if total_internal > 0:
        diversity_ratio = unique_count / total_internal
        if diversity_ratio < 0.3 and total_internal > 5:
            findings.append({
                "id": "links-low-diversity",
                "dimension": "internal_links",
                "severity": "low",
                "confidence": "confirmed",
                "title": f"Many duplicate internal link destinations ({unique_count} unique of {total_internal})",
                "description": (
                    "Multiple links point to the same pages. While some repetition "
                    "is normal (e.g., navigation), diversifying link targets helps "
                    "AI crawlers discover more of your content."
                ),
            })
            diversity_score = 5
        else:
            diversity_score = 15
    else:
        diversity_score = 0

    # --- 4. Hub pattern detection ---
    hub_score = 0
    link_paths = [urlparse(l["url"]).path for l in unique_internal]

    # Check if links go to related content sections (same path prefix)
    parsed_url = urlparse(url)
    current_path = parsed_url.path.rstrip("/")
    path_parts = current_path.split("/")

    if len(path_parts) >= 2:
        path_prefix = "/".join(path_parts[:2])
        related_links = sum(1 for p in link_paths if p.startswith(path_prefix) and p != current_path)
        if related_links >= 3:
            hub_score = 15
            findings.append({
                "id": "links-hub-pattern",
                "dimension": "internal_links",
                "severity": "pass",
                "confidence": "likely",
                "title": f"Hub pattern detected ({related_links} links to related content)",
                "description": (
                    f"This page links to {related_links} pages under the same "
                    f"content section ({path_prefix}/...). This hub-and-spoke "
                    "pattern signals topical authority to AI models."
                ),
            })
        elif unique_count >= 3 and related_links == 0 and current_path not in ("", "/"):
            findings.append({
                "id": "links-no-hub-pattern",
                "dimension": "internal_links",
                "severity": "low",
                "confidence": "hypothesis",
                "title": "No hub pattern — links don't connect to same-section content",
                "description": (
                    "This page links to various parts of the site but not to "
                    "related pages in the same content section. Linking to "
                    "topically related pages creates a hub-and-spoke pattern "
                    "that strengthens topical authority for AI models."
                ),
            })
            hub_score = 5
        else:
            hub_score = 10
    else:
        hub_score = 10  # homepage gets neutral score

    # --- 5. Sitemap coverage ---
    sitemap_score = 0
    if sitemap_pages and len(sitemap_pages) > 1:
        sitemap_set = set(p.rstrip("/").lower() for p in sitemap_pages)
        linked_set = set(u.rstrip("/").lower() for u in unique_internal_urls)
        covered = linked_set & sitemap_set
        coverage = len(covered) / len(sitemap_set) if sitemap_set else 0

        if coverage < 0.1 and len(sitemap_set) > 10:
            findings.append({
                "id": "links-low-sitemap-coverage",
                "dimension": "internal_links",
                "severity": "medium",
                "confidence": "confirmed",
                "title": f"Page links to only {len(covered)}/{len(sitemap_set)} sitemap pages",
                "description": (
                    f"This page links to only {round(coverage * 100)}% of the "
                    f"pages in the sitemap. Important pages should be reachable "
                    "from the homepage through internal links, not just the sitemap."
                ),
            })
        elif coverage >= 0.3:
            sitemap_score = 15
            findings.append({
                "id": "links-good-sitemap-coverage",
                "dimension": "internal_links",
                "severity": "pass",
                "confidence": "confirmed",
                "title": f"Good sitemap coverage ({len(covered)}/{len(sitemap_set)} pages linked)",
                "description": (
                    f"This page links to {round(coverage * 100)}% of sitemap pages, "
                    "providing good internal discovery paths for AI crawlers."
                ),
            })
        else:
            sitemap_score = 8
    else:
        sitemap_score = 10  # no sitemap data = neutral

    # --- Calculate overall score ---
    score = min(density_score + anchor_score + diversity_score + hub_score + sitemap_score, 100)
    grade = to_grade(score)

    summary_parts = [f"{total_internal} internal links"]
    if unique_count != total_internal:
        summary_parts.append(f"{unique_count} unique destinations")
    if total_external:
        summary_parts.append(f"{total_external} external links")
    summary = f"{', '.join(summary_parts)}. Link structure score: {score}/100."

    return {
        "dimension": "internal_links",
        "url": url,
        "score": score,
        "grade": grade,
        "summary": summary,
        "total_internal": total_internal,
        "unique_internal": unique_count,
        "total_external": total_external,
        "links_per_1000_words": links_per_1000_words,
        "generic_anchor_count": generic_count,
        "empty_anchor_count": empty_count,
        "findings": findings,
    }


if __name__ == "__main__":
    sitemap_pages = None

    if not sys.stdin.isatty():
        try:
            raw = json.load(sys.stdin)
            if "page" in raw:
                page_data = raw["page"]
                if "sitemap" in raw and isinstance(raw["sitemap"], list):
                    sitemap_pages = raw["sitemap"]
            else:
                page_data = raw
            print(json.dumps(
                analyze_internal_links(page_data, sitemap_pages),
                indent=2, default=str,
            ))
            sys.exit(0)
        except (json.JSONDecodeError, KeyError):
            pass

    if len(sys.argv) < 2:
        print("Usage: python3 internal_links.py <url>")
        print("   or: python3 fetch_page.py <url> full | python3 internal_links.py")
        sys.exit(1)

    page_data = fetch_page_data(sys.argv[1])
    print(json.dumps(
        analyze_internal_links(page_data, sitemap_pages),
        indent=2, default=str,
    ))
