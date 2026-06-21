import os
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
from analyze import router

load_dotenv()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Credit Risk API", docs_url=None, redoc_url=None)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(router)

# Serve static assets (CSS, JS, fonts if any)
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/api/client-config")
def client_config():
    """Return non-secret client config. API key only if set (same-origin requests only)."""
    return {"api_key": os.getenv("CREDIT_RISK_API_KEY", "")}


@app.get("/")
def index():
    return FileResponse("static/index.html")
