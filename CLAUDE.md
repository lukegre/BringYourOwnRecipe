# BringYourOwnRecipe

A mobile-friendly web app that extracts ingredients from a recipe photo using Claude vision and saves them as a recipe in Bring!

## How it works

1. User opens the app in their phone browser and takes (or uploads) a photo of a recipe
2. The image is sent to the backend, which calls Claude vision to extract the recipe name and ingredients
3. User reviews and edits the ingredient list and recipe name
4. On confirm, the backend creates a Bring! recipe via the `bring-api` library
5. The recipe appears in Bring! under **Recipes → Mine**

## Stack

- **Backend**: Python + FastAPI (`app/main.py`)
- **AI**: Anthropic SDK (`app/claude_client.py`) — `claude-sonnet-4-6` with vision
- **Bring! integration**: `bring-api` (miaucl's package) (`app/bring_client.py`)
- **Frontend**: Single-page HTML/JS, no build step (`app/static/index.html`)

## Project structure

```
app/
  main.py           # FastAPI app, routes, lifespan (aiohttp session + Bring login)
  claude_client.py  # extract_ingredients(bytes, media_type) → {recipe_name, ingredients}
  bring_client.py   # get_lists(), create_recipe() using BringTemplate + TemplateType.RECIPE
  static/
    index.html      # Full frontend: 4-state UI (upload → loading → preview → done)
requirements.txt
.env.example
```

## Environment variables

All three are required (put in `.env`):

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `BRING_EMAIL` | Bring! account email |
| `BRING_PASSWORD` | Bring! account password |

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in credentials
uvicorn app.main:app --reload --port 8000
```

To use from a phone on the same network:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
# open http://<your-machine-LAN-IP>:8000 on phone
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves `index.html` |
| `POST` | `/api/extract` | Multipart image upload → `{recipe_name, ingredients[]}` |
| `POST` | `/api/save-recipe` | JSON `{recipe_name, ingredients[]}` → creates Bring! recipe |

## Key implementation notes

- **`bring-api` vs `python-bring-api`**: Use `bring-api` (miaucl). It exposes `create_template()` and `TemplateType.RECIPE`. The other package (`python-bring-api`) only supports adding items to lists and has no recipe support.
- **`Ingredient` type**: `itemId` = ingredient name, `spec` = quantity string, `stock = False`
- **`BringTemplate`**: Populate `items` (not `ingredients`) for the shopping list items
- **Bring! object access**: `load_lists()` returns a dataclass — use `.lists`, `.listUuid`, `.name` (dot notation, not dict keys)
- **`aiohttp.ClientSession`**: Created once at startup via FastAPI lifespan, stored on `app.state.bring`. Do not create per-request.
- **Claude response format**: Returns a JSON object `{"recipe_name": str, "ingredients": [{name, quantity}]}`. The prompt instructs no markdown fences; the client strips them defensively anyway.
- **MIME type normalisation**: `image/jpg` is remapped to `image/jpeg` before sending to Anthropic.
