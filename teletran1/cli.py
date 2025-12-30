"""CLI interface for Teletran1."""

import json
import sys

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from teletran1 import __version__
from teletran1.analyzer import get_recommendation, prioritize_projects
from teletran1.notion_client import fetch_project_health

app = typer.Typer(
    name="teletran1",
    help="Project oversight system - recommends ONE project to focus on each week",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"Teletran1 v{__version__}")
        raise typer.Exit()


@app.command()
def recommend(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show all projects with priority scores"
    ),
    output_json: bool = typer.Option(
        False, "--json", "-j", help="Output as JSON instead of formatted text"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-d", help="Show project data without making LLM call"
    ),
    version: bool = typer.Option(
        None, "--version", "-V", callback=version_callback, is_eager=True
    ),
) -> None:
    """Get this week's project recommendation.

    Analyzes your Notion projects database and recommends ONE project
    to focus on, taking into account your ENTP personality and
    tendency to struggle with finishing projects.
    """
    try:
        # Fetch project data from Notion
        with console.status("[bold blue]Fetching projects from Notion..."):
            data = fetch_project_health()

        if not data.projects:
            console.print(
                Panel(
                    "[yellow]No projects found in your Notion database.[/yellow]\n\n"
                    "Make sure your database has the required properties:\n"
                    "- Name (title)\n"
                    "- Completion (number, 0-100)\n"
                    "- Priority (select: High, Medium, Low)\n"
                    "- Last Activity (date)\n"
                    "- Client Project (checkbox)\n"
                    "- Deadline (date)\n"
                    "- Next Action (text)",
                    title="No Projects",
                    border_style="yellow",
                )
            )
            raise typer.Exit(1)

        # Verbose mode: show all projects
        if verbose:
            prioritized = prioritize_projects(data)
            table = Table(title="All Projects (by priority)")
            table.add_column("Project", style="cyan")
            table.add_column("Completion", justify="right")
            table.add_column("Priority", justify="center")
            table.add_column("Status", style="dim")

            for project in prioritized:
                status_parts = []
                if project.is_near_completion:
                    status_parts.append("[green]NEAR DONE[/green]")
                if project.is_client_project:
                    status_parts.append("[blue]CLIENT[/blue]")
                if project.is_stale:
                    status_parts.append(f"[red]STALE ({project.days_since_activity}d)[/red]")

                table.add_row(
                    project.name,
                    f"{project.completion_percent}%",
                    project.priority.upper(),
                    " ".join(status_parts) if status_parts else "-",
                )

            console.print(table)
            console.print()

        # Dry run: just show data
        if dry_run:
            console.print(
                Panel(
                    f"Found [bold]{len(data.projects)}[/bold] projects\n"
                    f"Near completion (>75%): [bold]{len(data.near_completion_projects)}[/bold]\n"
                    f"Client + deadline: [bold]{len(data.client_projects_with_deadlines)}[/bold]\n"
                    f"Stale high-priority: [bold]{len(data.stale_high_priority)}[/bold]\n"
                    f"With next actions: [bold]{len(data.projects_with_next_actions)}[/bold]",
                    title="Project Summary (Dry Run)",
                    border_style="blue",
                )
            )
            raise typer.Exit()

        # Get recommendation
        with console.status("[bold blue]Analyzing with Claude..."):
            recommendation = get_recommendation(data)

        # Output
        if output_json:
            console.print_json(recommendation.model_dump_json())
        else:
            output = recommendation.format_output()
            console.print(
                Panel(
                    Markdown(output),
                    title="[bold green]This Week's Focus[/bold green]",
                    border_style="green",
                    padding=(1, 2),
                )
            )

    except Exception as e:
        if "NOTION_API_KEY" in str(e) or "ANTHROPIC_API_KEY" in str(e):
            console.print(
                Panel(
                    "[red]Missing configuration![/red]\n\n"
                    "Make sure you have a .env file with:\n"
                    "- NOTION_API_KEY\n"
                    "- NOTION_DATABASE_ID\n"
                    "- ANTHROPIC_API_KEY\n\n"
                    "See .env.example for details.",
                    title="Configuration Error",
                    border_style="red",
                )
            )
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def test_connection() -> None:
    """Test connections to Notion and Claude APIs."""
    with console.status("[bold blue]Testing Notion connection..."):
        try:
            data = fetch_project_health()
            console.print(f"[green]Notion:[/green] Connected - found {len(data.projects)} projects")
        except Exception as e:
            console.print(f"[red]Notion:[/red] Failed - {e}")

    with console.status("[bold blue]Testing Claude connection..."):
        try:
            from teletran1.llm import get_claude_client
            client = get_claude_client()
            response = client.analyze(
                "You are a test assistant.",
                "Respond with just the word 'OK'."
            )
            if "OK" in response:
                console.print("[green]Claude:[/green] Connected and responding")
            else:
                console.print("[yellow]Claude:[/yellow] Connected but unexpected response")
        except Exception as e:
            console.print(f"[red]Claude:[/red] Failed - {e}")


if __name__ == "__main__":
    app()
