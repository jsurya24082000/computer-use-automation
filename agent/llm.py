import json
import os
from typing import Any, Dict

from openai import OpenAI


class LLMClient:
    def __init__(self, model: str = "gpt-4o"):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def decide_action(self, prompt: str, temperature: float = 0.2) -> Dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a UI automation planner for a legacy bank back-office system. "
                        "You choose actions from a fixed set. Always respond with a single JSON object and no other text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
