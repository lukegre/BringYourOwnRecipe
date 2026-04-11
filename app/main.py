from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

import os
import aiohttp
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from bring_api import Bring

from app.claude_client import extract_ingredients
from app.bring_client import create_recipe

SUPPORTED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    timeout = aiohttp.ClientTimeout(total=30)
    session = aiohttp.ClientSession(timeout=timeout)
    bring = Bring(session, os.environ["BRING_EMAIL"], os.environ["BRING_PASSWORD"])
    await bring.login()
    app.state.bring = bring
    yield
    await session.close()


app = FastAPI(title="BringYourOwnRecipe", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/", response_class=FileResponse)
async def index():
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


@app.post("/api/extract")
async def api_extract(image: UploadFile = File(...)):
    media_type = image.content_type or "image/jpeg"
    # Normalise non-standard MIME types from some mobile browsers
    if media_type == "image/jpg":
        media_type = "image/jpeg"
    if media_type not in SUPPORTED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported image type: {media_type}")
    contents = await image.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image too large. Maximum size is 10 MB.")
    try:
        result = await extract_ingredients(contents, media_type)
    except Exception:
        raise HTTPException(status_code=502, detail="Ingredient extraction failed.")
    return {
        "recipe_name": result.get("recipe_name", ""),
        "ingredients": result.get("ingredients", []),
    }


class IngredientItem(BaseModel):
    name: str = Field(..., max_length=200)
    quantity: str = Field("", max_length=100)


class SaveRecipeRequest(BaseModel):
    recipe_name: str = Field(..., max_length=200)
    ingredients: list[IngredientItem] = Field(..., max_length=200)


@app.post("/api/save-recipe")
async def api_save_recipe(body: SaveRecipeRequest, request: Request):
    if not body.recipe_name.strip():
        raise HTTPException(status_code=400, detail="Recipe name is required.")
    if not body.ingredients:
        raise HTTPException(status_code=400, detail="No ingredients provided.")
    bring: Bring = request.app.state.bring
    uuid = await create_recipe(
        bring,
        body.recipe_name.strip(),
        [{"name": i.name, "quantity": i.quantity} for i in body.ingredients],
    )
    return {"uuid": uuid, "count": len(body.ingredients)}
