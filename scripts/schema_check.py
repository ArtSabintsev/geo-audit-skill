#!/usr/bin/env python3
"""
Schema/JSON-LD checker — detects, validates, and recommends structured data.
"""

import sys
import json
import re

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

# Schema types relevant for GEO by business type
RECOMMENDED_SCHEMAS = {
    "saas": ["Organization", "SoftwareApplication", "WebSite", "FAQPage", "BreadcrumbList"],
    "ecommerce": ["Organization", "Product", "Offer", "AggregateRating", "BreadcrumbList", "WebSite"],
    "local": ["LocalBusiness", "GeoCoordinates", "PostalAddress", "OpeningHoursSpecification", "WebSite"],
    "publisher": ["Organization", "Article", "Person", "BreadcrumbList", "WebSite", "SearchAction", "SpeakableSpecification", "HowTo"],
    "agency": ["Organization", "Service", "WebSite", "BreadcrumbList", "FAQPage"],
    "other": ["Organization", "WebSite", "BreadcrumbList", "HowTo"],
}

# Required properties per schema type
REQUIRED_PROPS = {
    "Organization": ["name", "url", "logo"],
    "LocalBusiness": ["name", "address", "telephone"],
    "SoftwareApplication": ["name", "operatingSystem", "applicationCategory"],
    "Product": ["name", "description", "offers"],
    "Article": ["headline", "author", "datePublished"],
    "Person": ["name"],
    "WebSite": ["name", "url"],
    "FAQPage": ["mainEntity"],
    "BreadcrumbList": ["itemListElement"],
    "Service": ["name", "provider"],
    "SpeakableSpecification": ["cssSelector"],
    "HowTo": ["name", "step"],
}


def extract_schemas(url):
    """Extract all structured data from a page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return {"error": f"Failed to fetch: {e}"}

    soup = BeautifulSoup(resp.text, "lxml")
    schemas = []

    # JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    schemas.append({"format": "json-ld", "data": item})
            else:
                schemas.append({"format": "json-ld", "data": data})
        except (json.JSONDecodeError, TypeError):
            schemas.append({"format": "json-ld", "error": "Invalid JSON-LD"})

    # Microdata (basic detection)
    microdata_items = soup.find_all(attrs={"itemscope": True})
    for item in microdata_items:
        item_type = item.get("itemtype", "")
        schemas.append({
            "format": "microdata",
            "type": item_type,
            "note": "Microdata detected — JSON-LD is preferred for AI discoverability",
        })

    # RDFa (basic detection)
    rdfa_items = soup.find_all(attrs={"typeof": True})
    for item in rdfa_items:
        schemas.append({
            "format": "rdfa",
            "type": item.get("typeof", ""),
            "note": "RDFa detected — JSON-LD is preferred for AI discoverability",
        })

    return schemas


def get_schema_type(data):
    """Extract the @type from a schema object, handling nested/graph structures."""
    if isinstance(data, dict):
        if "@graph" in data:
            types = []
            for item in data["@graph"]:
                t = item.get("@type")
                if isinstance(t, list):
                    types.extend(t)
                elif t:
                    types.append(t)
            return types
        t = data.get("@type")
        if isinstance(t, list):
            return t
        return [t] if t else []
    return []


def validate_schema(data):
    """Validate a JSON-LD schema for completeness."""
    issues = []
    types = get_schema_type(data)

    if not types:
        issues.append({"severity": "high", "message": "Missing @type property"})
        return issues

    context = data.get("@context")
    if not context:
        issues.append({"severity": "medium", "message": "Missing @context (should be https://schema.org)"})
    else:
        # Normalize to string for comparison
        ctx_str = context if isinstance(context, str) else str(context)
        valid_contexts = {
            "https://schema.org",
            "https://schema.org/",
            "http://schema.org",
            "http://schema.org/",
        }
        if ctx_str not in valid_contexts:
            issues.append({
                "severity": "medium",
                "message": (
                    f"Non-standard @context value: '{ctx_str}'. "
                    "Use 'https://schema.org' for maximum compatibility with AI models."
                ),
            })

    for schema_type in types:
        required = REQUIRED_PROPS.get(schema_type, [])
        source = data
        if "@graph" in data:
            for item in data["@graph"]:
                item_types = item.get("@type", [])
                if isinstance(item_types, str):
                    item_types = [item_types]
                if schema_type in item_types:
                    source = item
                    break

        for prop in required:
            val = source.get(prop)
            if val is None or val == "" or val == []:
                issues.append({
                    "severity": "high",
                    "message": f"{schema_type}: missing required property '{prop}'",
                })

    return issues


def detect_business_type(page_text, url):
    """Heuristic business type detection from page content."""
    text_lower = page_text.lower()

    saas_signals = sum(1 for kw in [
        "pricing", "sign up", "free trial", "api", "dashboard",
        "saas", "subscription", "plan", "enterprise",
    ] if kw in text_lower)

    ecom_signals = sum(1 for kw in [
        "add to cart", "buy now", "product", "shop", "price",
        "checkout", "shipping", "inventory",
    ] if kw in text_lower)

    local_signals = sum(1 for kw in [
        "near me", "call us", "visit us", "directions",
        "hours", "location", "service area",
    ] if kw in text_lower)
    # Phone numbers
    if re.search(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", page_text):
        local_signals += 2

    publisher_signals = sum(1 for kw in [
        "blog", "article", "author", "published", "editor",
        "byline", "subscribe", "newsletter",
    ] if kw in text_lower)

    agency_signals = sum(1 for kw in [
        "portfolio", "case study", "our services", "clients",
        "testimonial", "consultation",
    ] if kw in text_lower)

    scores = {
        "saas": saas_signals,
        "ecommerce": ecom_signals,
        "local": local_signals,
        "publisher": publisher_signals,
        "agency": agency_signals,
    }

    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else "other"


def analyze_schemas(url):
    """Full schema analysis for a URL."""
    schemas = extract_schemas(url)
    if isinstance(schemas, dict) and "error" in schemas:
        return schemas

    # Get page text for business type detection
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(resp.text, "lxml")
        for el in soup.find_all(["script", "style"]):
            el.decompose()
        page_text = soup.get_text(separator=" ", strip=True)
    except Exception:
        page_text = ""

    biz_type = detect_business_type(page_text, url)
    recommended = RECOMMENDED_SCHEMAS.get(biz_type, RECOMMENDED_SCHEMAS["other"])

    # Find existing types
    found_types = set()
    validation_results = []

    for schema in schemas:
        if schema.get("format") == "json-ld" and "data" in schema:
            types = get_schema_type(schema["data"])
            found_types.update(types)
            issues = validate_schema(schema["data"])
            validation_results.append({
                "types": types,
                "issues": issues,
                "valid": len([i for i in issues if i["severity"] == "high"]) == 0,
            })
        elif schema.get("type"):
            type_name = schema["type"].split("/")[-1]
            found_types.add(type_name)

    missing = [t for t in recommended if t not in found_types]

    return {
        "url": url,
        "detected_business_type": biz_type,
        "schemas_found": len(schemas),
        "formats": list(set(s.get("format", "unknown") for s in schemas)),
        "types_found": sorted(found_types),
        "recommended_types": recommended,
        "missing_types": missing,
        "validation": validation_results,
        "raw_schemas": schemas,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 schema_check.py <url>")
        sys.exit(1)

    print(json.dumps(analyze_schemas(sys.argv[1]), indent=2, default=str))
