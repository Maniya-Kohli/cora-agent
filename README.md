# Competitor Analysis Workflow

An AI-powered workflow that researches your competitive landscape and generates a branded PDF report — automatically. Works for any company.

Built on the **WAT framework**: Workflows define the SOP, Claude orchestrates decisions, Python tools execute deterministically.

---

## What it does

1. **Discovers competitors** — seeds from your known list, then uses web search to find more
2. **Researches each one** — overview, products, pricing, strengths, weaknesses, recent news, threat level
3. **Generates a branded PDF** — styled with your colors and logo, sections include:
   - Executive Summary
   - Competitive Landscape Overview (table)
   - Competitor Deep Dives (one section per competitor)
   - Product / Service Comparison
   - Pricing Intelligence
   - Strategic Gaps & Recommendations
4. **Uploads to Google Drive** — returns a shareable link

---

## Quickstart

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up API keys

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```
ANTHROPIC_API_KEY=   # Get from console.anthropic.com
SERPER_API_KEY=      # Get from serper.dev (free tier available)
```

### 3. Create your business profile

Copy the template and fill in your company details:

```bash
cp business_profile_template.yaml business_profile.yaml
```

Edit `business_profile.yaml` with:
- Your company name, tagline, description, and target market
- Your products/services
- Competitors you already know about
- Your brand colors (hex codes)
- Path to your logo PNG (optional — falls back to text if not provided)

### 4. (Optional) Add your logo

Save your logo as a PNG to the path specified in `business_profile.yaml` (default: `.tmp/logo.png`).

If no logo is provided, the report renders your company name in your accent color instead.

### 5. Set up Google Drive (for upload)

Download OAuth credentials from [Google Cloud Console](https://console.cloud.google.com/):
- Create a project → Enable the **Google Drive API**
- Go to **APIs & Services → Credentials → Create OAuth 2.0 Client ID** (Desktop app)
- Download the JSON file and save it as `credentials.json` in the project root

On first upload, a browser window will open for you to authorize access. The token is saved to `token.json` for future runs.

### 6. Run it

Just tell Claude: **"Run the competitor analysis"** and it will execute the full workflow.

Or run each step manually:

```bash
# Step 1: Research competitors
python tools/research_competitors.py

# Step 2: Generate PDF
python tools/generate_report_pdf.py

# Step 3: Upload to Google Drive
python tools/upload_to_drive.py
```

---

## Configuration reference (`business_profile.yaml`)

| Field | Required | Description |
|-------|----------|-------------|
| `company.name` | Yes | Your company name — appears throughout the report |
| `company.tagline` | Yes | One-liner shown on cover page |
| `company.industry` | Yes | Guides the competitor discovery searches |
| `company.description` | Yes | 2-4 sentences — used to frame all AI research |
| `company.target_market` | Yes | Who you sell to — used to assess threat levels |
| `company.products` | Yes | List of your products/services — drives comparison table |
| `known_competitors` | Recommended | Seed list; agent auto-discovers more |
| `brand.colors` | Yes | All hex colors for the PDF (see template for full list) |
| `brand.logo.png_path` | Optional | Path to logo PNG; text fallback if missing |
| `google_drive.reports_folder_name` | Optional | Drive folder name (defaults to `"<Company> Competitor Analysis Reports"`) |

---

## Project structure

```
business_profile.yaml          # Your company config (gitignored if contains secrets)
business_profile_template.yaml # Blank template to copy from
.env                           # API keys — never commit this
.env.example                   # Template for .env
credentials.json               # Google OAuth app credentials (gitignored)
token.json                     # Google OAuth user token (gitignored)

tools/
  research_competitors.py      # Web search + Claude → competitor_research.json
  generate_report_pdf.py       # competitor_research.json + profile → branded PDF
  upload_to_drive.py           # PDF → Google Drive, returns share link

workflows/
  competitor_analysis.md       # Full SOP for the agent to follow

.tmp/                          # Intermediate files (auto-generated, gitignored)
  competitor_research.json
  <company>_competitor_analysis_YYYY-MM-DD.pdf
  logo.png                     # Place your logo here
```

---

## Customizing for your brand

All brand settings live in `business_profile.yaml`. No code changes needed.

**Dark theme example:**
```yaml
brand:
  colors:
    primary_accent: "#ff4d4d"
    background:     "#0a0a0a"
    surface:        "#0d0d0d"
    border:         "#2a2a2a"
    foreground:     "#ffffff"
    muted:          "#9ca3af"
    emerald:        "#00d294"
    amber:          "#f99c00"
    blue:           "#54a2ff"
```

**Light theme example:**
```yaml
brand:
  colors:
    primary_accent: "#4a6cf7"
    background:     "#ffffff"
    surface:        "#f8f9fa"
    border:         "#e5e7eb"
    foreground:     "#111827"
    muted:          "#6b7280"
    emerald:        "#10b981"
    amber:          "#f59e0b"
    blue:           "#3b82f6"
```

---

## Environment variables

| Variable | Required | Where to get it |
|----------|----------|-----------------|
| `ANTHROPIC_API_KEY` | Yes | [console.anthropic.com](https://console.anthropic.com) |
| `SERPER_API_KEY` | Yes | [serper.dev](https://serper.dev) — free tier available |

Google OAuth credentials go in `credentials.json` (not in `.env`).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ANTHROPIC_API_KEY not set` | Add key to `.env` |
| `SERPER_API_KEY not set` | Add key to `.env` |
| `credentials.json not found` | Download from Google Cloud Console (see Step 5 above) |
| Google Drive API 403 error | Enable the Drive API in your Google Cloud project |
| Auth token expired | Run `python tools/upload_to_drive.py --reauth` |
| PDF has no logo | Save your logo PNG to the path in `brand.logo.png_path` |
