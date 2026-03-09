# geo-audit-skill

Claude Code skill that audits any website for AI search engine optimization (GEO) and autofixes what it finds.

Analyzes how visible your site is to AI-powered search (ChatGPT, Claude, Perplexity, Gemini, Google AI Overviews) and generates fixes.

## What it does

**Audits 8 dimensions:**
- AI Citability — scores content passages for how likely AI models are to cite them
- AI Crawler Access — checks robots.txt for GPTBot, ClaudeBot, PerplexityBot, etc.
- llms.txt — checks for and generates the llms.txt standard file
- Structured Data / Schema — detects, validates, and generates JSON-LD
- Technical SEO — status codes, redirects, security headers, SSR, Core Web Vitals
- Content Quality & E-E-A-T — expertise signals, readability, freshness
- Brand Presence — mentions across Reddit, YouTube, Wikipedia, LinkedIn, etc.
- Platform Readiness — optimization for Google AI Overviews, ChatGPT, Perplexity, Gemini

**Autofixes in two modes:**
- **Auto-generate** — writes fix files directly to `geo-fixes/` (llms.txt, JSON-LD schemas, robots.txt additions, meta tags)
- **Recommend** — presents code-level changes (heading structure, meta descriptions, content rewrites) for your approval before touching any source files

## Install

Copy the skill directory to your Claude Code skills folder:

```bash
cp -r geo-audit-skill ~/.claude/skills/geo-audit
```

Or symlink it:

```bash
ln -s /path/to/geo-audit-skill ~/.claude/skills/geo-audit
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

1. **Fetches** homepage, robots.txt, sitemap, llms.txt
2. **Detects** business type (SaaS, e-commerce, local, publisher, agency)
3. **Runs 5 parallel analyses** via Claude Code subagents
4. **Reports** findings per category with severity levels
5. **Auto-generates** fix files to `geo-fixes/`
6. **Recommends** code-level changes and waits for approval

## Structure

```
geo-audit-skill/
├── SKILL.md              # Skill definition — orchestration and commands
├── scripts/
│   ├── fetch_page.py     # Page fetching, robots.txt, sitemap, llms.txt
│   ├── citability.py     # Passage-level AI citation scoring
│   └── schema_check.py   # JSON-LD detection, validation, recommendations
├── templates/
│   ├── llms.txt.j2       # llms.txt generation template
│   └── schema/           # JSON-LD templates by business type
│       ├── organization.json
│       ├── local-business.json
│       ├── article.json
│       ├── software.json
│       └── product.json
└── README.md
```

## No weighted scores

Each audit category reports its own findings independently. There's no composite "GEO Score" — the field is too new for anyone to credibly weight these dimensions. You interpret the priorities.

## License

MIT
