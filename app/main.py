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
from app.bring_client import create_recipe

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


def cli():
    import socket
    import uvicorn
    import qrcode

    port = 8000
    # Get LAN IP by connecting to a public address (no traffic sent)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    url = f"http://{ip}:{port}"

    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    print(f"\n  {url}\n")

    uvicorn.run("app.main:app", host="0.0.0.0", port=port)


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
    try:
        result = await extract_ingredients(contents, media_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ingredient extraction failed: {exc}")
    return {
        "recipe_name": result.get("recipe_name", ""),
        "ingredients": result.get("ingredients", []),
        "instructions": result.get("instructions", ""),
    }


class IngredientItem(BaseModel):
    name: str
    quantity: str = ""


class SaveRecipeRequest(BaseModel):
    recipe_name: str
    ingredients: list[IngredientItem]
    instructions: str = ""


@app.post("/api/save-recipe")
async def api_save_recipe(body: SaveRecipeRequest, request: Request):
    if not body.recipe_name.strip():
        raise HTTPException(status_code=400, detail="Recipe name is required.")
    if not body.ingredients:
        raise HTTPException(status_code=400, detail="No ingredients provided.")
    bring: Bring = request.app.state.bring
    recipe_uuid = await create_recipe(
        bring,
        body.recipe_name.strip(),
        [{"name": i.name, "quantity": i.quantity} for i in body.ingredients],
        instructions=body.instructions.strip() or None,
    )
    return {"uuid": recipe_uuid, "count": len(body.ingredients)}
