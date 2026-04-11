from typing import Any

from bring_api import Bring
from bring_api.types import BringTemplate, Ingredient, TemplateType


async def get_lists(bring: Bring) -> list[dict[str, Any]]:
    raw = await bring.load_lists()
    return [
        {"uuid": lst.listUuid, "name": lst.name}
        for lst in raw.lists
    ]


async def create_recipe(
    bring: Bring,
    recipe_name: str,
    ingredients: list[dict[str, Any]],
) -> str:
    """Create a Bring! recipe and return its UUID."""
    items = [
        Ingredient(
            itemId=item["name"],
            stock=False,
            spec=item.get("quantity") or None,
        )
        for item in ingredients
    ]
    template = BringTemplate(name=recipe_name, items=items)
    result = await bring.create_template(template, TemplateType.RECIPE)
    return result.uuid or ""
