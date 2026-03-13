#!/usr/bin/env python3
"""
Technical SEO analyzer for GEO audit.

Runs 13 weighted checks that affect how AI crawlers index and understand pages:
 1. HTTPS                    (weight 15)
 2. Redirect chain <=2       (weight 10)
 3. Canonical tag            (weight 10)
 4. Single H1                (weight 10)
 5. Meta description length  (weight 10)
 6. Word count >= 300        (weight 15)
 7. Security headers         (weight 10)
 8. SSR content              (weight 15)
 9. Viewport meta tag        (weight  5)
10. Language attribute        (weight  5)
11. Open Graph tags          (weight  5)
12. Response time < 3s       (weight  5)
13. Image alt text >= 80%    (weight  5)

Accepts a URL as argument (fetches the page itself) or reads fetch_page.py
JSON from stdin.
"""

import sys
import json
import re
import time as _time
from urllib.parse import urlparse, urljoin

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

SECURITY_HEADERS = [
    "Strict-Transport-Security", "Content-Security-Policy",
    "X-Frame-Options", "X-Content-Type-Options",
    "Referrer-Policy", "Permissions-Policy",
]


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
    """Minimal page fetch for standalone usage. Returns dict matching fetch_page.py output."""
    result = {
        "url": url, "status_code": None, "redirect_chain": [],
        "canonical": None, "h1_tags": [], "description": None,
        "title": None, "word_count": 0, "has_ssr_content": True,
        "security_headers": {}, "images": [],
        "language": None, "viewport": None, "og_tags": {},
        "response_time_ms": None, "errors": [],
    }
    try:
        t0 = _time.monotonic()
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        t1 = _time.monotonic()
        result["response_time_ms"] = round((t1 - t0) * 1000)
        result["status_code"] = resp.status_code

        if resp.history:
            result["redirect_chain"] = [
                {"url": r.url, "status": r.status_code} for r in resp.history
            ]

        for h in SECURITY_HEADERS:
            result["security_headers"][h] = resp.headers.get(h)

        soup = BeautifulSoup(resp.text, "lxml")

        # Language
        html_tag = soup.find("html")
        if html_tag:
            result["language"] = html_tag.get("lang")

        # Title
        tag = soup.find("title")
        result["title"] = tag.get_text(strip=True) if tag else None

        # Meta tags
        for meta in soup.find_all("meta"):
            name = meta.get("name", meta.get("property", ""))
            content = meta.get("content", "")
            if name.lower() == "description":
                result["description"] = content
            if name.lower() == "viewport":
                result["viewport"] = content

        # OG tags
        for meta in soup.find_all("meta", attrs={"property": True}):
            prop = meta.get("property", "")
            content = meta.get("content", "")
            if prop.startswith("og:") and content:
                result["og_tags"][prop] = content

        # Canonical
        link = soup.find("link", rel="canonical")
        result["canonical"] = link.get("href") if link else None

        # H1 tags
        result["h1_tags"] = [h.get_text(strip=True) for h in soup.find_all("h1")]

        # Word count
        for el in soup.find_all(["script", "style", "nav", "footer", "header"]):
            el.decompose()
        text = soup.get_text(separator=" ", strip=True)
        result["word_count"] = len(text.split())

        # Images
        raw_soup = BeautifulSoup(resp.text, "lxml")
        for img in raw_soup.find_all("img"):
            result["images"].append({
                "src": img.get("src", ""),
                "alt": img.get("alt", ""),
            })

        # SSR check
        for root in raw_soup.find_all(id=re.compile(r"(app|root|__next|__nuxt)", re.I)):
            if len(root.get_text(strip=True)) < 50:
                result["has_ssr_content"] = False

    except Exception as e:
        result["errors"].append(str(e))

    return result


def analyze_technical_seo(page_data):
    """
    Run 13 technical SEO checks.

    page_data must have fields matching fetch_page.py output.
    """
    if "error" in page_data:
        return {"error": page_data["error"]}

    findings = []
    checks = []
    url = page_data.get("url", "")

    # --- 1. HTTPS ---
    is_https = url.startswith("https://")
    checks.append({"name": "HTTPS", "passed": is_https, "weight": 15})
    if not is_https:
        findings.append({
            "id": "tech-no-https",
            "dimension": "technical_seo",
            "severity": "critical",
            "title": "Site is not served over HTTPS",
            "description": (
                "Your site does not use HTTPS. Search engines and AI models "
                "penalize insecure sites. HTTPS is required for trust signals "
                "and modern web features."
            ),
        })

    # --- 2. Redirect chain ---
    redirect_chain = page_data.get("redirect_chain", [])
    redirect_count = len(redirect_chain)
    redirect_ok = redirect_count <= 2
    checks.append({"name": "Redirect chain", "passed": redirect_ok, "weight": 10})
    if not redirect_ok:
        findings.append({
            "id": "tech-redirect-chain",
            "dimension": "technical_seo",
            "severity": "medium",
            "title": f"Long redirect chain ({redirect_count} redirects)",
            "description": (
                f"Your URL goes through {redirect_count} redirects before "
                "reaching the final page. This slows down crawling and may "
                "cause AI crawlers to give up. Reduce to 1 redirect maximum."
            ),
        })

    # --- 3. Canonical tag ---
    has_canonical = bool(page_data.get("canonical"))
    checks.append({"name": "Canonical tag", "passed": has_canonical, "weight": 10})
    if not has_canonical:
        findings.append({
            "id": "tech-no-canonical",
            "dimension": "technical_seo",
            "severity": "medium",
            "title": "Missing canonical tag",
            "description": (
                "No canonical tag found. This can lead to duplicate content "
                "issues where AI models are unsure which version of a page "
                "to reference."
            ),
        })

    # --- 4. H1 count ---
    h1_tags = page_data.get("h1_tags", [])
    h1_count = len(h1_tags)
    h1_ok = h1_count == 1
    checks.append({"name": "Single H1", "passed": h1_ok, "weight": 10})
    if h1_count == 0:
        findings.append({
            "id": "tech-no-h1",
            "dimension": "technical_seo",
            "severity": "high",
            "title": "No H1 heading found",
            "description": (
                "The page has no H1 heading. AI models use the H1 as the primary "
                "topic signal for the page. Add exactly one H1 that clearly "
                "describes the page content."
            ),
        })
    elif h1_count > 1:
        findings.append({
            "id": "tech-multiple-h1",
            "dimension": "technical_seo",
            "severity": "low",
            "title": f"Multiple H1 headings ({h1_count} found)",
            "description": (
                "The page has multiple H1 headings, which can confuse AI models "
                "about the primary topic. Use exactly one H1 for the main page topic."
            ),
        })

    # --- 5. Meta description ---
    desc = page_data.get("description") or ""
    desc_len = len(desc)
    desc_ok = 50 <= desc_len <= 160
    checks.append({"name": "Meta description", "passed": desc_ok, "weight": 10})
    if desc_len == 0:
        findings.append({
            "id": "tech-no-description",
            "dimension": "technical_seo",
            "severity": "high",
            "title": "Missing meta description",
            "description": (
                "No meta description found. AI models often use the meta description "
                "as a summary of the page. Add a description between 50-160 characters."
            ),
        })
    elif desc_len < 50:
        findings.append({
            "id": "tech-short-description",
            "dimension": "technical_seo",
            "severity": "low",
            "title": f"Meta description too short ({desc_len} chars)",
            "description": (
                f"Your meta description is only {desc_len} characters. "
                "Aim for 50-160 characters for optimal AI comprehension."
            ),
        })
    elif desc_len > 160:
        findings.append({
            "id": "tech-long-description",
            "dimension": "technical_seo",
            "severity": "low",
            "title": f"Meta description too long ({desc_len} chars)",
            "description": (
                f"Your meta description is {desc_len} characters. It may be "
                "truncated. Aim for 50-160 characters."
            ),
        })

    # --- 6. Word count ---
    word_count = page_data.get("word_count", 0)
    word_count_ok = word_count >= 300
    checks.append({"name": "Word count (300+)", "passed": word_count_ok, "weight": 15})
    if not word_count_ok:
        sev = "high" if word_count < 100 else "medium"
        findings.append({
            "id": "tech-low-word-count",
            "dimension": "technical_seo",
            "severity": sev,
            "title": f"Low word count ({word_count} words)",
            "description": (
                f"The page has only {word_count} words. Pages with fewer than "
                "300 words are less likely to be indexed or cited by AI models. "
                "Add substantive content."
            ),
        })

    # --- 7. Security headers ---
    sec_headers = page_data.get("security_headers", {})
    sec_present = sum(1 for v in sec_headers.values() if v is not None)
    sec_total = len(sec_headers) if sec_headers else len(SECURITY_HEADERS)
    sec_ok = sec_present >= sec_total / 2
    checks.append({"name": "Security headers", "passed": sec_ok, "weight": 10})
    if sec_present == 0:
        findings.append({
            "id": "tech-no-security-headers",
            "dimension": "technical_seo",
            "severity": "medium",
            "title": "No security headers found",
            "description": (
                "None of the recommended security headers are set. While not "
                "directly affecting AI indexing, security headers contribute "
                "to overall site trust."
            ),
        })
    elif not sec_ok:
        missing = [k for k, v in sec_headers.items() if v is None]
        findings.append({
            "id": "tech-missing-security-headers",
            "dimension": "technical_seo",
            "severity": "low",
            "title": f"Missing security headers: {', '.join(missing)}",
            "description": (
                f"{sec_present} of {sec_total} recommended security headers are "
                f"present. Missing: {', '.join(missing)}."
            ),
        })

    # --- 8. SSR content ---
    ssr_ok = page_data.get("has_ssr_content", True)
    checks.append({"name": "SSR content", "passed": ssr_ok, "weight": 15})
    if not ssr_ok:
        findings.append({
            "id": "tech-no-ssr",
            "dimension": "technical_seo",
            "severity": "critical",
            "title": "Page appears to be client-side rendered",
            "description": (
                "The page appears to rely on client-side JavaScript rendering. "
                "AI crawlers typically do not execute JavaScript, so they may "
                "see an empty page. Implement server-side rendering (SSR) or "
                "static generation."
            ),
        })

    # --- 9. Viewport meta tag ---
    has_viewport = bool(page_data.get("viewport"))
    checks.append({"name": "Viewport meta", "passed": has_viewport, "weight": 5})
    if not has_viewport:
        findings.append({
            "id": "tech-no-viewport",
            "dimension": "technical_seo",
            "severity": "medium",
            "title": "Missing viewport meta tag",
            "description": (
                "No viewport meta tag found. This is essential for mobile "
                "responsiveness, which is a ranking factor for both traditional "
                "and AI search."
            ),
        })

    # --- 10. Language attribute ---
    has_lang = bool(page_data.get("language"))
    checks.append({"name": "Language attribute", "passed": has_lang, "weight": 5})
    if not has_lang:
        findings.append({
            "id": "tech-no-lang",
            "dimension": "technical_seo",
            "severity": "low",
            "title": "Missing lang attribute on <html>",
            "description": (
                "The <html> element has no lang attribute. This helps AI models "
                "understand the content language and serve it to appropriate users."
            ),
        })

    # --- 11. Open Graph tags ---
    og_tags = page_data.get("og_tags", {})
    og_title = og_tags.get("og:title")
    og_desc = og_tags.get("og:description")
    og_image = og_tags.get("og:image")
    og_count = sum(1 for v in [og_title, og_desc, og_image] if v)
    og_ok = og_count >= 2
    checks.append({"name": "Open Graph tags", "passed": og_ok, "weight": 5})
    if og_count == 0:
        findings.append({
            "id": "tech-no-og-tags",
            "dimension": "technical_seo",
            "severity": "medium",
            "title": "No Open Graph tags found",
            "description": (
                "No og:title, og:description, or og:image tags found. Open Graph "
                "tags improve how your content appears when shared and help AI "
                "models extract metadata."
            ),
        })
    elif not og_ok:
        missing_og = []
        if not og_title:
            missing_og.append("og:title")
        if not og_desc:
            missing_og.append("og:description")
        if not og_image:
            missing_og.append("og:image")
        findings.append({
            "id": "tech-incomplete-og",
            "dimension": "technical_seo",
            "severity": "low",
            "title": f"Missing Open Graph tags: {', '.join(missing_og)}",
            "description": (
                f"Found {og_count}/3 key Open Graph tags. Missing: "
                f"{', '.join(missing_og)}. Complete OG tags improve content "
                "discoverability."
            ),
        })

    # --- 12. Response time ---
    response_time_ms = page_data.get("response_time_ms")
    response_ok = response_time_ms is not None and response_time_ms < 3000
    checks.append({"name": "Response time (<3s)", "passed": response_ok, "weight": 5})
    if response_time_ms is not None and response_time_ms >= 3000:
        sev = "high" if response_time_ms >= 8000 else "medium"
        findings.append({
            "id": "tech-slow-response",
            "dimension": "technical_seo",
            "severity": sev,
            "title": f"Slow response time ({response_time_ms / 1000:.1f}s)",
            "description": (
                f"The page took {response_time_ms / 1000:.1f} seconds to load. "
                "AI crawlers may timeout on slow pages. Aim for under 3 seconds."
            ),
        })

    # --- 13. Image alt text coverage ---
    images = page_data.get("images", [])
    total_images = len(images)
    images_with_alt = sum(1 for img in images if (img.get("alt") or "").strip())
    alt_coverage = images_with_alt / total_images if total_images > 0 else 1.0
    alt_ok = alt_coverage >= 0.8
    checks.append({"name": "Image alt text", "passed": alt_ok, "weight": 5})
    if total_images > 0 and not alt_ok:
        missing_alt = total_images - images_with_alt
        sev = "medium" if missing_alt > 5 else "low"
        findings.append({
            "id": "tech-missing-alt",
            "dimension": "technical_seo",
            "severity": sev,
            "title": f"{missing_alt} image{'s' if missing_alt != 1 else ''} missing alt text",
            "description": (
                f"{images_with_alt}/{total_images} images have alt text "
                f"({round(alt_coverage * 100)}% coverage). Alt text helps AI models "
                "understand image content and improves accessibility."
            ),
        })

    # --- Calculate score ---
    total_weight = sum(c["weight"] for c in checks)
    earned_weight = sum(c["weight"] for c in checks if c["passed"])
    score = round((earned_weight / total_weight) * 100) if total_weight else 0
    grade = to_grade(score)

    passed_count = sum(1 for c in checks if c["passed"])
    summary = f"{passed_count}/{len(checks)} technical checks passed. Score: {score}/100."

    return {
        "dimension": "technical_seo",
        "url": url,
        "score": score,
        "grade": grade,
        "summary": summary,
        "checks": checks,
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
            print(json.dumps(analyze_technical_seo(page_data), indent=2, default=str))
            sys.exit(0)
        except (json.JSONDecodeError, KeyError):
            pass

    if len(sys.argv) < 2:
        print("Usage: python3 technical_seo.py <url>")
        print("   or: python3 fetch_page.py <url> full | python3 technical_seo.py")
        sys.exit(1)

    page_data = fetch_page_data(sys.argv[1])
    print(json.dumps(analyze_technical_seo(page_data), indent=2, default=str))
