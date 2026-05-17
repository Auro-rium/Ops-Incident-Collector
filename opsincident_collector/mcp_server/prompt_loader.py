from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


@dataclass(frozen=True)
class PromptAsset:
    name: str
    version: str
    description: str | None
    raw_xml: str
    path: Path


def load_prompt(name: str, prompt_dir: Path = PROMPT_DIR) -> PromptAsset:
    path = prompt_dir / f"{name}.xml"
    if not path.exists():
        raise FileNotFoundError(f"MCP prompt XML not found: {name}")
    raw_xml = path.read_text(encoding="utf-8")
    root = ElementTree.fromstring(raw_xml)
    if root.tag != "prompt":
        raise ValueError(f"MCP prompt XML must have <prompt> root: {path}")
    prompt_name = root.attrib.get("name") or name
    version = root.attrib.get("version") or "1.0"
    description_node = root.find("description")
    description = (
        "".join(description_node.itertext()).strip()
        if description_node is not None
        else None
    )
    return PromptAsset(
        name=prompt_name,
        version=version,
        description=description,
        raw_xml=raw_xml,
        path=path,
    )


def load_all_prompts(prompt_dir: Path = PROMPT_DIR) -> dict[str, PromptAsset]:
    if not prompt_dir.exists():
        return {}
    prompts = {}
    for path in sorted(prompt_dir.glob("*.xml")):
        asset = load_prompt(path.stem, prompt_dir=prompt_dir)
        prompts[asset.name] = asset
    return prompts
