---
name: geo-audit
description: >
  GEO audit and autofix tool. Audits any website for AI search engine optimization
  (ChatGPT, Claude, Perplexity, Gemini, Google AI Overviews) and traditional SEO.
  Generates fix files automatically and recommends code-level changes for approval.
  Use when user says "geo", "seo", "audit", "AI search", "AI visibility",
  "citability", or provides a URL for analysis.
allowed-tools: Read, Grep, Glob, Bash, WebFetch, Write, Edit, Agent
---

# GEO Audit + Autofix — Claude Code Skill

> Audit any website for AI search visibility, then fix the problems.

---

## Commands

| Command | What It Does |
|---------|-------------|
| `/geo-audit <url>` | Full audit + autofix |
| `/geo-audit quick <url>` | Findings only, no fixes |

---

## Audit Flow

### Phase 1: Discovery (Sequential)

1. **Fetch the homepage** using the `fetch_page.py` script:
   ```bash
   python3 <skill-dir>/scripts/fetch_page.py <url> full
   ```
   This returns JSON with page data, robots.txt, llms.txt status, and sitemap pages.

2. **Detect business type** from the fetched data:
   - **SaaS** — pricing page, "sign up", "free trial", API docs, /app, /dashboard
   - **E-commerce** — product pages, cart, "add to cart", price elements
   - **Local Service** — phone number, address, "near me", Google Maps embed
   - **Publisher** — blog, articles, bylines, publication dates
   - **Agency** — portfolio, case studies, "our services", client logos
   - **Other** — default, apply general GEO best practices

3. **Identify key pages** from sitemap (up to 50 pages). Prioritize:
   - Homepage
   - About/team pages
   - Top content/blog pages
   - Product/service pages
   - Pricing page (if SaaS)

### Phase 2: Parallel Analysis (5 Subagents)

Launch these 5 analyses simultaneously using the Agent tool:

#### Agent 1: AI Citability + Content Quality
- Run citability scorer on up to 10 key pages:
  ```bash
  python3 <skill-dir>/scripts/citability.py <url>
  ```
- Score passages for AI citation readiness (answer block quality, self-containment, statistical density, structural readability, uniqueness signals)
- Assess E-E-A-T signals: author credentials, original research, expertise indicators
- Check content freshness: publication dates, last-modified headers, temporal references
- Evaluate readability: sentence length distribution, jargon density

#### Agent 2: AI Crawler Access + llms.txt
- Parse robots.txt results from Phase 1 fetch data
- Check status of these AI crawlers: GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, anthropic-ai, PerplexityBot, CCBot, Bytespider, cohere-ai, Google-Extended, GoogleOther, Applebot-Extended, FacebookBot, Amazonbot
- Check llms.txt and llms-full.txt existence and quality
- If llms.txt exists, validate its structure
- If llms.txt is missing, draft one based on site structure

#### Agent 3: Schema / Structured Data
- Run schema checker on homepage and key pages:
  ```bash
  python3 <skill-dir>/scripts/schema_check.py <url>
  ```
- Detect existing JSON-LD, microdata, RDFa
- Validate against schema.org specs
- Identify missing schema types based on business type
- Generate correct JSON-LD for missing schemas using templates in `templates/schema/`

#### Agent 4: Technical SEO
- Check from Phase 1 fetch data:
  - HTTP status codes and redirect chains
  - HTTPS enforcement
  - Security headers (HSTS, CSP, X-Frame-Options, etc.)
  - Canonical tags
  - Meta robots directives
  - Heading hierarchy (H1-H6 structure)
  - Image alt text coverage
  - Internal/external link structure
- Check SSR vs client-side rendering
- Check mobile meta viewport
- Use WebFetch to check Core Web Vitals via PageSpeed Insights:
  ```
  https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=<url>&strategy=mobile
  ```

#### Agent 5: Brand Mentions + Platform Optimization
- Search for the brand/site name across:
  - Reddit (site:reddit.com "<brand>")
  - YouTube (site:youtube.com "<brand>")
  - Wikipedia mentions
  - LinkedIn presence
  - GitHub presence (if relevant)
  - Industry directories
- Assess platform-specific optimization:
  - **Google AI Overviews**: structured data, E-E-A-T, featured snippet formatting
  - **ChatGPT**: citability score, llms.txt, clear definitions
  - **Perplexity**: source diversity, recency, factual density
  - **Gemini**: Google entity recognition, Knowledge Panel eligibility

### Phase 3: Report

Present findings grouped by category. For each category:
- Current state (what exists now)
- Issues found (with severity: Critical / High / Medium / Low)
- Specific findings with evidence

**Do NOT compute a weighted composite score.** Report each category independently. Let the user interpret priorities.

Categories to report:
1. AI Citability
2. AI Crawler Access
3. llms.txt Status
4. Structured Data / Schema
5. Technical SEO
6. Content Quality & E-E-A-T
7. Brand Presence
8. Platform Readiness

### Phase 4: Autofix

**Auto-generate** (write immediately to `geo-fixes/` in current working directory):
- `geo-fixes/llms.txt` — ready-to-deploy llms.txt file
- `geo-fixes/llms-full.txt` — detailed version
- `geo-fixes/schema/` — JSON-LD files for each missing schema type
- `geo-fixes/robots-txt-additions.txt` — recommended robots.txt additions for AI crawlers
- `geo-fixes/meta-tags.html` — optimized meta tag snippets
- `geo-fixes/FINDINGS.md` — full audit report in markdown

**Recommend for approval** (present to user, do NOT implement until approved):
- Heading structure changes (H1/H2/H3 hierarchy fixes)
- Meta description rewrites
- Content restructuring for citability (passage length, answer blocks)
- Alt text additions for images
- Internal linking improvements
- Any changes to existing source code files

Present code-level recommendations as a numbered list with:
- File path (if in a repo context)
- Current state
- Recommended change
- Why it helps AI visibility

Wait for user to approve specific items before making any code edits.

---

## Script Reference

### fetch_page.py
```
python3 scripts/fetch_page.py <url> [mode]
```
Modes: `page`, `robots`, `llms`, `sitemap`, `blocks`, `full`

Returns JSON to stdout.

### citability.py
```
python3 scripts/citability.py <url>
```
Returns JSON with per-passage citability scores and page-level summary.

### schema_check.py
```
python3 scripts/schema_check.py <url>
```
Returns JSON with detected schemas, validation results, and missing schema recommendations.

---

## Business Type Adaptations

Adjust recommendations based on detected type:

| Type | Key Schema | Key Recommendations |
|------|-----------|-------------------|
| SaaS | SoftwareApplication, Organization | Comparison pages, feature definitions, pricing structured data |
| E-commerce | Product, Offer, AggregateRating | Product descriptions as answer blocks, review aggregation |
| Local | LocalBusiness, GeoCoordinates | Google Business Profile, local citations, service area pages |
| Publisher | Article, Person, Organization | Author pages, E-E-A-T signals, topic clusters |
| Agency | Organization, Service | Case studies as citable content, portfolio schema |

---

## Quality Gates

- Max 50 pages crawled per audit
- 30-second timeout per page fetch
- 1-second delay between requests
- Always respect robots.txt
- Skip pages with >80% content similarity
