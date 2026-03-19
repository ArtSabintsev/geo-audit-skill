#!/usr/bin/env python3
"""
Search intent classifier for GEO audit.

Classifies page content into search intent categories and checks whether
the page type aligns with the detected intent:

  - Informational: guides, tutorials, how-tos, definitions
  - Commercial: comparisons, reviews, "best of" lists, feature tables
  - Transactional: buy/order CTAs, pricing, product pages, checkout
  - Navigational: brand-heavy, login, specific service pages

Accepts a URL as argument or reads fetch_page.py JSON from stdin.
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

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    desc = ""
    for meta in soup.find_all("meta"):
        if (meta.get("name") or "").lower() == "description":
            desc = meta.get("content", "")

    h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1")]
    headings = []
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            headings.append({"level": level, "text": h.get_text(strip=True)})

    for el in soup.find_all(["script", "style", "nav", "footer", "header"]):
        el.decompose()
    text_content = soup.get_text(separator=" ", strip=True)

    base_domain = urlparse(url).netloc
    internal_links = []
    external_links = []
    for a in raw_soup.find_all("a", href=True):
        href = a["href"]
        link_text = a.get_text(strip=True)
        parsed = urlparse(href)
        if parsed.netloc == base_domain or href.startswith("/"):
            internal_links.append({"url": href, "text": link_text})
        elif parsed.scheme in ("http", "https"):
            external_links.append({"url": href, "text": link_text})

    return {
        "url": url,
        "title": title,
        "description": desc,
        "h1_tags": h1_tags,
        "heading_structure": headings,
        "text_content": text_content,
        "word_count": len(text_content.split()),
        "internal_links": internal_links,
        "external_links": external_links,
    }


def classify_intent(page_data):
    """Classify the search intent of a page from on-page signals."""
    if "error" in page_data:
        return {"error": page_data["error"]}

    text = page_data.get("text_content", "").lower()
    title = (page_data.get("title") or "").lower()
    h1_tags = [h.lower() for h in page_data.get("h1_tags", [])]
    headings = page_data.get("heading_structure", [])
    heading_texts = [h["text"].lower() for h in headings]
    all_headings = " ".join(heading_texts)
    url = page_data.get("url", "").lower()
    word_count = page_data.get("word_count", 0)
    internal_links = page_data.get("internal_links", [])
    link_texts = " ".join(l.get("text", "").lower() for l in internal_links)

    findings = []

    # --- Score each intent type ---
    intent_scores = {
        "informational": 0,
        "commercial": 0,
        "transactional": 0,
        "navigational": 0,
    }

    # ---- INFORMATIONAL signals ----
    info_heading_patterns = [
        r"\bhow\s+to\b", r"\bwhat\s+is\b", r"\bwhat\s+are\b",
        r"\bwhy\s+", r"\bguide\b", r"\btutorial\b",
        r"\bexplained\b", r"\bintroduction\b", r"\blearn\b",
        r"\bunderstand\b", r"\bdefinition\b", r"\btips\b",
    ]
    for p in info_heading_patterns:
        if re.search(p, all_headings):
            intent_scores["informational"] += 3
        if re.search(p, title):
            intent_scores["informational"] += 5

    info_content_patterns = [
        r"\bin\s+this\s+(?:guide|article|post|tutorial)\b",
        r"\bstep\s+\d+\b", r"\bstep-by-step\b",
        r"\bhere(?:'s| is)\s+(?:how|what|why)\b",
        r"\bfor\s+(?:beginners?|experts?)\b",
        r"\beverything\s+you\s+need\s+to\s+know\b",
    ]
    for p in info_content_patterns:
        if re.search(p, text):
            intent_scores["informational"] += 2

    if word_count > 1000:
        intent_scores["informational"] += 3
    if word_count > 2000:
        intent_scores["informational"] += 2

    # URL signals
    if re.search(r"/(?:blog|articles?|guides?|learn|resources?|wiki|help|docs?|documentation)/", url):
        intent_scores["informational"] += 5

    # ---- COMMERCIAL signals ----
    commercial_heading_patterns = [
        r"\bbest\b", r"\btop\s+\d+\b", r"\bvs\.?\s+\b",
        r"\bcompare|comparison\b", r"\breview\b",
        r"\balternatives?\b", r"\bfeatures?\b",
        r"\bpros?\s+(?:and|&)\s+cons?\b",
    ]
    for p in commercial_heading_patterns:
        if re.search(p, all_headings):
            intent_scores["commercial"] += 3
        if re.search(p, title):
            intent_scores["commercial"] += 5

    commercial_content_patterns = [
        r"\bcompared\s+to\b", r"\bbetter\s+than\b", r"\bworse\s+than\b",
        r"\b(?:advantages?|disadvantages?)\b",
        r"\b(?:ratings?|rankings?|scored?)\b",
        r"\bwe\s+(?:tested|reviewed|evaluated|ranked)\b",
        r"\bour\s+(?:pick|choice|recommendation|verdict)\b",
    ]
    for p in commercial_content_patterns:
        if re.search(p, text):
            intent_scores["commercial"] += 2

    # Pricing mention without direct purchase = commercial investigation
    if re.search(r"\bpric(?:e|ing|es)\b", text) and not re.search(r"\badd\s+to\s+cart\b", text):
        intent_scores["commercial"] += 3

    if re.search(r"/(?:compare|vs|review|best|alternatives?)/", url):
        intent_scores["commercial"] += 5

    # ---- TRANSACTIONAL signals ----
    transactional_patterns = [
        r"\bbuy\s+(?:now|today|online)\b",
        r"\badd\s+to\s+cart\b", r"\badd\s+to\s+bag\b",
        r"\bcheckout\b", r"\border\s+(?:now|today|online)\b",
        r"\bshop\s+(?:now|today|online)\b",
        r"\bget\s+started\b", r"\bsign\s*up\b",
        r"\bfree\s+trial\b", r"\bstart\s+(?:your\s+)?free\b",
        r"\bsubscribe\b", r"\bdownload\s+(?:now|free|today)\b",
        r"\bbook\s+(?:now|a|an|your)\b",
        r"\brequest\s+(?:a\s+)?(?:demo|quote)\b",
    ]
    for p in transactional_patterns:
        if re.search(p, text):
            intent_scores["transactional"] += 3
        if re.search(p, link_texts):
            intent_scores["transactional"] += 2

    # Price elements
    price_count = len(re.findall(r"\$\d+(?:\.\d{2})?(?:\s*/\s*(?:mo|month|year|yr))?", text))
    if price_count >= 3:
        intent_scores["transactional"] += 5
    elif price_count >= 1:
        intent_scores["transactional"] += 2

    if re.search(r"/(?:pricing|plans|products?|shop|store|cart|checkout|buy)/", url):
        intent_scores["transactional"] += 5

    # ---- NAVIGATIONAL signals ----
    navigational_patterns = [
        r"\blog\s*in\b", r"\bsign\s*in\b",
        r"\bmy\s+account\b", r"\bdashboard\b",
        r"\bcontact\s+us\b", r"\bsupport\b",
    ]
    for p in navigational_patterns:
        if re.search(p, text[:500]):
            intent_scores["navigational"] += 2

    if re.search(r"/(?:login|signin|account|dashboard|support|contact)/", url):
        intent_scores["navigational"] += 5

    # Homepage is often navigational
    parsed = urlparse(page_data.get("url", ""))
    if parsed.path in ("", "/", "/index.html", "/index.php"):
        intent_scores["navigational"] += 3

    if word_count < 200:
        intent_scores["navigational"] += 2

    # --- Determine primary and secondary intent ---
    sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
    primary_intent = sorted_intents[0][0]
    primary_score = sorted_intents[0][1]
    secondary_intent = sorted_intents[1][0] if sorted_intents[1][1] > 0 else None
    secondary_score = sorted_intents[1][1]

    # Confidence based on score separation
    if primary_score == 0:
        primary_intent = "informational"  # default
        confidence = "low"
    elif primary_score - (secondary_score or 0) >= 8:
        confidence = "high"
    elif primary_score - (secondary_score or 0) >= 4:
        confidence = "medium"
    else:
        confidence = "low"

    # --- Detect page type ---
    page_type = "general"
    if re.search(r"/(?:blog|articles?|posts?)/", url) or word_count > 1500:
        page_type = "article"
    if re.search(r"/(?:products?|shop|store)/", url) or price_count >= 3:
        page_type = "product"
    if re.search(r"/(?:pricing|plans)/", url):
        page_type = "pricing"
    if re.search(r"/(?:about|team|company)/", url):
        page_type = "about"
    if re.search(r"/(?:contact|support|help)/", url):
        page_type = "support"
    if re.search(r"/(?:compare|vs|alternatives?)/", url):
        page_type = "comparison"
    if re.search(r"/(?:services?|solutions?)/", url):
        page_type = "service"
    if parsed.path in ("", "/", "/index.html", "/index.php"):
        page_type = "homepage"

    # --- Check intent-page type alignment ---
    alignment_map = {
        "informational": ["article", "general", "about", "support"],
        "commercial": ["comparison", "article", "general", "service"],
        "transactional": ["product", "pricing", "service", "homepage"],
        "navigational": ["homepage", "support", "about", "general"],
    }
    aligned_types = alignment_map.get(primary_intent, [])
    is_aligned = page_type in aligned_types

    # --- Build findings ---
    intent_label = primary_intent.capitalize()
    findings.append({
        "id": f"intent-primary-{primary_intent}",
        "dimension": "search_intent",
        "severity": "pass",
        "confidence": "likely",
        "title": f"Primary intent: {intent_label} (confidence: {confidence})",
        "description": (
            f"The page content signals {intent_label.lower()} search intent "
            f"based on headings, content patterns, URL structure, and page elements."
        ),
    })

    if secondary_intent and secondary_score > 3:
        findings.append({
            "id": f"intent-secondary-{secondary_intent}",
            "dimension": "search_intent",
            "severity": "pass",
            "confidence": "likely",
            "title": f"Secondary intent: {secondary_intent.capitalize()}",
            "description": (
                f"The page also shows {secondary_intent} signals, suggesting "
                f"mixed intent. This can be intentional (e.g., informational "
                f"content with commercial comparisons)."
            ),
        })

    if is_aligned:
        findings.append({
            "id": "intent-aligned",
            "dimension": "search_intent",
            "severity": "pass",
            "confidence": "likely",
            "title": f"Page type ({page_type}) aligns with {intent_label.lower()} intent",
            "description": (
                f"The {page_type} page format matches the detected "
                f"{intent_label.lower()} intent. AI models are more likely to "
                f"cite content when the page format matches the query intent."
            ),
        })
    else:
        findings.append({
            "id": "intent-misaligned",
            "dimension": "search_intent",
            "severity": "medium",
            "confidence": "hypothesis",
            "title": f"Page type ({page_type}) may not match {intent_label.lower()} intent",
            "description": (
                f"The page appears to be a {page_type} page but the content "
                f"signals {intent_label.lower()} intent. Consider whether the "
                f"page format serves the user's likely goal. For example, an "
                f"informational query landing on a product page may cause users "
                f"to bounce."
            ),
        })

    # --- Intent-specific recommendations ---
    if primary_intent == "informational" and not any(
        re.search(r"\?$", h["text"]) for h in headings
    ):
        findings.append({
            "id": "intent-info-no-questions",
            "dimension": "search_intent",
            "severity": "low",
            "confidence": "hypothesis",
            "title": "Informational page has no question-format headings",
            "description": (
                "This informational page has no headings phrased as questions. "
                "Question headings (e.g., 'What is X?', 'How does Y work?') "
                "match how users phrase queries and are more likely to be "
                "selected for featured snippets and AI citations."
            ),
        })

    if primary_intent == "commercial" and not re.search(
        r"\b(?:table|vs\.?|compare|comparison)\b", all_headings
    ):
        findings.append({
            "id": "intent-commercial-no-comparison",
            "dimension": "search_intent",
            "severity": "low",
            "confidence": "hypothesis",
            "title": "Commercial page lacks comparison structure",
            "description": (
                "This page has commercial intent signals but no comparison "
                "tables or vs-style headings. Structured comparisons help AI "
                "models extract and cite your evaluations."
            ),
        })

    if primary_intent == "transactional" and word_count > 2000:
        findings.append({
            "id": "intent-transactional-too-long",
            "dimension": "search_intent",
            "severity": "low",
            "confidence": "hypothesis",
            "title": "Transactional page may be too content-heavy",
            "description": (
                f"This transactional page has {word_count} words. "
                "Transactional pages typically perform better with concise, "
                "action-oriented content. Consider moving detailed information "
                "to supporting pages and keeping the conversion path clear."
            ),
        })

    # --- Score: based on how clear the intent signal is + alignment ---
    score = 0
    # Clear primary intent
    if primary_score >= 10:
        score += 40
    elif primary_score >= 5:
        score += 25
    elif primary_score > 0:
        score += 15

    # Good separation from secondary
    if confidence == "high":
        score += 25
    elif confidence == "medium":
        score += 15
    elif confidence == "low":
        score += 5

    # Alignment bonus
    if is_aligned:
        score += 25

    # Intent-appropriate content elements
    if primary_intent == "informational" and word_count >= 500:
        score += 10
    elif primary_intent == "commercial" and re.search(r"\b(?:vs|compare|best|top)\b", all_headings):
        score += 10
    elif primary_intent == "transactional" and price_count >= 1:
        score += 10
    elif primary_intent == "navigational":
        score += 10

    score = min(score, 100)
    grade = to_grade(score)

    return {
        "dimension": "search_intent",
        "url": page_data.get("url", ""),
        "score": score,
        "grade": grade,
        "primary_intent": primary_intent,
        "secondary_intent": secondary_intent,
        "confidence": confidence,
        "page_type": page_type,
        "intent_aligned": is_aligned,
        "intent_scores": intent_scores,
        "summary": (
            f"Primary intent: {intent_label} ({confidence} confidence). "
            f"Page type: {page_type}. "
            f"{'Aligned' if is_aligned else 'Misaligned'} with detected intent."
        ),
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
            print(json.dumps(classify_intent(page_data), indent=2, default=str))
            sys.exit(0)
        except (json.JSONDecodeError, KeyError):
            pass

    if len(sys.argv) < 2:
        print("Usage: python3 search_intent.py <url>")
        print("   or: python3 fetch_page.py <url> full | python3 search_intent.py")
        sys.exit(1)

    page_data = fetch_page_data(sys.argv[1])
    print(json.dumps(classify_intent(page_data), indent=2, default=str))
