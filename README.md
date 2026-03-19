# geo-audit-skill

**Audit any website for AI search visibility. Get fixes you can deploy today.**

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill that checks how well your site can be found by ChatGPT, Claude, Perplexity, Gemini, and Google AI Overviews — then tells you exactly what to fix, with step-by-step instructions for your specific platform (WordPress, Squarespace, Wix, Shopify, etc.).

## What it checks

We audit 11 dimensions of AI search readiness:

| Dimension | What it measures |
|-----------|-----------------|
| **AI Citability** | Can AI models extract and quote your content? Scores passages for citation readiness, FAQ/snippet detection, conversational tone, entity density, semantic topic coverage, LLM chunk sizing, and keyword density. |
| **Crawler Access** | Are the 30+ AI crawlers (GPTBot, ClaudeBot, PerplexityBot, etc.) allowed in your robots.txt? |
| **llms.txt** | Do you have the llms.txt file that helps AI understand your site? Like robots.txt, but for AI comprehension. |
| **Structured Data** | Is your JSON-LD schema complete? Checks for Organization, WebSite, and business-specific schemas. |
| **Technical SEO** | 13 checks: HTTPS, headings, meta tags, page speed, security headers, SSR, alt text, and more. |
| **E-E-A-T Signals** | 9 trust signals: author bylines, credentials, publication dates, citations, contact info, and more. |
| **Brand Presence** | Social profiles, review platforms (G2, Trustpilot), About page, press page, Schema.org sameAs links. |
| **Platform Readiness** | Per-engine scores for Google AI Overviews, ChatGPT, Claude, Perplexity, and Gemini. |
| **Search Intent** | Is your page type aligned with its search intent? Classifies pages as informational, commercial, transactional, or navigational and flags mismatches. |
| **Content Freshness** | How old is your content? Detects dates from meta tags, JSON-LD, visible text, and HTTP headers. Flags stale content that AI models may deprioritize. |
| **Internal Links** | Is your content well-connected? Checks link density, anchor text quality, hub-and-spoke patterns, and sitemap coverage. |

<details>
<summary><strong>Full list of 32 AI crawlers checked</strong></summary>

| Crawler | Operator |
|---------|----------|
| GPTBot | OpenAI |
| OAI-SearchBot | OpenAI |
| ChatGPT-User | OpenAI |
| ClaudeBot | Anthropic |
| anthropic-ai | Anthropic |
| PerplexityBot | Perplexity |
| Google-Extended | Google |
| GoogleOther | Google |
| GoogleOther-Image | Google |
| GoogleOther-Video | Google |
| Applebot-Extended | Apple |
| Bytespider | ByteDance / TikTok |
| TikTokSpider | ByteDance / TikTok |
| CCBot | Common Crawl |
| cohere-ai | Cohere |
| cohere-training-data-crawler | Cohere |
| FacebookBot | Meta |
| Meta-ExternalAgent | Meta |
| Meta-ExternalFetcher | Meta |
| Amazonbot | Amazon |
| DuckAssistBot | DuckDuckGo |
| YouBot | You.com |
| AI2Bot | Allen AI |
| Ai2Bot-Dolma | Allen AI |
| Diffbot | Diffbot |
| ImagesiftBot | ImagesiftBot |
| aiHitBot | aiHit |
| img2dataset | LAION |
| MyCentralAIScraperBot | MyCentralAI |
| omgili | Webz.io |
| omgilibot | Webz.io |
| Quora-Bot | Quora |

</details>

## Platform detection

We automatically detect 15 website platforms and tailor recommendations:

WordPress, WordPress.com, Squarespace, Wix, Shopify, Webflow, Ghost, Framer, HubSpot, Carrd, Weebly, Drupal, Next.js, Vercel, Netlify

Instead of "edit your robots.txt file", you get "In Squarespace, go to Settings > Website > SEO > robots.txt."

## Install

```bash
npx skills add ArtSabintsev/geo-audit-skill
```

### Dependencies

```bash
pip install requests beautifulsoup4 lxml
```

## Usage

In Claude Code:

```
/geo-audit https://example.com          # Full audit + autofix
/geo-audit quick https://example.com    # Findings only, no fixes
```

## How it works

1. **Fetches** your homepage, robots.txt, sitemap, and llms.txt
2. **Detects** your platform (WordPress, Squarespace, Wix, etc.) and business type (SaaS, e-commerce, local, publisher, agency)
3. **Runs 11 parallel analyses** via Claude Code subagents — one per dimension
4. **Reports** findings by dimension with severity levels and confidence labels (Confirmed, Likely, Hypothesis)
5. **Auto-generates** fix files to `geo-fixes/` — robots.txt, llms.txt, JSON-LD schemas, meta tags
6. **AI-generates** meta descriptions, alt text, heading restructures, FAQ sections, and content gap analysis
7. **Suggests rewrites** for the weakest citability passages with before/after examples
8. **Recommends** code-level changes and waits for your approval before touching source files

## What gets fixed automatically

These files are written directly to `geo-fixes/` in your project:

- `llms.txt` — ready-to-deploy AI context file for your site
- `llms-full.txt` — detailed version with full page content
- `schema/*.json` — JSON-LD files for each missing schema type
- `robots-txt-additions.txt` — robots.txt rules to allow AI crawlers
- `meta-tags.html` — optimized meta tag snippets
- `FINDINGS.md` — full audit report in markdown

## AI-powered suggestions

Claude uses the audit data to generate contextual, site-specific recommendations:

- **Meta description rewrites** — optimized 120-160 char descriptions for pages with missing or weak meta tags
- **Alt text generation** — descriptive alt text based on image filenames and surrounding content
- **Heading restructure** — proposed H1/H2/H3 hierarchy with FAQ-style question headings
- **FAQ section drafting** — Q&A pairs the page implicitly answers + ready-to-use FAQPage JSON-LD schema
- **Content gap analysis** — subtopics and questions the page should cover but doesn't, tailored to business type
- **Robots.txt crawler explainer** — what each blocked crawler does, the tradeoff, and whether to allow it

## What needs your approval

These changes are recommended but not made until you say yes:

- Heading structure fixes (H1/H2/H3 hierarchy)
- AI-generated meta description rewrites
- Content restructuring for better AI citability
- Passage rewrites for weak citability scores (before/after with reasoning)
- AI-generated alt text for images
- FAQ sections and schema markup
- Internal linking improvements
- Any edits to your existing source code

## Structure

```
geo-audit-skill/
├── SKILL.md              # Skill definition and orchestration
├── scripts/
│   ├── fetch_page.py     # Page fetching + platform detection + robots.txt + sitemap + llms.txt
│   ├── citability.py     # AI citation scoring, FAQ detection, entity/topic analysis, chunk sizing, keyword density
│   ├── schema_check.py   # JSON-LD detection, validation, and generation
│   ├── technical_seo.py  # 13 weighted technical checks
│   ├── eeat.py           # 9 E-E-A-T trust signals
│   ├── brand_presence.py # Social, review, and brand page detection
│   ├── llms_txt.py       # llms.txt quality and spec compliance
│   ├── platform_readiness.py  # Per-AI-engine readiness scores
│   ├── search_intent.py  # Search intent classification + page type alignment
│   ├── content_freshness.py   # Publication/modification date detection + staleness scoring
│   └── internal_links.py # Link density, anchor quality, hub patterns, sitemap coverage
├── templates/
│   ├── llms.txt.j2       # llms.txt generation template
│   └── schema/           # JSON-LD templates by business type
└── README.md
```

## Who this is for

- **Marketing managers** who want their company to show up in AI search results
- **Small business owners** who use WordPress, Squarespace, or Wix and want to be found by ChatGPT and Perplexity
- **SEO professionals** adding AI optimization to their toolkit
- **Developers** who want to audit client sites from the command line
- **Agency teams** running GEO audits for clients

## Confidence labels

Every finding includes a confidence label so you know what to trust:

| Label | Meaning | Example |
|-------|---------|---------|
| **Confirmed** | Directly verified from the page | Missing HTTPS, no H1 tag, blocked crawler in robots.txt |
| **Likely** | Based on heuristic analysis | SSR detection, E-E-A-T regex signals, composite platform scores |
| **Hypothesis** | Suggested improvement, may not apply | "Add a data table", "Add FAQ content" |

## What is GEO?

GEO stands for Generative Engine Optimization. It's like SEO, but for AI search engines.

Traditional SEO helps you rank on Google. GEO helps AI models (ChatGPT, Claude, Perplexity, Google AI Overviews) find, understand, and cite your content when people ask questions.

The two overlap but they're not the same. A site can rank #1 on Google but be completely invisible to AI if it blocks AI crawlers, lacks structured data, or has content that's hard for AI to extract.

## Keeping the crawler list up to date

The AI crawler list is based on [ai-robots-txt/ai.robots.txt](https://github.com/ai-robots-txt/ai.robots.txt), the community-maintained canonical list of AI bot user-agents. Check that repo periodically for new crawlers.

## License

MIT
