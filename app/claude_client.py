import base64
import json
import os
import re
from typing import Any

import anthropic

_client: anthropic.AsyncAnthropic | None = None

_PROMPT = (
    "This image contains a recipe. "
    "Return ONLY a JSON object — no prose, no markdown fences — with exactly two keys: "
    '"recipe_name" (the name of the recipe as a string, or an empty string if not visible) and '
    '"ingredients" (a JSON array of objects, each with exactly two string keys: '
    '"name" (the ingredient name, e.g. "plain flour") and '
    '"quantity" (the amount and unit, e.g. "200g" or "2 tbsp"; use an empty string if not stated)). '
    'Example output: {"recipe_name": "Banana Bread", "ingredients": ['
    '{"name": "plain flour", "quantity": "200g"}, {"name": "baking powder", "quantity": "1 tsp"}]}'
)


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


async def extract_ingredients(
    image_bytes: bytes, media_type: str
) -> dict[str, Any]:
    """Return {"recipe_name": str, "ingredients": [{"name": str, "quantity": str}]}."""
    client = _get_client()
    image_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": _PROMPT},
                ],
            }
        ],
    )

    raw_text = message.content[0].text.strip()
    # Strip accidental markdown fences
    raw_text = re.sub(r"^```[a-z]*\n?", "", raw_text)
    raw_text = re.sub(r"\n?```$", "", raw_text)

    result: dict[str, Any] = json.loads(raw_text)
    return result
