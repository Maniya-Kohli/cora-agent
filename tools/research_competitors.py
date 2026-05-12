#!/usr/bin/env python3
"""
Competitor research tool for Merced.
Reads business_profile.yaml, discovers + researches competitors via web search,
synthesizes findings with Claude, and writes .tmp/competitor_research.json.
"""

import json
import os
import sys
import argparse
from datetime import date
from pathlib import Path

import anthropic
import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

ROOT = Path(__file__).parent.parent
TMP = ROOT / ".tmp"
TMP.mkdir(exist_ok=True)


def serper_search(query: str, num_results: int = 5) -> list[dict]:
    """Run a web search via Serper and return a list of result snippets."""
    if not SERPER_API_KEY:
        raise EnvironmentError("SERPER_API_KEY not set in .env")
    resp = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json={"q": query, "num": num_results},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("organic", [])[:num_results]:
        results.append({
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": item.get("snippet", ""),
        })
    return results


def discover_additional_competitors(company: dict, known_names: list[str]) -> list[dict]:
    """Use web search + Claude to find competitors not already in the known list."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    search_queries = [
        f"{company['name']} competitors alternatives 2025",
        f"AI trading agent intelligence evaluation platform crypto 2025",
        f"on-chain agent performance registry ERC-8004 alternatives",
    ]

    search_results = []
    for q in search_queries:
        try:
            results = serper_search(q, num_results=5)
            search_results.extend(results)
        except Exception as e:
            print(f"[WARN] Search failed for '{q}': {e}", file=sys.stderr)

    if not search_results:
        print("[WARN] No search results for competitor discovery — skipping auto-discovery", file=sys.stderr)
        return []

    context = "\n".join(
        f"- {r['title']}: {r['snippet']} ({r['link']})" for r in search_results
    )
    known_str = ", ".join(known_names)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"""Based on the following web search results about competitors to {company['name']}
({company['tagline']}), identify up to 4 additional competitors NOT already in this known list: {known_str}.

For each new competitor, return a JSON array with objects containing:
- name (string)
- url (string)
- category (string: one of data_and_execution, ai_agent_platform, backtesting_quant, agent_reputation, other)
- notes (string: one sentence on why they compete with {company['name']})

Return ONLY valid JSON array. If no new competitors found, return [].

Search results:
{context}"""
        }],
    )

    try:
        text = message.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        print(f"[WARN] Could not parse competitor discovery response: {e}", file=sys.stderr)
        return []


def research_single_competitor(competitor: dict, our_company: dict) -> dict:
    """Research a single competitor using web search + Claude synthesis."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    name = competitor["name"]
    url = competitor.get("url", "")

    print(f"  Researching {name}...")

    search_queries = [
        f"{name} {url} product features pricing 2025",
        f"{name} funding news recent developments 2025",
        f"{name} vs {our_company['name']} comparison",
    ]

    search_results = []
    for q in search_queries:
        try:
            results = serper_search(q, num_results=4)
            search_results.extend(results)
        except Exception as e:
            print(f"[WARN] Search failed for '{q}': {e}", file=sys.stderr)

    context = "\n".join(
        f"- {r['title']}: {r['snippet']} ({r['link']})" for r in search_results
    ) if search_results else "No search results available."

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=f"""You are a competitive intelligence analyst researching competitors to {our_company['name']}.
{our_company['name']} is: {our_company['description'][:300]}
Target market: {our_company['target_market'][:200]}""",
        messages=[{
            "role": "user",
            "content": f"""Research {name} ({url}) as a competitor to {our_company['name']}.

Using the search results below, synthesize a competitive profile. Return a JSON object with these exact keys:
- overview (string): 2-3 sentences on what they do, their positioning, and target market
- products_services (array of strings): their main offerings
- pricing (string): pricing model/tiers if known, or "Not publicly available"
- target_market (string): who they sell to
- strengths (array of strings): 2-4 competitive strengths vs {our_company['name']}
- weaknesses (array of strings): 2-4 competitive weaknesses vs {our_company['name']}
- recent_news (array of strings): notable recent developments, funding, product launches (up to 3)
- threat_level (string): one of "High", "Medium", "Low" — how directly they threaten {our_company['name']}
- threat_rationale (string): one sentence explaining the threat level

Return ONLY valid JSON.

Search results:
{context}"""
        }],
    )

    try:
        text = message.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        profile = json.loads(text)
    except Exception as e:
        print(f"[WARN] Could not parse profile for {name}: {e}", file=sys.stderr)
        profile = {
            "overview": f"Research parsing failed for {name}.",
            "products_services": [],
            "pricing": "Unknown",
            "target_market": "Unknown",
            "strengths": [],
            "weaknesses": [],
            "recent_news": [],
            "threat_level": "Unknown",
            "threat_rationale": "Research incomplete.",
        }

    return {
        "name": name,
        "url": url,
        "category": competitor.get("category", "other"),
        "known_notes": competitor.get("notes", ""),
        **profile,
    }


def generate_strategic_gaps(our_company: dict, competitor_profiles: list[dict]) -> list[dict]:
    """Use Claude to synthesize strategic gaps and recommendations from all competitor data."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    profiles_summary = json.dumps([{
        "name": c["name"],
        "overview": c.get("overview", ""),
        "strengths": c.get("strengths", []),
        "threat_level": c.get("threat_level", "Unknown"),
    } for c in competitor_profiles], indent=2)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=f"""You are a strategic advisor for {our_company['name']}.
Company: {our_company['description'][:400]}
Target market: {our_company['target_market'][:200]}""",
        messages=[{
            "role": "user",
            "content": f"""Based on this competitive landscape, identify the top 5 strategic gaps and opportunities for {our_company['name']}.

Competitor profiles:
{profiles_summary}

Return a JSON array of 5 objects, each with:
- title (string): short name for the gap/opportunity
- description (string): 2-3 sentences explaining the gap
- competitors_winning_here (array of strings): which competitors are currently winning in this area
- recommended_action (string): specific action {our_company['name']} could take
- impact (string): one of "High", "Medium", "Low"
- timeframe (string): one of "Immediate (0-3 months)", "Short-term (3-6 months)", "Medium-term (6-12 months)"

Return ONLY valid JSON array."""
        }],
    )

    try:
        text = message.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        print(f"[WARN] Could not parse strategic gaps: {e}", file=sys.stderr)
        return []


def generate_executive_summary(our_company: dict, competitor_profiles: list[dict], gaps: list[dict]) -> str:
    """Generate a concise executive summary of the competitive landscape."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    high_threats = [c["name"] for c in competitor_profiles if c.get("threat_level") == "High"]
    top_gaps = [g["title"] for g in gaps[:3] if g.get("impact") == "High"]

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"""Write a 4-5 bullet executive summary of the competitive landscape for {our_company['name']}.

Key facts:
- Analyzed {len(competitor_profiles)} competitors
- High-threat competitors: {', '.join(high_threats) if high_threats else 'None identified'}
- Top strategic opportunities: {', '.join(top_gaps) if top_gaps else 'See full report'}
- Company position: {our_company['tagline']}

Return plain text bullet points starting with •. No headers, no JSON."""
        }],
    )

    return message.content[0].text.strip()


def main():
    parser = argparse.ArgumentParser(description="Research Merced competitors")
    parser.add_argument(
        "--profile",
        default=str(ROOT / "business_profile.yaml"),
        help="Path to business_profile.yaml",
    )
    parser.add_argument(
        "--output",
        default=str(TMP / "competitor_research.json"),
        help="Output JSON path",
    )
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)
    if not SERPER_API_KEY:
        print("ERROR: SERPER_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    with open(args.profile) as f:
        profile = yaml.safe_load(f)

    company = profile["company"]
    known_competitors = profile.get("known_competitors", [])
    known_names = [c["name"] for c in known_competitors]

    print(f"Loaded profile for {company['name']}")
    print(f"Known competitors: {', '.join(known_names)}")

    print("\nDiscovering additional competitors...")
    new_competitors = discover_additional_competitors(company, known_names)
    if new_competitors:
        print(f"  Found {len(new_competitors)} new competitors: {', '.join(c['name'] for c in new_competitors)}")
    else:
        print("  No new competitors discovered beyond known list")

    all_competitors = known_competitors + new_competitors

    print(f"\nResearching {len(all_competitors)} competitors...")
    competitor_profiles = []
    for comp in all_competitors:
        try:
            profile_data = research_single_competitor(comp, company)
            competitor_profiles.append(profile_data)
        except Exception as e:
            print(f"[WARN] Failed to research {comp['name']}: {e}", file=sys.stderr)

    print("\nGenerating strategic gap analysis...")
    gaps = generate_strategic_gaps(company, competitor_profiles)

    print("Generating executive summary...")
    exec_summary = generate_executive_summary(company, competitor_profiles, gaps)

    output = {
        "generated_date": date.today().isoformat(),
        "company": company,
        "executive_summary": exec_summary,
        "competitor_profiles": competitor_profiles,
        "strategic_gaps": gaps,
        "metadata": {
            "total_competitors_analyzed": len(competitor_profiles),
            "known_competitors_count": len(known_competitors),
            "discovered_competitors_count": len(new_competitors),
        },
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nDone. Research saved to: {args.output}")
    print(f"  Competitors analyzed: {len(competitor_profiles)}")
    print(f"  Strategic gaps identified: {len(gaps)}")


if __name__ == "__main__":
    main()
