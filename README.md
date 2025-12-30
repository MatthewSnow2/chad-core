# Teletran1

**Project oversight system for ENTPs who love starting but struggle finishing.**

Teletran1 analyzes your project health data from Notion and recommends **ONE project** to focus on each week. It understands the ENTP personality - reframing "grinding through the last 15%" as "the exciting challenge of shipping."

## Quick Start

```bash
# 1. Install
pip install -e .

# 2. Configure
cp .env.example .env
# Edit .env with your Notion and Anthropic API keys

# 3. Run
teletran1
```

## Features

- **Notion Integration**: Pulls project data from your Notion database
- **Smart Prioritization**: Applies rules that work for ENTPs:
  1. Projects >75% complete - FINISH THESE FIRST
  2. Client projects with deadlines
  3. High-priority projects going stale (>7 days)
  4. Projects with clear next actions
- **ENTP Reframing**: Uses Claude to reframe "finish this" as an exciting challenge
- **Clean CLI**: Rich terminal output with `--verbose`, `--json`, and `--dry-run` options

## Usage

```bash
# Get this week's recommendation
teletran1

# Show all projects with priority scores
teletran1 --verbose

# Output as JSON
teletran1 --json

# Preview without calling Claude
teletran1 --dry-run

# Test API connections
teletran1 test-connection
```

## Example Output

```
╭─────────────── This Week's Focus ───────────────╮
│                                                 │
│ **Project**: GRIMLOCK                           │
│ **Completion**: 85%                             │
│ **Why This Week**: You're 85% done - this is    │
│ the shipping challenge! Cross the finish line   │
│ and unlock the ability to demo this at the      │
│ next hackathon.                                 │
│ **First Action**: Complete the API validation   │
│ tests for the webhook endpoint                  │
│ **What Shipping Enables**: A portfolio piece    │
│ that demonstrates your n8n + Claude expertise   │
│                                                 │
╰─────────────────────────────────────────────────╯
```

## Notion Database Setup

Create a Notion database with these properties:

| Property | Type | Description |
|----------|------|-------------|
| Name | Title | Project name |
| Completion | Number (0-100) | Percentage complete |
| Priority | Select (High/Medium/Low) | Priority level |
| Last Activity | Date | When last worked on |
| Client Project | Checkbox | Is this for a client? |
| Deadline | Date | Optional deadline |
| Next Action | Text | Concrete next step |
| Notes | Text | Additional context |

Then:
1. Create a Notion integration at https://www.notion.so/my-integrations
2. Share your database with the integration
3. Copy the database ID from the URL

## Configuration

Create a `.env` file:

```bash
NOTION_API_KEY=secret_xxx
NOTION_DATABASE_ID=xxx
ANTHROPIC_API_KEY=sk-ant-xxx
```

## Architecture

```
teletran1/
├── __init__.py         # Version info
├── config.py           # Pydantic settings
├── models.py           # Project & Recommendation schemas
├── notion_client.py    # Notion API integration
├── llm.py              # Claude client
├── analyzer.py         # Core prioritization logic
└── cli.py              # Typer CLI
```

## How It Works

1. **Fetch**: Pulls all projects from your Notion database
2. **Score**: Applies prioritization rules (near-completion, deadlines, staleness)
3. **Analyze**: Sends project data to Claude with ENTP-aware system prompt
4. **Recommend**: Returns ONE project with reframed motivation

## Why "Teletran1"?

Named after the Autobot computer from Transformers - an AI system that analyzes situations and provides strategic recommendations. Just like Teletran-1 helped Optimus Prime focus on what matters, this tool helps you focus on shipping.

## License

MIT
