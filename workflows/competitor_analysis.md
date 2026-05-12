# Workflow: Competitor Analysis Report

## Objective
Research Merced's competitive landscape, generate a structured analysis, and produce a branded PDF report delivered to Google Drive.

## Trigger
Run on-demand. The user will say something like: "Run the competitor analysis" or "Generate the competitor report."

## Required Inputs
- `business_profile.yaml` — must exist in the project root (contains company info, known competitors, brand settings)
- Active internet connection (web search for competitor research)
- Google Drive credentials (`credentials.json` + `token.json` in project root, or valid OAuth flow)

## Steps

### Step 1: Load Business Profile
Read `business_profile.yaml`. Extract:
- Company description and target market
- Known competitors list
- Brand settings (colors, fonts, logo path)
- Google Drive folder name

### Step 2: Research Competitors
Run `tools/research_competitors.py`.

**Inputs (pass as CLI args or via the script's config):**
- Path to `business_profile.yaml`

**What it does:**
1. Takes the known competitors from the profile as the seed list
2. Uses web search to discover 2–4 additional competitors not already in the list
3. For each competitor (known + discovered), researches:
   - Company overview: what they do, founding, size, positioning, target market
   - Product/service offerings vs. Merced's
   - Pricing model (if publicly available)
   - Recent news, funding, or strategic moves
4. Identifies strategic gaps: areas where competitors are winning that Merced could address
5. Writes output to `.tmp/competitor_research.json`

**On failure:**
- If web search rate-limits or fails on a specific competitor, log it and continue — partial results are acceptable
- If the script errors entirely, check API key in `.env` (requires `ANTHROPIC_API_KEY` and `SERPER_API_KEY`)

### Step 3: Generate Branded PDF
Run `tools/generate_report_pdf.py`.

**Inputs:**
- `.tmp/competitor_research.json` (from Step 2)
- `business_profile.yaml` (for brand settings and logo)

**What it produces:**
A branded PDF at `.tmp/merced_competitor_analysis_YYYY-MM-DD.pdf` with these sections:
1. **Cover page** — Merced logo, report title, date, tagline
2. **Executive Summary** — 3–5 bullet points: top findings, key threats, top opportunities
3. **Competitive Landscape Overview** — table of all competitors with category, positioning, target market
4. **Competitor Deep Dives** — one section per competitor with overview, products, pricing, recent moves
5. **Product/Service Comparison** — side-by-side table: Merced vs. top competitors across key dimensions
6. **Pricing Intelligence** — what competitors charge and how they package it
7. **Strategic Gaps & Recommendations** — areas where competitors are winning that Merced should address, ranked by impact

**Branding rules enforced by the script:**
- Background: `#0a0a0a`, surface cards: `#0d0d0d`
- Primary text: `#ffffff`, muted text: `#9ca3af`
- Accent / highlight: `#ff4d4d` (section headers, key callouts)
- Positive indicators: `#00d294`, warnings: `#f99c00`
- Font: PP Neue Montreal (Bold for headings, Medium for subheadings, Book for body) — falls back to Helvetica if not installed
- Logo rendered on cover page and in header of each subsequent page

**On failure:**
- If font file is missing, script falls back to Helvetica — do not block on this
- If logo SVG fails to render, skip it and note in output — do not block report generation

### Step 4: Upload to Google Drive
Run `tools/upload_to_drive.py`.

**Inputs:**
- Path to the generated PDF (`.tmp/merced_competitor_analysis_YYYY-MM-DD.pdf`)
- Folder name from `business_profile.yaml` (`google_drive.reports_folder_name`)

**What it does:**
1. Authenticates with Google Drive (OAuth2 — will prompt browser auth on first run)
2. Finds or creates the folder named in the config
3. Uploads the PDF
4. Returns the shareable link

**On failure:**
- If auth fails, prompt the user to re-run the OAuth flow: `python tools/upload_to_drive.py --reauth`
- If folder creation fails, fall back to Drive root and note the path

### Step 5: Report to User
Tell the user:
- The Google Drive link to the uploaded PDF
- How many competitors were analyzed
- The top 3 strategic recommendations surfaced in the report
- Any warnings or partial failures encountered during research

## Expected Output
- `.tmp/competitor_research.json` — structured research data (intermediate, disposable)
- `.tmp/merced_competitor_analysis_YYYY-MM-DD.pdf` — local branded PDF (intermediate)
- Google Drive: PDF uploaded to "Merced Competitor Analysis Reports" folder

## Environment Variables Required (in `.env`)
```
ANTHROPIC_API_KEY=        # For LLM-powered research synthesis in research_competitors.py
SERPER_API_KEY=           # For web search (serper.dev) — get a free key at serper.dev
```

## Dependencies
Install with: `pip install -r requirements.txt`
- `anthropic` — Claude API for research synthesis
- `reportlab` — PDF generation
- `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib` — Drive upload
- `requests` — HTTP calls for web search
- `pyyaml` — reading business_profile.yaml
- `svglib`, `reportlab` — rendering SVG logo in PDF

## Error Recovery
| Error | Action |
|-------|--------|
| Missing `SERPER_API_KEY` | Ask user to add it to `.env`, then re-run |
| Missing `ANTHROPIC_API_KEY` | Ask user to add it to `.env`, then re-run |
| Google Drive auth expired | Run `python tools/upload_to_drive.py --reauth` |
| PDF font not found | Script auto-falls back to Helvetica — continue |
| Competitor research partial (some failed) | Generate report with available data, note gaps |
