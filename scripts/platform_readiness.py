#!/usr/bin/env python3
"""
Platform readiness composite scorer for GEO audit.

Computes per-platform readiness scores using weighted combinations of
other dimension scores:

  Google AI Overviews = schema 50% + eeat 50%
  ChatGPT             = citability 50% + llms_txt 50%
  Claude              = citability 40% + llms_txt 30% + eeat 30%
  Perplexity          = technical_seo 50% + citability 50%
  Gemini              = schema 40% + brand_presence 30% + eeat 30%

Reads a JSON object from stdin containing dimension results, e.g.:
{
  "schema": {"score": 72},
  "eeat": {"score": 65},
  "citability": {"score": 80},
  "llms_txt": {"score": 45},
  "technical_seo": {"score": 90},
  "brand_presence": {"score": 55}
}

Or accepts individual scores as positional arguments:
  python3 platform_readiness.py <schema> <eeat> <citability> <llms_txt> <tech_seo> <brand>
"""

import sys
import json


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


def analyze_platform_readiness(scores):
    """
    Compute platform readiness from dimension scores.

    scores is a dict with keys: schema, eeat, citability, llms_txt,
    technical_seo, brand_presence — each mapping to a numeric score (0-100).
    """
    schema = scores.get("schema", 0)
    eeat = scores.get("eeat", 0)
    citability = scores.get("citability", 0)
    llms_txt = scores.get("llms_txt", 0)
    technical_seo = scores.get("technical_seo", 0)
    brand_presence = scores.get("brand_presence", 0)

    findings = []

    # --- Google AI Overviews ---
    google_score = round(schema * 0.5 + eeat * 0.5)
    google_recs = []
    if schema < 65:
        google_recs.append("Improve structured data (JSON-LD schemas)")
    if eeat < 65:
        google_recs.append("Strengthen E-E-A-T signals (authorship, credentials, dates)")

    # --- ChatGPT ---
    chatgpt_score = round(citability * 0.5 + llms_txt * 0.5)
    chatgpt_recs = []
    if citability < 65:
        chatgpt_recs.append("Improve content citability (clear definitions, self-contained blocks)")
    if llms_txt < 65:
        chatgpt_recs.append("Create or improve llms.txt file")

    # --- Claude ---
    claude_score = round(citability * 0.4 + llms_txt * 0.3 + eeat * 0.3)
    claude_recs = []
    if citability < 65:
        claude_recs.append("Improve content citability with clear, self-contained passages")
    if llms_txt < 65:
        claude_recs.append("Create or improve llms.txt for context")
    if eeat < 65:
        claude_recs.append("Strengthen expertise and trust signals")

    # --- Perplexity ---
    perplexity_score = round(technical_seo * 0.5 + citability * 0.5)
    perplexity_recs = []
    if technical_seo < 65:
        perplexity_recs.append("Fix technical SEO issues (HTTPS, canonicals, SSR)")
    if citability < 65:
        perplexity_recs.append("Write more citable, fact-dense content blocks")

    # --- Gemini ---
    gemini_score = round(schema * 0.4 + brand_presence * 0.3 + eeat * 0.3)
    gemini_recs = []
    if schema < 65:
        gemini_recs.append("Add comprehensive structured data")
    if brand_presence < 65:
        gemini_recs.append("Increase brand presence across social and review platforms")
    if eeat < 65:
        gemini_recs.append("Strengthen E-E-A-T signals")

    platforms = [
        {
            "name": "Google AI Overviews",
            "score": google_score,
            "grade": to_grade(google_score),
            "components": [
                {"dimension": "schema", "weight": 0.5},
                {"dimension": "eeat", "weight": 0.5},
            ],
            "recommendations": google_recs,
        },
        {
            "name": "ChatGPT",
            "score": chatgpt_score,
            "grade": to_grade(chatgpt_score),
            "components": [
                {"dimension": "citability", "weight": 0.5},
                {"dimension": "llms_txt", "weight": 0.5},
            ],
            "recommendations": chatgpt_recs,
        },
        {
            "name": "Claude",
            "score": claude_score,
            "grade": to_grade(claude_score),
            "components": [
                {"dimension": "citability", "weight": 0.4},
                {"dimension": "llms_txt", "weight": 0.3},
                {"dimension": "eeat", "weight": 0.3},
            ],
            "recommendations": claude_recs,
        },
        {
            "name": "Perplexity",
            "score": perplexity_score,
            "grade": to_grade(perplexity_score),
            "components": [
                {"dimension": "technical_seo", "weight": 0.5},
                {"dimension": "citability", "weight": 0.5},
            ],
            "recommendations": perplexity_recs,
        },
        {
            "name": "Gemini",
            "score": gemini_score,
            "grade": to_grade(gemini_score),
            "components": [
                {"dimension": "schema", "weight": 0.4},
                {"dimension": "brand_presence", "weight": 0.3},
                {"dimension": "eeat", "weight": 0.3},
            ],
            "recommendations": gemini_recs,
        },
    ]

    # Generate findings per platform
    for platform in platforms:
        if platform["score"] >= 65:
            severity = "pass"
        elif platform["score"] >= 50:
            severity = "medium"
        elif platform["score"] >= 35:
            severity = "high"
        else:
            severity = "critical"

        if platform["recommendations"]:
            description = (
                f"Score: {platform['score']}/100 ({platform['grade']}). "
                f"To improve: {'; '.join(platform['recommendations'])}."
            )
        else:
            description = (
                f"Score: {platform['score']}/100 ({platform['grade']}). "
                "Your site is well-optimized for this platform."
            )

        slug = platform["name"].lower().replace(" ", "-")
        findings.append({
            "id": f"platform-{slug}",
            "dimension": "platform_readiness",
            "severity": severity,
            "title": f"{platform['name']}: {platform['grade']} ({platform['score']}/100)",
            "description": description,
        })

    # Overall score = average of all platform scores
    overall_score = round(sum(p["score"] for p in platforms) / len(platforms))
    grade = to_grade(overall_score)

    best = max(platforms, key=lambda p: p["score"])
    worst = min(platforms, key=lambda p: p["score"])

    summary = (
        f"Platform readiness: {overall_score}/100. "
        f"Best: {best['name']} ({best['score']}). "
        f"Weakest: {worst['name']} ({worst['score']})."
    )

    return {
        "dimension": "platform_readiness",
        "score": overall_score,
        "grade": grade,
        "summary": summary,
        "platforms": platforms,
        "findings": findings,
    }


def _extract_scores(raw):
    """Extract dimension scores from various input formats."""
    scores = {}
    dimension_keys = [
        "schema", "eeat", "citability", "llms_txt",
        "technical_seo", "brand_presence",
    ]

    for key in dimension_keys:
        if key in raw:
            val = raw[key]
            if isinstance(val, dict):
                scores[key] = val.get("score", 0)
            elif isinstance(val, (int, float)):
                scores[key] = val
            else:
                scores[key] = 0
        else:
            scores[key] = 0

    return scores


if __name__ == "__main__":
    # If stdin has data, read it as JSON
    if not sys.stdin.isatty():
        try:
            raw = json.load(sys.stdin)
            scores = _extract_scores(raw)
            print(json.dumps(
                analyze_platform_readiness(scores), indent=2, default=str
            ))
            sys.exit(0)
        except (json.JSONDecodeError, KeyError) as e:
            print(json.dumps({"error": f"Invalid JSON input: {e}"}))
            sys.exit(1)

    # Positional arguments: schema eeat citability llms_txt tech_seo brand
    if len(sys.argv) == 7:
        try:
            scores = {
                "schema": int(sys.argv[1]),
                "eeat": int(sys.argv[2]),
                "citability": int(sys.argv[3]),
                "llms_txt": int(sys.argv[4]),
                "technical_seo": int(sys.argv[5]),
                "brand_presence": int(sys.argv[6]),
            }
            print(json.dumps(
                analyze_platform_readiness(scores), indent=2, default=str
            ))
            sys.exit(0)
        except ValueError:
            pass

    print("Usage: python3 platform_readiness.py <schema> <eeat> <citability> <llms_txt> <tech_seo> <brand>")
    print("   or: echo '{\"schema\":{\"score\":72},\"eeat\":{\"score\":65},...}' | python3 platform_readiness.py")
    sys.exit(1)
