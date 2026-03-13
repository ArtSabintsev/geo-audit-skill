#!/usr/bin/env python3
"""
Fetch and parse web pages for GEO audit.
Extracts HTML, meta tags, headers, structured data, robots.txt, llms.txt, and sitemap.
"""

import sys
import json
import re
from urllib.parse import urljoin, urlparse

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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

AI_CRAWLERS = [
    "GPTBot", "OAI-SearchBot", "ChatGPT-User",
    "ClaudeBot", "anthropic-ai",
    "PerplexityBot", "CCBot", "Bytespider", "cohere-ai",
    "Google-Extended", "GoogleOther", "Applebot-Extended",
    "FacebookBot", "Amazonbot",
    "Meta-ExternalAgent", "Meta-ExternalFetcher",
    "YouBot", "AI2Bot", "Diffbot", "ImagesiftBot",
]

SECURITY_HEADERS = [
    "Strict-Transport-Security", "Content-Security-Policy",
    "X-Frame-Options", "X-Content-Type-Options",
    "Referrer-Policy", "Permissions-Policy",
]


def fetch_page(url, timeout=30):
    """Fetch a page and return structured data."""
    result = {
        "url": url, "status_code": None, "redirect_chain": [],
        "response_headers": {}, "meta_tags": {}, "title": None,
        "description": None, "canonical": None, "h1_tags": [],
        "heading_structure": [], "word_count": 0, "text_content": "",
        "internal_links": [], "external_links": [], "images": [],
        "structured_data": [], "has_ssr_content": True,
        "security_headers": {}, "errors": [],
        "language": None, "viewport": None,
        "og_tags": {}, "meta_robots": None, "x_robots_tag": None,
        "response_time_ms": None,
    }

    result["detected_platform"] = None

    try:
        import time as _time
        _t0 = _time.monotonic()
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        _t1 = _time.monotonic()
        result["response_time_ms"] = round((_t1 - _t0) * 1000)
        if resp.history:
            result["redirect_chain"] = [
                {"url": r.url, "status": r.status_code} for r in resp.history
            ]
        result["status_code"] = resp.status_code
        result["response_headers"] = dict(resp.headers)

        for h in SECURITY_HEADERS:
            result["security_headers"][h] = resp.headers.get(h)

        # X-Robots-Tag header
        result["x_robots_tag"] = resp.headers.get("X-Robots-Tag")

        soup = BeautifulSoup(resp.text, "lxml")

        # Language attribute from <html lang="...">
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
            if name and content:
                result["meta_tags"][name.lower()] = content
                if name.lower() == "description":
                    result["description"] = content
                if name.lower() == "viewport":
                    result["viewport"] = content
                if name.lower() == "robots":
                    result["meta_robots"] = content

        # Open Graph tags
        for meta in soup.find_all("meta", attrs={"property": True}):
            prop = meta.get("property", "")
            content = meta.get("content", "")
            if prop.startswith("og:") and content:
                result["og_tags"][prop] = content

        # Canonical
        link = soup.find("link", rel="canonical")
        result["canonical"] = link.get("href") if link else None

        # Headings
        for level in range(1, 7):
            for h in soup.find_all(f"h{level}"):
                text = h.get_text(strip=True)
                result["heading_structure"].append({"level": level, "text": text})
                if level == 1:
                    result["h1_tags"].append(text)

        # Text content (strip boilerplate)
        for el in soup.find_all(["script", "style", "nav", "footer", "header"]):
            el.decompose()
        text = soup.get_text(separator=" ", strip=True)
        result["text_content"] = text
        result["word_count"] = len(text.split())

        # Links
        base_domain = urlparse(url).netloc
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            link_text = a.get_text(strip=True)
            parsed = urlparse(href)
            if parsed.netloc == base_domain:
                result["internal_links"].append({"url": href, "text": link_text})
            elif parsed.scheme in ("http", "https"):
                result["external_links"].append({"url": href, "text": link_text})

        # Images
        for img in soup.find_all("img"):
            result["images"].append({
                "src": img.get("src", ""),
                "alt": img.get("alt", ""),
                "loading": img.get("loading"),
            })

        # JSON-LD
        raw_soup = BeautifulSoup(resp.text, "lxml")
        for script in raw_soup.find_all("script", type="application/ld+json"):
            try:
                result["structured_data"].append(json.loads(script.string))
            except (json.JSONDecodeError, TypeError):
                result["errors"].append("Invalid JSON-LD found")

        # SSR check
        for root in raw_soup.find_all(id=re.compile(r"(app|root|__next|__nuxt)", re.I)):
            if len(root.get_text(strip=True)) < 50:
                result["has_ssr_content"] = False
                result["errors"].append(
                    f"Possible client-side-only rendering: #{root.get('id', '?')} has minimal content"
                )

        # Platform detection
        result["detected_platform"] = detect_platform(resp.text, resp.headers)

    except requests.exceptions.Timeout:
        result["errors"].append(f"Timeout after {timeout}s")
    except requests.exceptions.ConnectionError as e:
        result["errors"].append(f"Connection error: {e}")
    except Exception as e:
        result["errors"].append(f"Error: {e}")

    return result


def detect_platform(html, headers):
    """Detect what platform/CMS a website is built on."""
    lower = html.lower()
    server = (headers.get("server") or "").lower()
    powered_by = (headers.get("x-powered-by") or "").lower()

    # Extract generator meta tag
    gen_match = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    generator = (gen_match.group(1) if gen_match else "").lower()

    if "wp-content" in lower or "wp-includes" in lower or "wordpress" in generator:
        if ".wordpress.com" in lower or "WordPress.com" in headers.get("x-powered-by", ""):
            return {"name": "WordPress.com", "slug": "wordpress-com"}
        return {"name": "WordPress", "slug": "wordpress"}
    if "squarespace.com" in lower or "static.squarespace.com" in lower or "squarespace-cdn" in lower:
        return {"name": "Squarespace", "slug": "squarespace"}
    if "wix.com" in lower or "wixstatic.com" in lower or headers.get("x-wix-request-id"):
        return {"name": "Wix", "slug": "wix"}
    if "cdn.shopify.com" in lower or headers.get("x-shopify-stage"):
        return {"name": "Shopify", "slug": "shopify"}
    if "webflow.com" in lower or "assets.website-files.com" in lower or "webflow" in generator:
        return {"name": "Webflow", "slug": "webflow"}
    if "ghost.org" in lower or "ghost" in generator:
        return {"name": "Ghost", "slug": "ghost"}
    if "framer.com" in lower or "framerusercontent.com" in lower:
        return {"name": "Framer", "slug": "framer"}
    if "hubspot.com" in lower or "hs-scripts.com" in lower or "hscollectedforms" in lower:
        return {"name": "HubSpot", "slug": "hubspot"}
    if "carrd.co" in lower:
        return {"name": "Carrd", "slug": "carrd"}
    if "weebly.com" in lower or "editmysite.com" in lower:
        return {"name": "Weebly", "slug": "weebly"}
    if "drupal" in lower or "drupal" in generator:
        return {"name": "Drupal", "slug": "drupal"}
    if "__next" in lower or "next.js" in powered_by:
        return {"name": "Next.js", "slug": "nextjs"}
    if "vercel" in server or headers.get("x-vercel-id"):
        return {"name": "Vercel", "slug": "vercel"}
    if "netlify" in server or headers.get("x-nf-request-id"):
        return {"name": "Netlify", "slug": "netlify"}
    return None


def fetch_robots(url, timeout=15):
    """Fetch and parse robots.txt for AI crawler directives."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    result = {
        "url": robots_url, "exists": False, "content": "",
        "ai_crawler_status": {}, "sitemaps": [], "errors": [],
    }

    try:
        resp = requests.get(robots_url, headers=HEADERS, timeout=timeout)
        if resp.status_code == 200:
            result["exists"] = True
            result["content"] = resp.text

            lines = resp.text.split("\n")
            current_agent = None
            agent_rules = {}

            for line in lines:
                line = line.strip()
                if line.lower().startswith("user-agent:"):
                    current_agent = line.split(":", 1)[1].strip()
                    agent_rules.setdefault(current_agent, [])
                elif current_agent and line.lower().startswith(("disallow:", "allow:")):
                    directive, path = line.split(":", 1)
                    agent_rules[current_agent].append({
                        "directive": directive.strip().capitalize(),
                        "path": path.strip(),
                    })
                elif line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    if not sitemap_url.startswith("http"):
                        sitemap_url = "http" + sitemap_url
                    result["sitemaps"].append(sitemap_url)

            for crawler in AI_CRAWLERS:
                if crawler in agent_rules:
                    rules = agent_rules[crawler]
                    if any(r["directive"] == "Disallow" and r["path"] == "/" for r in rules):
                        result["ai_crawler_status"][crawler] = "BLOCKED"
                    elif any(r["directive"] == "Disallow" and r["path"] for r in rules):
                        result["ai_crawler_status"][crawler] = "PARTIALLY_BLOCKED"
                    else:
                        result["ai_crawler_status"][crawler] = "ALLOWED"
                elif "*" in agent_rules:
                    wildcard = agent_rules["*"]
                    if any(r["directive"] == "Disallow" and r["path"] == "/" for r in wildcard):
                        result["ai_crawler_status"][crawler] = "BLOCKED_BY_WILDCARD"
                    else:
                        result["ai_crawler_status"][crawler] = "ALLOWED_BY_DEFAULT"
                else:
                    result["ai_crawler_status"][crawler] = "NOT_MENTIONED"

        elif resp.status_code == 404:
            result["errors"].append("No robots.txt (404)")
            for crawler in AI_CRAWLERS:
                result["ai_crawler_status"][crawler] = "NO_ROBOTS_TXT"
        else:
            result["errors"].append(f"Unexpected status: {resp.status_code}")

    except Exception as e:
        result["errors"].append(f"Error: {e}")

    return result


def fetch_llms_txt(url, timeout=15):
    """Check for llms.txt and llms-full.txt."""
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
            if resp.status_code == 200 and not resp.headers.get("content-type", "").startswith("text/html"):
                result[key]["exists"] = True
                result[key]["content"] = resp.text
        except Exception as e:
            result["errors"].append(f"Error checking {path}: {e}")

    return result


def crawl_sitemap(url, max_pages=50, timeout=15):
    """Discover pages from sitemap.xml."""
    parsed = urlparse(url)
    candidates = [
        f"{parsed.scheme}://{parsed.netloc}/sitemap.xml",
        f"{parsed.scheme}://{parsed.netloc}/sitemap_index.xml",
    ]

    pages = set()

    for sitemap_url in candidates:
        try:
            resp = requests.get(sitemap_url, headers=HEADERS, timeout=timeout)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # Sitemap index — fetch child sitemaps
            for sm in soup.find_all("sitemap"):
                loc = sm.find("loc")
                if not loc:
                    continue
                try:
                    child = requests.get(loc.text.strip(), headers=HEADERS, timeout=timeout)
                    if child.status_code == 200:
                        child_soup = BeautifulSoup(child.text, "lxml")
                        for u in child_soup.find_all("url"):
                            loc_tag = u.find("loc")
                            if loc_tag:
                                pages.add(loc_tag.text.strip())
                            if len(pages) >= max_pages:
                                break
                except Exception:
                    pass
                if len(pages) >= max_pages:
                    break

            # Direct URL entries
            for u in soup.find_all("url"):
                loc = u.find("loc")
                if loc:
                    pages.add(loc.text.strip())
                if len(pages) >= max_pages:
                    break

            if pages:
                break

        except Exception:
            continue

    return list(pages)[:max_pages]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 fetch_page.py <url> [mode]")
        print("Modes: page (default), robots, llms, sitemap, full")
        sys.exit(1)

    target = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "page"

    if mode == "page":
        data = fetch_page(target)
    elif mode == "robots":
        data = fetch_robots(target)
    elif mode == "llms":
        data = fetch_llms_txt(target)
    elif mode == "sitemap":
        found = crawl_sitemap(target)
        data = {"pages": found, "count": len(found)}
    elif mode == "full":
        data = {
            "page": fetch_page(target),
            "robots": fetch_robots(target),
            "llms": fetch_llms_txt(target),
            "sitemap": crawl_sitemap(target),
        }
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)

    print(json.dumps(data, indent=2, default=str))
