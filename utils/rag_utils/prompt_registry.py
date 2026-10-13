from pathlib import Path
from typing import Any


PROMPT_DIR = Path("docs/prompts")


class PromptRegistry:
    def __init__(self, prompt_dir: Path | None = None):
        self.prompt_dir = prompt_dir or PROMPT_DIR

    def get_prompt(self, name: str) -> dict[str, Any]:
        path = self.prompt_dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt not found: {path}")
        text = path.read_text(encoding="utf-8")

        metadata = {}
        lines = text.splitlines()
        body_lines = []
        for line in lines:
            if line.startswith("VERSION:"):
                metadata["version"] = line.replace("VERSION:", "").strip()
            elif line.startswith("PURPOSE:"):
                metadata["purpose"] = line.replace("PURPOSE:", "").strip()
            else:
                body_lines.append(line)
        return {"metadata": metadata, "template": "\n".join(body_lines).strip()}

    def render(self, name: str, **kwargs: Any) -> str:
        prompt = self.get_prompt(name)
        template = prompt["template"]
        return template.format(**kwargs)


prompt_registry = PromptRegistry()
