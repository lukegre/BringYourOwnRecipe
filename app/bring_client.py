from typing import Any

from bring_api import Bring


async def get_lists(bring: Bring) -> list[dict[str, Any]]:
    raw = await bring.load_lists()
    return [
        {"uuid": lst["listUuid"], "name": lst["name"]}
        for lst in raw["lists"]
    ]


async def add_ingredients(
    bring: Bring,
    list_uuid: str,
    ingredients: list[dict[str, Any]],
) -> int:
    for item in ingredients:
        await bring.save_item(
            list_uuid,
            item["name"],
            item.get("quantity", ""),
        )
    return len(ingredients)
