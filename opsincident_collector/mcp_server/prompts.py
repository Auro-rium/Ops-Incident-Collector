from __future__ import annotations

from opsincident_collector.mcp_server.prompt_loader import load_all_prompts


def get_prompt_map() -> dict[str, str]:
    return {name: asset.raw_xml for name, asset in load_all_prompts().items()}


PROMPTS = get_prompt_map()
