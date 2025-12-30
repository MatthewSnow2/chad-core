# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Teletran1 is a lightweight CLI tool that helps ENTPs (and anyone who struggles with finishing projects) focus on shipping. It pulls project data from Notion, applies prioritization rules, and uses Claude to generate motivational recommendations.

## Build & Run Commands

```bash
# Install
pip install -e .

# Run
teletran1                    # Get weekly recommendation
teletran1 --verbose          # Show all projects
teletran1 --dry-run          # Preview without LLM call
teletran1 test-connection    # Test API connections

# Development
pip install -e ".[dev]"      # Install dev dependencies
pytest                       # Run tests
ruff check .                 # Lint
```

## Architecture

```
teletran1/
├── __init__.py         # Version
├── config.py           # Pydantic settings (env vars)
├── models.py           # Project, Recommendation, ProjectHealthData
├── notion_client.py    # Notion API - fetches project database
├── llm.py              # Claude client - simple analyze() method
├── analyzer.py         # Core logic - prioritization + LLM call
└── cli.py              # Typer CLI - recommend, test-connection
```

## Key Patterns

**Data Flow**: Notion DB → notion_client.py → analyzer.py → llm.py → CLI output

**Prioritization Rules** (in `analyzer.py`):
1. Projects >75% complete (score +1000)
2. Client projects with deadlines (score +500)
3. High-priority stale projects (score +250)
4. Projects with next actions (score +100)

**ENTP Reframing**: The system prompt tells Claude to reframe "grind through remaining 15%" as "Ship X this week - it's a new challenge: the challenge of finishing"

## Configuration

All settings via environment variables (`.env` file):
- `NOTION_API_KEY`: Notion integration token
- `NOTION_DATABASE_ID`: ID of projects database
- `ANTHROPIC_API_KEY`: Claude API key
- `MODEL_NAME`: Optional, defaults to claude-sonnet-4-5-20250929

## Testing

Tests are in `tests/` directory. Use mocks for Notion and Claude APIs.

```bash
pytest tests/test_analyzer.py -v
```

## Notion Database Schema

Expected properties in the Notion database:
- Name (title)
- Completion (number 0-100)
- Priority (select: High, Medium, Low)
- Last Activity (date)
- Client Project (checkbox)
- Deadline (date)
- Next Action (rich text)
- Notes (rich text)
