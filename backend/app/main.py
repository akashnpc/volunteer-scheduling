from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app import config
from app.db import SessionLocal, engine
from app.db_setup import init_db
from app.routers import auth, insights, programs, shifts, signups, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(engine)
    if config.SEED_ON_STARTUP:
        from app.seed import seed_if_empty

        with SessionLocal() as db:
            seed_if_empty(db)
    yield


app = FastAPI(title="Volunteer Scheduling API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_origin_regex=config.CORS_ORIGIN_REGEX,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    """Flatten pydantic's error list into one readable sentence for the UI."""
    parts = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"] if p not in ("body", "query", "path"))
        parts.append(f"{field}: {err['msg']}" if field else err["msg"])
    return JSONResponse(status_code=422, content={"detail": "; ".join(parts) or "Invalid request"})


@app.exception_handler(IntegrityError)
async def integrity_error(request: Request, exc: IntegrityError):
    # Reaching here means a database constraint caught something the service
    # checks missed (e.g. a race). Refuse rather than 500.
    return JSONResponse(status_code=409, content={"detail": "That change conflicts with existing data"})


@app.get("/health")
def health():
    return {"status": "ok"}


for module in (auth, users, programs, shifts, signups, insights):
    app.include_router(module.router, prefix="/api")
