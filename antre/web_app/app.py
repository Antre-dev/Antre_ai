# web_app/app.py

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from antre.agent import handle_message


app = FastAPI()

templates = Jinja2Templates(directory="antre/web_app/templates")

app.mount(
    "/static",
    StaticFiles(directory="antre/web_app/static"),
    name="static"
)


class ChatRequest(BaseModel):
    message: str


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


@app.post("/chat")
async def chat(data: ChatRequest):
    response = await handle_message(data.message)

    return {
        "response": response
    }