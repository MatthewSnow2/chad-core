"""Simplified Claude client for project analysis."""

import anthropic

from teletran1.config import get_settings


class ClaudeClient:
    """Simplified Claude API client for Teletran1 analysis."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.model_name

    def analyze(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt to Claude and get the response.

        Args:
            system_prompt: The system context (Teletran1 persona)
            user_prompt: The user message with project data

        Returns:
            Claude's response text
        """
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract text from response
        if message.content and len(message.content) > 0:
            return message.content[0].text
        return ""


def get_claude_client() -> ClaudeClient:
    """Get a Claude client instance."""
    return ClaudeClient()
