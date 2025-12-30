"""Core analysis logic for Teletran1 project recommendations."""

import json

from teletran1.llm import get_claude_client
from teletran1.models import Project, ProjectHealthData, Recommendation

# System prompt defining Teletran1's persona and behavior
SYSTEM_PROMPT = """You are Teletran-1, a project oversight system for Matthew Snow, an AI Engineer and consultant.

## Your Role
Analyze project health data and recommend ONE project for focus this week.

## Matthew's Working Style
- ENTP personality: loves starting new things, struggles finishing
- Thrives on novelty and challenge
- 75-80% completion is danger zone for abandonment
- Daily walks for brainstorming; remote work preferred
- Runs consulting company (Me, Myself Plus AI LLC)

## Prioritization Rules (in order)
1. Projects >75% complete - FINISH THESE FIRST (frame as "shipping challenge")
2. Client projects with deadlines - revenue depends on delivery
3. High-priority projects going stale (>7 days inactive)
4. Projects with clear next actions defined

## Reframing Strategy
Don't say "grind through remaining 15%"
Say "Ship [PROJECT] this week - it's a new challenge: the challenge of finishing"

## Output Format
You MUST respond with ONLY a JSON object in this exact format (no markdown, no explanation):
{
    "project": "[name]",
    "completion": [X],
    "why_this_week": "[1-2 sentences, emphasize what finishing unlocks]",
    "first_action": "[specific, concrete next step]",
    "what_shipping_enables": "[motivation - what becomes possible after]"
}"""


def build_project_summary(data: ProjectHealthData) -> str:
    """Build a summary of project health data for Claude."""
    if not data.projects:
        return "No projects found in the database."

    lines = ["# Current Project Health Data\n"]

    for project in data.projects:
        status_flags = []
        if project.is_near_completion:
            status_flags.append("NEAR COMPLETION")
        if project.is_client_project:
            status_flags.append("CLIENT")
        if project.has_deadline:
            deadline_str = project.deadline.strftime("%Y-%m-%d") if project.deadline else "TBD"
            status_flags.append(f"DEADLINE: {deadline_str}")
        if project.is_stale:
            status_flags.append(f"STALE ({project.days_since_activity}d)")

        flags_str = f" [{', '.join(status_flags)}]" if status_flags else ""

        lines.append(f"## {project.name}{flags_str}")
        lines.append(f"- Completion: {project.completion_percent}%")
        lines.append(f"- Priority: {project.priority}")

        if project.last_activity:
            lines.append(f"- Last Activity: {project.last_activity.strftime('%Y-%m-%d')}")
        else:
            lines.append("- Last Activity: Unknown")

        if project.next_action:
            lines.append(f"- Next Action: {project.next_action}")

        if project.notes:
            lines.append(f"- Notes: {project.notes}")

        lines.append("")  # Empty line between projects

    return "\n".join(lines)


def prioritize_projects(data: ProjectHealthData) -> list[Project]:
    """Apply prioritization rules and return sorted projects.

    Priority order:
    1. Projects >75% complete
    2. Client projects with deadlines
    3. High-priority stale projects (>7 days inactive)
    4. Projects with next actions defined
    """
    scored_projects: list[tuple[int, Project]] = []

    for project in data.projects:
        score = 0

        # Rule 1: Near completion (highest priority)
        if project.is_near_completion:
            score += 1000

        # Rule 2: Client projects with deadlines
        if project.is_client_project and project.has_deadline:
            score += 500

        # Rule 3: High-priority stale projects
        if project.priority == "high" and project.is_stale:
            score += 250

        # Rule 4: Has next action defined
        if project.next_action:
            score += 100

        # Bonus: Higher completion = higher priority
        score += project.completion_percent

        # Bonus: Higher priority level
        priority_bonus = {"high": 50, "medium": 25, "low": 0}
        score += priority_bonus.get(project.priority, 0)

        scored_projects.append((score, project))

    # Sort by score descending
    scored_projects.sort(key=lambda x: x[0], reverse=True)

    return [p for _, p in scored_projects]


def analyze_projects(data: ProjectHealthData) -> Recommendation:
    """Analyze project health data and generate a recommendation.

    Args:
        data: Project health data from Notion

    Returns:
        Weekly project recommendation
    """
    if not data.projects:
        return Recommendation(
            project="No Projects",
            completion=0,
            why_this_week="You have no projects in your Notion database.",
            first_action="Add some projects to your Notion database!",
            what_shipping_enables="Having projects to work on.",
        )

    # Build the analysis prompt
    project_summary = build_project_summary(data)
    user_prompt = f"""Based on the following project health data, recommend ONE project for me to focus on this week.

{project_summary}

Remember: I'm an ENTP who loves starting new things but struggles to finish. Frame finishing as the exciting challenge, not as a grind. Focus on what shipping unlocks, not just checking boxes.

Respond with ONLY a JSON object - no markdown formatting, no code blocks, just raw JSON."""

    # Get Claude's analysis
    client = get_claude_client()
    response = client.analyze(SYSTEM_PROMPT, user_prompt)

    # Parse the response
    try:
        # Strip any potential markdown formatting
        clean_response = response.strip()
        if clean_response.startswith("```"):
            # Remove markdown code blocks if present
            lines = clean_response.split("\n")
            clean_response = "\n".join(
                line for line in lines if not line.startswith("```")
            )

        recommendation_data = json.loads(clean_response)
        return Recommendation(**recommendation_data)
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback: use rule-based prioritization
        prioritized = prioritize_projects(data)
        top_project = prioritized[0]

        return Recommendation(
            project=top_project.name,
            completion=top_project.completion_percent,
            why_this_week=f"This is your top priority based on completion ({top_project.completion_percent}%) and status.",
            first_action=top_project.next_action or "Define the next concrete action for this project.",
            what_shipping_enables="Moving forward on your highest-impact work.",
        )


def get_recommendation(data: ProjectHealthData | None = None) -> Recommendation:
    """Get a weekly project recommendation.

    Args:
        data: Optional pre-fetched project data. If None, fetches from Notion.

    Returns:
        Weekly project recommendation
    """
    if data is None:
        from teletran1.notion_client import fetch_project_health
        data = fetch_project_health()

    return analyze_projects(data)
