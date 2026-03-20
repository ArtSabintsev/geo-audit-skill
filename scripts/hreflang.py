#!/usr/bin/env python3
"""
Hreflang (international SEO) validator for GEO audit.

Validates the hreflang implementation on a page to assess:
  - Self-referencing tag: the current page should appear in its own hreflang set
  - x-default tag: a language-neutral fallback should be specified
  - Valid language codes: each hreflang value must be a valid ISO 639-1 code
  - Consistent protocol: all hreflang URLs should use the same protocol
  - Canonical alignment: canonical URL should match one of the hreflang URLs

Accepts a URL as argument or reads fetch_page.py JSON from stdin.
"""

import sys
import json
import re
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

# Common ISO 639-1 two-letter language codes
VALID_LANG_CODES = {
    "aa", "ab", "af", "ak", "am", "an", "ar", "as", "av", "ay", "az",
    "ba", "be", "bg", "bh", "bi", "bm", "bn", "bo", "br", "bs",
    "ca", "ce", "ch", "co", "cr", "cs", "cu", "cv", "cy",
    "da", "de", "dv", "dz",
    "ee", "el", "en", "eo", "es", "et", "eu",
    "fa", "ff", "fi", "fj", "fo", "fr", "fy",
    "ga", "gd", "gl", "gn", "gu", "gv",
    "ha", "he", "hi", "ho", "hr", "ht", "hu", "hy", "hz",
    "ia", "id", "ie", "ig", "ii", "ik", "io", "is", "it", "iu",
    "ja", "jv",
    "ka", "kg", "ki", "kj", "kk", "kl", "km", "kn", "ko", "kr", "ks", "ku", "kv", "kw", "ky",
    "la", "lb", "lg", "li", "ln", "lo", "lt", "lu", "lv",
    "mg", "mh", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my",
    "na", "nb", "nd", "ne", "ng", "nl", "nn", "no", "nr", "nv", "ny",
    "oc", "oj", "om", "or", "os",
    "pa", "pi", "pl", "ps", "pt",
    "qu",
    "rm", "rn", "ro", "ru", "rw",
    "sa", "sc", "sd", "se", "sg", "si", "sk", "sl", "sm", "sn", "so", "sq", "sr", "ss", "st", "su", "sv", "sw",
    "ta", "te", "tg", "th", "ti", "tk", "tl", "tn", "to", "tr", "ts", "tt", "tw", "ty",
    "ug", "uk", "ur", "uz",
    "ve", "vi", "vo",
    "wa", "wo",
    "xh",
    "yi", "yo",
    "za", "zh", "zu",
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

    # Canonical
    canonical_tag = soup.find("link", rel="canonical")
    canonical = canonical_tag.get("href") if canonical_tag else None

    # Hreflang links
    hreflang_links = []
    for link in soup.find_all("link", rel="alternate"):
        hreflang = link.get("hreflang")
        href = link.get("href")
        if hreflang and href:
            hreflang_links.append({
                "hreflang": hreflang,
                "href": href,
            })

    return {
        "url": url,
        "canonical": canonical,
        "hreflang_links": hreflang_links,
    }


def analyze_hreflang(page_data):
    """Analyze hreflang implementation on a page."""
    if "error" in page_data:
        return {"error": page_data["error"]}

    findings = []
    url = page_data.get("url", "")
    canonical = page_data.get("canonical")
    hreflang_links = page_data.get("hreflang_links", [])

    # --- No hreflang tags: neutral result (not every site needs them) ---
    if not hreflang_links:
        findings.append({
            "id": "hreflang-none",
            "dimension": "hreflang",
            "severity": "pass",
            "confidence": "confirmed",
            "title": "No hreflang tags — single-language site",
            "description": (
                "No hreflang tags were found on this page. This is perfectly "
                "fine for single-language sites. Hreflang tags are only needed "
                "when you have alternate language or regional versions of a page."
            ),
        })
        return {
            "dimension": "hreflang",
            "url": url,
            "score": 100,
            "grade": "A",
            "summary": "No hreflang tags found. Single-language site — no action needed.",
            "hreflang_count": 0,
            "languages": [],
            "findings": findings,
        }

    # --- Hreflang tags found: validate implementation ---
    checks = []
    hreflang_values = [l["hreflang"] for l in hreflang_links]
    hreflang_hrefs = [l["href"] for l in hreflang_links]

    # Collect languages for the output
    languages = []
    for val in hreflang_values:
        if val.lower() != "x-default":
            lang = val.split("-")[0].lower()
            if lang not in languages:
                languages.append(lang)

    # --- a. Self-referencing tag (weight 25) ---
    normalized_url = url.rstrip("/").lower()
    has_self_ref = any(
        href.rstrip("/").lower() == normalized_url
        for href in hreflang_hrefs
    )
    checks.append({"name": "Self-referencing tag", "passed": has_self_ref, "weight": 25})
    if not has_self_ref:
        findings.append({
            "id": "hreflang-no-self-ref",
            "dimension": "hreflang",
            "severity": "high",
            "confidence": "confirmed",
            "title": "Missing self-referencing hreflang tag",
            "description": (
                "The current page URL is not included in the hreflang set. "
                "Every page with hreflang tags must include a self-referencing "
                "entry pointing to itself. This helps search engines and AI "
                "crawlers confirm the relationship between language variants."
            ),
        })
    else:
        findings.append({
            "id": "hreflang-self-ref-ok",
            "dimension": "hreflang",
            "severity": "pass",
            "confidence": "confirmed",
            "title": "Self-referencing hreflang tag present",
            "description": "The page correctly includes itself in the hreflang set.",
        })

    # --- b. x-default tag (weight 20) ---
    has_x_default = any(
        val.lower() == "x-default"
        for val in hreflang_values
    )
    checks.append({"name": "x-default tag", "passed": has_x_default, "weight": 20})
    if not has_x_default:
        findings.append({
            "id": "hreflang-no-x-default",
            "dimension": "hreflang",
            "severity": "medium",
            "confidence": "confirmed",
            "title": "Missing x-default hreflang tag",
            "description": (
                "No x-default hreflang tag found. The x-default value tells "
                "search engines and AI crawlers which page to show when no "
                "language variant matches the user's preference. Add an "
                "x-default entry pointing to your primary or language-selection page."
            ),
        })
    else:
        findings.append({
            "id": "hreflang-x-default-ok",
            "dimension": "hreflang",
            "severity": "pass",
            "confidence": "confirmed",
            "title": "x-default hreflang tag present",
            "description": "An x-default fallback is correctly specified.",
        })

    # --- c. Valid language codes (weight 25) ---
    invalid_codes = []
    for val in hreflang_values:
        if val.lower() == "x-default":
            continue
        parts = val.lower().split("-")
        lang = parts[0]
        if lang not in VALID_LANG_CODES:
            invalid_codes.append(val)
        elif len(parts) > 1:
            region = parts[1]
            # Region code should be 2 uppercase letters (ISO 3166-1 alpha-2)
            if not re.match(r"^[a-z]{2}$", region):
                invalid_codes.append(val)

    codes_valid = len(invalid_codes) == 0
    checks.append({"name": "Valid language codes", "passed": codes_valid, "weight": 25})
    if not codes_valid:
        findings.append({
            "id": "hreflang-invalid-codes",
            "dimension": "hreflang",
            "severity": "high",
            "confidence": "confirmed",
            "title": f"Invalid hreflang language code(s): {', '.join(invalid_codes)}",
            "description": (
                f"The following hreflang values are not valid ISO 639-1 codes "
                f"(optionally with a region subtag): {', '.join(invalid_codes)}. "
                "Use two-letter language codes like 'en', 'fr', 'de', or "
                "language-region pairs like 'en-US', 'pt-BR'."
            ),
        })
    else:
        findings.append({
            "id": "hreflang-codes-ok",
            "dimension": "hreflang",
            "severity": "pass",
            "confidence": "confirmed",
            "title": "All hreflang language codes are valid",
            "description": "Every hreflang value uses a valid ISO 639-1 language code.",
        })

    # --- d. Consistent protocol (weight 15) ---
    protocols = set()
    for href in hreflang_hrefs:
        parsed = urlparse(href)
        if parsed.scheme:
            protocols.add(parsed.scheme)

    protocol_consistent = len(protocols) <= 1
    checks.append({"name": "Consistent protocol", "passed": protocol_consistent, "weight": 15})
    if not protocol_consistent:
        findings.append({
            "id": "hreflang-mixed-protocol",
            "dimension": "hreflang",
            "severity": "medium",
            "confidence": "confirmed",
            "title": "Mixed protocols in hreflang URLs",
            "description": (
                f"Hreflang URLs use mixed protocols ({', '.join(sorted(protocols))}). "
                "All hreflang URLs should use the same protocol — preferably HTTPS. "
                "Mixed protocols can cause search engines and AI crawlers to treat "
                "the language variants as separate, unrelated pages."
            ),
        })
    else:
        findings.append({
            "id": "hreflang-protocol-ok",
            "dimension": "hreflang",
            "severity": "pass",
            "confidence": "confirmed",
            "title": "Consistent protocol across hreflang URLs",
            "description": "All hreflang URLs use the same protocol.",
        })

    # --- e. Canonical alignment (weight 15) ---
    if canonical:
        normalized_canonical = canonical.rstrip("/").lower()
        canonical_in_hreflang = any(
            href.rstrip("/").lower() == normalized_canonical
            for href in hreflang_hrefs
        )
        checks.append({"name": "Canonical alignment", "passed": canonical_in_hreflang, "weight": 15})
        if not canonical_in_hreflang:
            findings.append({
                "id": "hreflang-canonical-mismatch",
                "dimension": "hreflang",
                "severity": "medium",
                "confidence": "confirmed",
                "title": "Canonical URL not found in hreflang set",
                "description": (
                    f"The canonical URL ({canonical}) does not match any of "
                    "the hreflang href values. The canonical URL should be "
                    "included as one of the hreflang entries to avoid "
                    "conflicting signals for search engines and AI crawlers."
                ),
            })
        else:
            findings.append({
                "id": "hreflang-canonical-ok",
                "dimension": "hreflang",
                "severity": "pass",
                "confidence": "confirmed",
                "title": "Canonical URL aligns with hreflang set",
                "description": "The canonical URL matches one of the hreflang entries.",
            })
    else:
        # No canonical — give the weight as a pass (cannot check)
        checks.append({"name": "Canonical alignment", "passed": True, "weight": 15})
        findings.append({
            "id": "hreflang-no-canonical",
            "dimension": "hreflang",
            "severity": "pass",
            "confidence": "confirmed",
            "title": "No canonical tag to validate against hreflang",
            "description": (
                "No canonical tag found, so canonical-hreflang alignment "
                "cannot be checked. Consider adding a canonical tag."
            ),
        })

    # --- Calculate score (weighted pass/fail) ---
    total_weight = sum(c["weight"] for c in checks)
    earned_weight = sum(c["weight"] for c in checks if c["passed"])
    score = round((earned_weight / total_weight) * 100) if total_weight else 0
    grade = to_grade(score)

    passed_count = sum(1 for c in checks if c["passed"])
    summary = (
        f"{passed_count}/{len(checks)} hreflang checks passed. "
        f"{len(hreflang_links)} hreflang tag(s) covering {len(languages)} language(s). "
        f"Score: {score}/100."
    )

    return {
        "dimension": "hreflang",
        "url": url,
        "score": score,
        "grade": grade,
        "summary": summary,
        "hreflang_count": len(hreflang_links),
        "languages": languages,
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
            print(json.dumps(analyze_hreflang(page_data), indent=2, default=str))
            sys.exit(0)
        except (json.JSONDecodeError, KeyError):
            pass

    if len(sys.argv) < 2:
        print("Usage: python3 hreflang.py <url>")
        print("   or: python3 fetch_page.py <url> full | python3 hreflang.py")
        sys.exit(1)

    page_data = fetch_page_data(sys.argv[1])
    print(json.dumps(analyze_hreflang(page_data), indent=2, default=str))
