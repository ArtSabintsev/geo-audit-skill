---
name: geo-audit
description: >
  GEO audit and autofix tool. Audits any website for AI search engine optimization
  (ChatGPT, Claude, Perplexity, Gemini, Google AI Overviews) and traditional SEO.
  Generates fix files automatically and recommends code-level changes for approval.
  Use when user says "geo", "seo", "audit", "AI search", "AI visibility",
  "citability", or provides a URL for analysis.
user-invocable: true
argument-hint: <url> or quick <url>
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
   python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_page.py <url> full
   ```
   This returns JSON with page data (including language, viewport, OG tags, meta robots, X-Robots-Tag, response time, detected platform), robots.txt, llms.txt status, and sitemap pages.

   The script auto-detects 15 platforms: WordPress, WordPress.com, Squarespace, Wix, Shopify, Webflow, Ghost, Framer, HubSpot, Carrd, Weebly, Drupal, Next.js, Vercel, Netlify. The `detected_platform` field will be `{"name": "Squarespace", "slug": "squarespace"}` or `null`.

   **When a platform is detected**, tailor all fix recommendations to that platform. For example:
   - WordPress: "Install Yoast SEO plugin, go to Yoast SEO > Tools > File Editor"
   - Squarespace: "Go to Settings > Website > SEO > robots.txt"
   - Wix: "Go to Dashboard > Marketing & SEO > SEO Tools > robots.txt Editor"
   - Shopify: "Go to Online Store > Themes > Edit Code > robots.txt.liquid"

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

### Phase 2: Parallel Analysis (8 Subagents)

Launch these 8 analyses simultaneously using the Agent tool:

#### Agent 1: AI Citability + Content Quality
- Run citability scorer on up to 10 key pages:
  ```bash
  python3 ${CLAUDE_SKILL_DIR}/scripts/citability.py <url>
  ```
- Score passages for AI citation readiness (answer block quality, self-containment, statistical density, structural readability, uniqueness signals)
- Detects comparison patterns, how-to/instructional content, cause-effect language
- Enhanced self-containment: flags dangling pronouns, context-reference phrases
- Page-level findings: data table detection (>500 word pages), heading structure validation (>50% blocks without headings)
- FAQ/featured snippet detection: Q&A headings, definition patterns ("What is..."), numbered step lists, direct answer quality

#### Agent 2: AI Crawler Access + llms.txt Quality
- Parse robots.txt results from Phase 1 fetch data
- Check status of these AI crawlers: GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, anthropic-ai, PerplexityBot, CCBot, Bytespider, cohere-ai, cohere-training-data-crawler, Google-Extended, GoogleOther, GoogleOther-Image, GoogleOther-Video, Applebot-Extended, FacebookBot, Amazonbot, Meta-ExternalAgent, Meta-ExternalFetcher, YouBot, AI2Bot, Ai2Bot-Dolma, Diffbot, ImagesiftBot, aiHitBot, DuckAssistBot, img2dataset, MyCentralAIScraperBot, omgili, omgilibot, Quora-Bot, TikTokSpider
- Run llms.txt quality scorer:
  ```bash
  python3 ${CLAUDE_SKILL_DIR}/scripts/llms_txt.py <url>
  ```
- Scores existence, content length, markdown structure (# title, > description, ## sections), key pages section, about section, markdown link format, llms-full.txt bonus
- If llms.txt is missing, draft one based on site structure

#### Agent 3: Schema / Structured Data
- Run schema checker on homepage and key pages:
  ```bash
  python3 ${CLAUDE_SKILL_DIR}/scripts/schema_check.py <url>
  ```
- Detect existing JSON-LD, microdata, RDFa
- Validate against schema.org specs including @context validation (missing or non-standard @context)
- Identify missing schema types based on business type
- Generate correct JSON-LD for missing schemas using templates in `templates/schema/`

#### Agent 4: Technical SEO (13 checks)
- Run the technical SEO analyzer:
  ```bash
  python3 ${CLAUDE_SKILL_DIR}/scripts/technical_seo.py <url>
  ```
  Or pipe Phase 1 data:
  ```bash
  python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_page.py <url> full | python3 ${CLAUDE_SKILL_DIR}/scripts/technical_seo.py
  ```
- 13 weighted checks: HTTPS, redirect chain, canonical tag, H1 count, meta description length, word count (300+), security headers, SSR detection, viewport meta, language attribute, Open Graph tags, response time (<3s), image alt text coverage (80%+)
- Optionally check Core Web Vitals via PageSpeed Insights:
  ```
  https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=<url>&strategy=mobile
  ```

#### Agent 5: E-E-A-T Analysis (9 signals)
- Run the E-E-A-T analyzer:
  ```bash
  python3 ${CLAUDE_SKILL_DIR}/scripts/eeat.py <url>
  ```
  Or pipe Phase 1 data:
  ```bash
  python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_page.py <url> full | python3 ${CLAUDE_SKILL_DIR}/scripts/eeat.py
  ```
- 9 weighted signals: author bylines, publication dates, citation language, credentials, contact information, about page link, trust indicators, first-party expertise, schema.org authorship
- Each signal has a weight; score = (earned weight / total weight) * 100

#### Agent 6: Brand Presence
- Run the brand presence analyzer:
  ```bash
  python3 ${CLAUDE_SKILL_DIR}/scripts/brand_presence.py <url>
  ```
  Or pipe Phase 1 data:
  ```bash
  python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_page.py <url> full | python3 ${CLAUDE_SKILL_DIR}/scripts/brand_presence.py
  ```
- Social media links (10 platforms: Twitter/X, LinkedIn, GitHub, YouTube, Wikipedia, Instagram, Facebook, TikTok, Reddit, Crunchbase)
- Review site links (5 platforms: G2, Capterra, Trustpilot, Product Hunt, Yelp)
- Brand pages (/about, /press, /media, /newsroom, /news)
- Schema.org sameAs links in structured data

#### Agent 7: Platform Readiness (composite)
- Run after all other dimension scores are available:
  ```bash
  echo '{"schema":72,"eeat":65,"citability":80,"llms_txt":45,"technical_seo":90,"brand_presence":55}' \
    | python3 ${CLAUDE_SKILL_DIR}/scripts/platform_readiness.py
  ```
- Computes per-platform readiness:
  - **Google AI Overviews**: schema 50% + eeat 50%
  - **ChatGPT**: citability 50% + llms_txt 50%
  - **Claude**: citability 40% + llms_txt 30% + eeat 30%
  - **Perplexity**: technical_seo 50% + citability 50%
  - **Gemini**: schema 40% + brand_presence 30% + eeat 30%
- Overall score = average of all 5 platform scores

#### Agent 8: Brand Mentions (Web Search)
- Search for the brand/site name across:
  - Reddit (site:reddit.com "<brand>")
  - YouTube (site:youtube.com "<brand>")
  - Wikipedia mentions
  - LinkedIn presence
  - GitHub presence (if relevant)
  - Industry directories

### Phase 3: Report

Present findings grouped by category. For each category:
- Current state (what exists now)
- Issues found (with severity: Critical / High / Medium / Low)
- Confidence label for each finding:
  - **Confirmed** — directly verified (e.g., missing HTTPS, no H1 tag, absent robots.txt entry)
  - **Likely** — based on heuristic analysis (e.g., SSR detection, regex-based E-E-A-T signals, composite platform scores)
  - **Hypothesis** — suggested improvement, may not apply to every site (e.g., missing data tables, FAQ content suggestions)
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

**Content rewrite suggestions** — For the 3-5 weakest citability passages (lowest scores from citability.py), generate a rewritten version that:
- Starts with a clear declarative sentence (5-30 words) that directly answers the implied question
- Stays within the optimal 134-167 word passage length
- Replaces dangling pronouns with proper nouns
- Adds statistical density where appropriate (numbers, percentages, named sources)
- Structures as Q&A, definition, or how-to format when the topic allows

Present each rewrite as:
- **Original** (first 50 words + score)
- **Suggested rewrite** (full passage)
- **Why** (which citability factors improve)

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
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_page.py <url> [mode]
```
Modes: `page`, `robots`, `llms`, `sitemap`, `full`

Returns JSON to stdout. Page mode includes: language attribute, viewport meta, Open Graph tags, meta robots, X-Robots-Tag header, response time (ms), and checks 20 AI crawlers.

### citability.py
```
python3 ${CLAUDE_SKILL_DIR}/scripts/citability.py <url>
```
Returns JSON with per-passage citability scores, page-level summary, and structural findings (data table detection, heading structure validation).

### schema_check.py
```
python3 ${CLAUDE_SKILL_DIR}/scripts/schema_check.py <url>
```
Returns JSON with detected schemas, validation results (including @context validation), and missing schema recommendations.

### eeat.py
```
python3 ${CLAUDE_SKILL_DIR}/scripts/eeat.py <url>
```
Or pipe from fetch_page.py:
```
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_page.py <url> full | python3 ${CLAUDE_SKILL_DIR}/scripts/eeat.py
```
Returns JSON with 9 E-E-A-T signals, per-signal weights, overall score, grade, and findings.

### brand_presence.py
```
python3 ${CLAUDE_SKILL_DIR}/scripts/brand_presence.py <url>
```
Or pipe from fetch_page.py:
```
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_page.py <url> full | python3 ${CLAUDE_SKILL_DIR}/scripts/brand_presence.py
```
Returns JSON with social platform presence (10), review platforms (5), brand pages, sameAs detection, score, and findings.

### technical_seo.py
```
python3 ${CLAUDE_SKILL_DIR}/scripts/technical_seo.py <url>
```
Or pipe from fetch_page.py:
```
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_page.py <url> full | python3 ${CLAUDE_SKILL_DIR}/scripts/technical_seo.py
```
Returns JSON with 13 weighted technical checks, per-check pass/fail, overall score, grade, and findings.

### llms_txt.py
```
python3 ${CLAUDE_SKILL_DIR}/scripts/llms_txt.py <url>
```
Or pipe from fetch_page.py:
```
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_page.py <url> full | python3 ${CLAUDE_SKILL_DIR}/scripts/llms_txt.py
```
Returns JSON with llms.txt quality score, spec compliance checks, and findings.

### platform_readiness.py
```
python3 ${CLAUDE_SKILL_DIR}/scripts/platform_readiness.py <schema> <eeat> <citability> <llms_txt> <tech_seo> <brand>
```
Or pipe dimension scores as JSON:
```
echo '{"schema":72,"eeat":65,"citability":80,"llms_txt":45,"technical_seo":90,"brand_presence":55}' \
  | python3 ${CLAUDE_SKILL_DIR}/scripts/platform_readiness.py
```
Returns JSON with per-platform readiness scores (Google AI Overviews, ChatGPT, Claude, Perplexity, Gemini), recommendations, and overall score.

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
