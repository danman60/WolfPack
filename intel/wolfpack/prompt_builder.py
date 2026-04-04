"""Configurable prompt builder — loads agent prompt sections from DB with code fallback."""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Section assembly order
SECTION_ORDER = [
    "role",
    "constraints",
    "input_format",
    "reasoning_instructions",
    "output_schema",
    "examples",
]


class PromptBuilder:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self._defaults: Dict[str, Dict[str, str]] = {}  # agent_name -> {section: content}

    def register_defaults(self, agent_name: str, sections: Dict[str, str]):
        """Register hardcoded defaults for an agent (called at init)."""
        self._defaults[agent_name] = sections

    def _load_from_db(self, agent_name: str) -> Dict[str, str]:
        """Load active prompt sections from database."""
        try:
            result = (
                self.supabase.table("wp_prompt_templates")
                .select("section, content")
                .eq("agent_name", agent_name)
                .eq("is_active", True)
                .execute()
            )

            if result.data:
                return {row["section"]: row["content"] for row in result.data}
        except Exception as e:
            logger.warning(f"Failed to load prompts from DB for {agent_name}: {e}")

        return {}

    def build_system_prompt(self, agent_name: str) -> str:
        """Build system prompt from DB sections with fallback to defaults."""
        db_sections = self._load_from_db(agent_name)
        defaults = self._defaults.get(agent_name, {})

        # Merge: DB overrides take precedence
        merged = {**defaults, **db_sections}

        # Assemble in order
        parts = []
        for section in SECTION_ORDER:
            content = merged.get(section)
            if content:
                parts.append(content.strip())

        # Include any extra sections not in SECTION_ORDER
        for section, content in merged.items():
            if section not in SECTION_ORDER and content:
                parts.append(content.strip())

        return "\n\n".join(parts)

    def get_sections(self, agent_name: str) -> Dict[str, str]:
        """Get current effective sections (DB overrides merged with defaults)."""
        db_sections = self._load_from_db(agent_name)
        defaults = self._defaults.get(agent_name, {})
        return {**defaults, **db_sections}

    def estimate_tokens(self, agent_name: str) -> int:
        """Approximate token count for the system prompt."""
        prompt = self.build_system_prompt(agent_name)
        # Rough approximation: ~4 chars per token for English
        return len(prompt) // 4


# Module-level singleton
_prompt_builder: Optional[PromptBuilder] = None


def get_prompt_builder() -> Optional[PromptBuilder]:
    """Get the global PromptBuilder instance (may be None if not initialized)."""
    return _prompt_builder


def init_prompt_builder(supabase_client) -> PromptBuilder:
    """Initialize the global PromptBuilder with a Supabase client."""
    global _prompt_builder
    _prompt_builder = PromptBuilder(supabase_client)
    return _prompt_builder
