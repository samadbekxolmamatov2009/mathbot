from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from . import models
from .auth import limiter, router as auth_router
from .config import settings
from .courses import router as courses_router
from .turso_admin import router as turso_router
from .student_detail import router as student_detail_router
from .database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MatematikaPro API", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.include_router(auth_router)
app.include_router(courses_router)
app.include_router(turso_router)
app.include_router(student_detail_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}