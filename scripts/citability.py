#!/usr/bin/env python3
"""
Citability scorer — scores content passages for AI citation readiness.

Evaluates how likely an AI model is to cite a given passage based on:
- Answer block quality: does it directly answer a question?
- Self-containment: can it be extracted without surrounding context?
- Structural readability: sentence length, lists, clarity
- Statistical density: numbers, sources, specifics
- Uniqueness signals: original data, case studies
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


def score_passage(text, heading=None):
    """Score a single passage for AI citability (0-100)."""
    words = text.split()
    word_count = len(words)
    if word_count < 10:
        return None

    scores = {}

    # --- Answer Block Quality (0-30) ---
    abq = 0

    definition_patterns = [
        r"\b\w+\s+is\s+(?:a|an|the)\s",
        r"\b\w+\s+refers?\s+to\s",
        r"\b\w+\s+means?\s",
        r"\b\w+\s+(?:can be |are )?defined\s+as\s",
    ]
    if any(re.search(p, text, re.I) for p in definition_patterns):
        abq += 15

    # Comparison patterns (vs, compared to, difference between)
    comparison_patterns = [
        r"\bvs\.?\s+",
        r"\bcompared\s+to\b",
        r"\bdifference\s+between\b",
        r"\b(?:better|worse)\s+than\b",
        r"\b(?:advantages?|disadvantages?|pros?|cons?)\b",
    ]
    if any(re.search(p, text, re.I) for p in comparison_patterns):
        abq += 5

    # How-to / instructional patterns
    howto_patterns = [
        r"\bhow\s+to\b",
        r"\bstep\s+\d+\b",
        r"\bfollow\s+these\s+steps\b",
        r"\bhere(?:'s| is)\s+(?:how|what)\b",
        r"\b(?:first|next|then|finally),?\s+\w+",
    ]
    if any(re.search(p, text, re.I) for p in howto_patterns):
        abq += 5

    # Cause-effect patterns
    cause_effect_patterns = [
        r"\b(?:because|therefore|consequently|as a result)\b",
        r"\b(?:leads? to|results? in|causes?|due to)\b",
        r"\b(?:if|when)\s+.+?,?\s+(?:then|it)\b",
    ]
    if any(re.search(p, text, re.I) for p in cause_effect_patterns):
        abq += 3

    first_60 = " ".join(words[:60])
    if re.search(r"(?:\d+%|\$[\d,]+|\d+\s+(?:million|billion))", first_60):
        abq += 10

    if heading and heading.strip().endswith("?"):
        abq += 10

    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    clear = sum(1 for s in sentences if 5 <= len(s.split()) <= 25)
    if sentences:
        abq += int((clear / len(sentences)) * 10)

    if re.search(r"(?:according to|research shows|studies? (?:show|indicate|found))", text, re.I):
        abq += 5

    scores["answer_block_quality"] = min(abq, 30)

    # --- Self-Containment (0-25) ---
    sc = 0

    if 134 <= word_count <= 167:
        sc += 10
    elif 100 <= word_count <= 200:
        sc += 7
    elif 80 <= word_count <= 250:
        sc += 4
    elif 30 <= word_count <= 400:
        sc += 2

    pronouns = len(re.findall(
        r"\b(?:it|they|them|their|this|that|these|those|he|she|his|her)\b", text, re.I
    ))
    ratio = pronouns / word_count if word_count else 1
    if ratio < 0.02:
        sc += 8
    elif ratio < 0.04:
        sc += 5
    elif ratio < 0.06:
        sc += 3

    proper_nouns = len(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text))
    if proper_nouns >= 3:
        sc += 7
    elif proper_nouns >= 1:
        sc += 4

    # Penalty: dangling pronouns at start of passage
    first_sentence = sentences[0] if sentences else ""
    first_words = first_sentence.split()[:3]
    dangling_starts = {"it", "this", "that", "these", "those", "they", "he", "she"}
    if first_words and first_words[0].lower() in dangling_starts:
        sc -= 3

    # Penalty: context-reference phrases that require surrounding text
    context_refs = [
        r"\bas\s+(?:mentioned|noted|described|discussed)\s+(?:above|below|earlier|previously)\b",
        r"\b(?:the\s+)?(?:above|below|following|preceding)\s+(?:section|paragraph|table|chart)\b",
        r"\bsee\s+(?:above|below)\b",
        r"\bas\s+we\s+(?:saw|discussed|mentioned)\b",
    ]
    if any(re.search(p, text, re.I) for p in context_refs):
        sc -= 4

    # Bonus: starts with a complete declarative sentence
    if first_words and len(first_words) >= 3:
        if not first_words[0].lower() in dangling_starts:
            sc += 2

    scores["self_containment"] = min(max(sc, 0), 25)

    # --- Structural Readability (0-20) ---
    sr = 0

    if sentences:
        avg_len = word_count / len(sentences)
        if 10 <= avg_len <= 20:
            sr += 8
        elif 8 <= avg_len <= 25:
            sr += 5
        else:
            sr += 2

    if re.search(r"(?:first|second|third|finally|additionally|moreover)", text, re.I):
        sr += 4
    if re.search(r"(?:\d+[\.\)]\s|\b(?:step|tip|point)\s+\d+)", text, re.I):
        sr += 4
    if "\n" in text:
        sr += 4

    scores["structural_readability"] = min(sr, 20)

    # --- Statistical Density (0-15) ---
    sd = 0

    sd += min(len(re.findall(r"\d+(?:\.\d+)?%", text)) * 3, 6)
    sd += min(len(re.findall(r"\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|M|B|K))?", text)) * 3, 5)
    sd += min(len(re.findall(
        r"\b\d+(?:,\d{3})*(?:\.\d+)?\s+(?:users|customers|pages|sites|companies|people|percent|times)",
        text, re.I
    )) * 2, 4)

    if re.search(r"\b20(?:2[0-9]|1\d)\b", text):
        sd += 2

    if re.search(r"(?:according to|per|from|by)\s+[A-Z]", text):
        sd += 2

    scores["statistical_density"] = min(sd, 15)

    # --- Uniqueness Signals (0-10) ---
    us = 0

    if re.search(r"(?:our (?:research|study|data|analysis|findings)|we (?:found|discovered|analyzed))", text, re.I):
        us += 5
    if re.search(r"(?:case study|for example|for instance|in practice|real-world)", text, re.I):
        us += 3
    if re.search(r"(?:using|with|via|through)\s+[A-Z][a-z]+", text):
        us += 2

    scores["uniqueness_signals"] = min(us, 10)

    total = sum(scores.values())

    if total >= 80:
        grade, label = "A", "Highly Citable"
    elif total >= 65:
        grade, label = "B", "Good Citability"
    elif total >= 50:
        grade, label = "C", "Moderate Citability"
    elif total >= 35:
        grade, label = "D", "Low Citability"
    else:
        grade, label = "F", "Poor Citability"

    return {
        "heading": heading,
        "word_count": word_count,
        "total_score": total,
        "grade": grade,
        "label": label,
        "breakdown": scores,
        "preview": " ".join(words[:30]) + ("..." if word_count > 30 else ""),
    }


def analyze_page(url):
    """Analyze all content blocks on a page for citability."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return {"error": f"Failed to fetch: {e}"}

    soup = BeautifulSoup(resp.text, "lxml")
    for el in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "form"]):
        el.decompose()

    blocks = []
    current_heading = "Introduction"
    current_paragraphs = []

    for el in soup.find_all(["h1", "h2", "h3", "h4", "p", "ul", "ol", "table"]):
        if el.name.startswith("h"):
            if current_paragraphs:
                combined = " ".join(current_paragraphs)
                if len(combined.split()) >= 20:
                    blocks.append({"heading": current_heading, "content": combined})
            current_heading = el.get_text(strip=True)
            current_paragraphs = []
        else:
            text = el.get_text(strip=True)
            if text and len(text.split()) >= 5:
                current_paragraphs.append(text)

    if current_paragraphs:
        combined = " ".join(current_paragraphs)
        if len(combined.split()) >= 20:
            blocks.append({"heading": current_heading, "content": combined})

    scored = []
    for block in blocks:
        result = score_passage(block["content"], block["heading"])
        if result:
            scored.append(result)

    if scored:
        avg = sum(b["total_score"] for b in scored) / len(scored)
        top5 = sorted(scored, key=lambda x: x["total_score"], reverse=True)[:5]
        bottom5 = sorted(scored, key=lambda x: x["total_score"])[:5]
        optimal = sum(1 for b in scored if 134 <= b["word_count"] <= 167)
    else:
        avg, top5, bottom5, optimal = 0, [], [], 0

    grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for b in scored:
        grade_dist[b["grade"]] += 1

    # --- Page-level structural findings ---
    page_findings = []

    # Data table detection: flag pages with 500+ words but no data tables
    total_word_count = sum(b["word_count"] for b in scored)
    has_tables = bool(soup.find("table"))
    if total_word_count > 500 and not has_tables:
        page_findings.append({
            "id": "citability-no-data-table",
            "severity": "low",
            "title": "No data tables on a content-heavy page",
            "description": (
                f"This page has {total_word_count} words but no <table> elements. "
                "Data tables improve citability by providing structured, extractable facts "
                "that AI models can reference directly."
            ),
        })

    # Heading structure validation: flag when >50% of blocks lack headings
    blocks_without_headings = sum(
        1 for b in blocks if b["heading"] == "Introduction"
    )
    if len(blocks) > 2 and blocks_without_headings / len(blocks) > 0.5:
        page_findings.append({
            "id": "citability-poor-heading-structure",
            "severity": "medium",
            "title": "Over 50% of content blocks lack headings",
            "description": (
                f"{blocks_without_headings} of {len(blocks)} content blocks have no "
                "associated heading. Well-structured headings help AI models identify "
                "and extract specific answer passages."
            ),
        })

    # --- FAQ / featured snippet detection ---
    # Check for Q&A patterns (headings ending with ?)
    qa_headings = [
        b["heading"] for b in blocks
        if b["heading"] and b["heading"].strip().endswith("?")
    ]

    # Check for definition-style headings ("What is...", "What are...")
    definition_headings = [
        b["heading"] for b in blocks
        if b["heading"] and re.search(
            r"^(?:what|who|where|when|why|how)\s+", b["heading"], re.I
        )
    ]

    # Check for how-to/step lists in content
    has_step_content = any(
        re.search(r"(?:step\s+\d|^\d+[\.\)]\s)", b["content"], re.I | re.M)
        for b in blocks
    )

    # Check for direct answer blocks (short, declarative first sentences)
    direct_answers = 0
    for b in blocks:
        first_sent = b["content"].split(".")[0] if b["content"] else ""
        first_words = first_sent.split()
        if (b["heading"] and b["heading"].strip().endswith("?")
                and 5 <= len(first_words) <= 30):
            direct_answers += 1

    faq_signals = len(qa_headings) + len(definition_headings)
    has_faq_content = faq_signals > 0 or has_step_content

    if total_word_count > 300 and not has_faq_content:
        page_findings.append({
            "id": "citability-no-faq-content",
            "severity": "medium",
            "title": "No FAQ or featured-snippet-ready content detected",
            "description": (
                "No question-answer headings, definition patterns (\"What is...\"), "
                "or numbered step lists found. Content structured as Q&A or how-to "
                "steps is significantly more likely to be cited by AI models and "
                "selected for featured snippets."
            ),
        })
    elif has_faq_content and direct_answers == 0 and qa_headings:
        page_findings.append({
            "id": "citability-weak-faq-answers",
            "severity": "low",
            "title": "Question headings found but answers may not be concise enough",
            "description": (
                f"Found {len(qa_headings)} question heading(s) but no concise "
                "direct answer sentences immediately following them. AI models "
                "prefer answers that start with a clear, brief declarative sentence "
                "(5-30 words) before elaborating."
            ),
        })

    if has_faq_content:
        parts = []
        if qa_headings:
            parts.append(f"{len(qa_headings)} Q&A heading(s)")
        if definition_headings:
            parts.append(f"{len(definition_headings)} definition heading(s)")
        if has_step_content:
            parts.append("step-by-step content")
        page_findings.append({
            "id": "citability-faq-found",
            "severity": "pass",
            "title": f"Featured snippet-ready content detected: {', '.join(parts)}",
            "description": (
                "Content includes patterns that AI models and search engines "
                "favor for direct answers and featured snippets."
            ),
        })

    # --- Conversational language detection ---
    all_text = " ".join(b["content"] for b in blocks)
    all_words = all_text.split()
    all_word_count = len(all_words)

    if all_word_count > 100:
        # Second person ("you", "your") signals reader-directed writing
        second_person = len(re.findall(r"\b(?:you|your|you're|you've|you'll)\b", all_text, re.I))
        # First person plural ("we", "our") signals inclusive tone
        first_person = len(re.findall(r"\b(?:we|our|we're|we've|we'll)\b", all_text, re.I))
        # Questions in body text (not headings)
        body_questions = len(re.findall(r"[^.!?\n][^.!?\n]{10,}\?", all_text))
        # Contractions signal natural voice
        contractions = len(re.findall(
            r"\b(?:don't|doesn't|isn't|aren't|wasn't|weren't|can't|won't|wouldn't|shouldn't|couldn't|it's|that's|there's|here's|let's)\b",
            all_text, re.I
        ))
        # Conversational connectors
        connectors = len(re.findall(
            r"\b(?:for example|in other words|think of it as|put simply|basically|essentially|in short|the point is|here's the thing|the bottom line)\b",
            all_text, re.I
        ))

        conversational_signals = second_person + first_person + body_questions + contractions + connectors
        conv_ratio = conversational_signals / all_word_count

        if conv_ratio < 0.005 and all_word_count > 300:
            page_findings.append({
                "id": "citability-low-conversational-tone",
                "severity": "medium",
                "title": "Content lacks conversational language",
                "description": (
                    "The page uses a formal or impersonal tone with very few "
                    "second-person pronouns (you/your), questions, or conversational "
                    "connectors. AI models trained on natural dialogue tend to favor "
                    "and better cite content written in a conversational, reader-directed style."
                ),
            })
        elif conv_ratio >= 0.01:
            page_findings.append({
                "id": "citability-good-conversational-tone",
                "severity": "pass",
                "title": "Good conversational language detected",
                "description": (
                    "Content uses reader-directed language (you/your), questions, "
                    "and natural connectors that AI models find easy to extract and cite."
                ),
            })

    # --- Entity recognition ---
    # Named entities: capitalized multi-word sequences (excluding sentence starts)
    # Look for proper nouns mid-sentence
    entity_pattern = re.findall(
        r"(?<=[a-z]\s)[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*", all_text
    )
    # Defined terms: "X is a/an...", "X refers to..."
    defined_terms = re.findall(
        r"([A-Z][A-Za-z\s]{2,30}?)\s+(?:is\s+(?:a|an|the)\s|refers?\s+to\s|means?\s|can\s+be\s+defined\s+as\s)",
        all_text
    )
    # Technical terms in bold or emphasis (from original HTML)
    raw_soup = BeautifulSoup(resp.text, "lxml")
    bold_terms = [
        el.get_text(strip=True) for el in raw_soup.find_all(["strong", "b", "em"])
        if 1 <= len(el.get_text(strip=True).split()) <= 5
    ]

    unique_entities = set(entity_pattern + defined_terms + bold_terms)
    entity_count = len(unique_entities)

    if all_word_count > 300:
        entity_density = entity_count / (all_word_count / 100)  # per 100 words
        if entity_density < 0.5:
            page_findings.append({
                "id": "citability-low-entity-density",
                "severity": "medium",
                "title": "Low named entity density",
                "description": (
                    f"Found only {entity_count} distinct named entities across "
                    f"{all_word_count} words. Content rich in named entities "
                    "(people, organizations, products, defined terms) is easier for "
                    "AI models to index, disambiguate, and cite accurately."
                ),
            })
        elif entity_density >= 2.0:
            page_findings.append({
                "id": "citability-good-entity-density",
                "severity": "pass",
                "title": f"Strong entity coverage ({entity_count} distinct entities)",
                "description": (
                    "Content is rich in named entities and defined terms, making it "
                    "easy for AI models to identify, index, and cite specific claims."
                ),
            })

    # --- Semantic topic coverage ---
    headings = [b["heading"] for b in blocks if b["heading"] != "Introduction"]
    unique_headings = set(headings)

    if all_word_count > 500:
        # Check heading diversity: how many distinct subtopics
        if len(unique_headings) < 3:
            page_findings.append({
                "id": "citability-low-topic-coverage",
                "severity": "medium",
                "title": f"Narrow topic coverage ({len(unique_headings)} subtopic headings)",
                "description": (
                    f"Only {len(unique_headings)} distinct heading(s) found on a "
                    f"{all_word_count}-word page. Broader topic coverage with more "
                    "subtopic headings (H2/H3) helps AI models match your content "
                    "to a wider range of queries and increases citation surface area."
                ),
            })
        elif len(unique_headings) >= 5:
            page_findings.append({
                "id": "citability-good-topic-coverage",
                "severity": "pass",
                "title": f"Good semantic topic coverage ({len(unique_headings)} subtopics)",
                "description": (
                    "Content covers multiple subtopics with distinct headings, "
                    "increasing the range of AI queries it can answer."
                ),
            })

        # Check for heading word overlap (low diversity = repetitive subtopics)
        if len(unique_headings) >= 3:
            heading_words = [set(h.lower().split()) for h in unique_headings]
            # Find words that appear in >60% of headings
            all_heading_words = {}
            for word_set in heading_words:
                for w in word_set:
                    if len(w) > 3:  # skip short words
                        all_heading_words[w] = all_heading_words.get(w, 0) + 1
            repetitive = [
                w for w, c in all_heading_words.items()
                if c / len(heading_words) > 0.6 and c >= 3
            ]
            if repetitive:
                page_findings.append({
                    "id": "citability-repetitive-headings",
                    "severity": "low",
                    "title": f"Headings repeat the same terms: {', '.join(repetitive[:3])}",
                    "description": (
                        "Multiple headings share the same key terms, which may "
                        "signal narrow topic coverage. Diversifying heading language "
                        "helps AI models match your content to varied query phrasings."
                    ),
                })

    # Add confidence labels
    HYPOTHESIS_IDS = {
        "citability-no-data-table", "citability-no-faq-content",
        "citability-weak-faq-answers", "citability-low-conversational-tone",
        "citability-low-entity-density", "citability-low-topic-coverage",
        "citability-repetitive-headings",
    }
    for f in page_findings:
        if f["id"] in HYPOTHESIS_IDS:
            f["confidence"] = "hypothesis"
        else:
            f["confidence"] = "confirmed"

    return {
        "url": url,
        "blocks_analyzed": len(scored),
        "average_score": round(avg, 1),
        "optimal_length_passages": optimal,
        "grade_distribution": grade_dist,
        "top_5": top5,
        "bottom_5": bottom5,
        "all_blocks": scored,
        "page_findings": page_findings,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 citability.py <url>")
        sys.exit(1)

    print(json.dumps(analyze_page(sys.argv[1]), indent=2, default=str))
