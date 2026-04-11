from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

import os
import aiohttp
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from bring_api import Bring

from app.claude_client import extract_ingredients
from app.bring_client import get_lists, add_ingredients

SUPPORTED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"}
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


@app.get("/api/lists")
async def api_lists(request: Request):
    bring: Bring = request.app.state.bring
    return {"lists": await get_lists(bring)}


@app.post("/api/extract")
async def api_extract(image: UploadFile = File(...)):
    media_type = image.content_type or "image/jpeg"
    # Normalise non-standard MIME types from some mobile browsers
    if media_type == "image/jpg":
        media_type = "image/jpeg"
    if media_type not in SUPPORTED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported image type: {media_type}")
    contents = await image.read()
    try:
        ingredients = await extract_ingredients(contents, media_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ingredient extraction failed: {exc}")
    return {"ingredients": ingredients}


class Ingredient(BaseModel):
    name: str
    quantity: str = ""


class AddRequest(BaseModel):
    list_uuid: str
    ingredients: list[Ingredient]


@app.post("/api/add")
async def api_add(body: AddRequest, request: Request):
    bring: Bring = request.app.state.bring
    count = await add_ingredients(
        bring,
        body.list_uuid,
        [{"name": i.name, "quantity": i.quantity} for i in body.ingredients],
    )
    return {"added": count}
