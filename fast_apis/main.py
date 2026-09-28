"""Read-only demo API for existing DineIQ analytical artifacts."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from fast_apis.services import analytics_service as analytics
from fast_apis.services import auth_service as auth
from fast_apis import database
from fast_apis.routes.dynamic import router as dynamic_router
from fast_apis.routes.management import router as management_router
from fast_apis.routes.exports import router as exports_router


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "DineiqFrantend" / "template"

app = FastAPI(title="DineIQ Demo API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5500", "http://127.0.0.1:5500",
        "http://localhost:8000", "http://127.0.0.1:8000",
    ],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)
app.include_router(dynamic_router)
app.include_router(management_router)
app.include_router(exports_router)


def deny_unscoped_regional(user):
    if "REGIONAL_MANAGER" in user["roles"] and "ADMIN" not in user["roles"]:
        raise HTTPException(403, "This legacy report has no regional scope")


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "DineIQ API"}


@app.post("/api/register")
def register_account(payload: RegisterRequest):
    user, error = auth.register(payload.username, payload.email, payload.password)
    if error:
        raise HTTPException(status_code=409 if "already exists" in error else 422, detail=error)
    return {"success": True, "message": "Account created successfully.", "user": user}


@app.post("/api/login")
def login_account(payload: LoginRequest):
    result = auth.login(payload.email, payload.password)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return {"success": True, "message": "Login successful.", **result}


@app.get("/api/auth/me")
def auth_me(user=Depends(auth.current_user)):
    return user


@app.get("/api/dashboard/summary")
def dashboard_summary(user=Depends(auth.current_user)):
    deny_unscoped_regional(user)
    return analytics.get_executive_summary()


@app.get("/api/menu/intelligence")
def menu_intelligence(classification: str | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), user=Depends(auth.current_user)):
    deny_unscoped_regional(user)
    return analytics.get_menu_intelligence(classification, limit, offset)


@app.get("/api/customers/segments")
def customer_segments(limit: int = Query(25, ge=1, le=200), offset: int = Query(0, ge=0), user=Depends(auth.current_user)):
    deny_unscoped_regional(user)
    return analytics.get_customer_segments(limit, offset)


@app.get("/api/forecast")
def forecast(limit: int = Query(30, ge=1, le=200), offset: int = Query(0, ge=0), user=Depends(auth.current_user)):
    deny_unscoped_regional(user)
    return analytics.get_forecast(limit, offset)


@app.get("/api/model-comparison")
def model_comparison(limit: int = Query(30, ge=1, le=200), offset: int = Query(0, ge=0), user=Depends(auth.current_user)):
    deny_unscoped_regional(user)
    return analytics.get_model_comparison(limit, offset)


@app.get("/api/recommendations")
def recommendations(priority: str | None = None, type: str | None = None, limit: int = Query(30, ge=1, le=200), offset: int = Query(0, ge=0), user=Depends(auth.current_user)):
    deny_unscoped_regional(user)
    return analytics.get_recommendations(priority, type, limit, offset)


@app.get("/api/models/status")
def model_status(user=Depends(auth.current_user)):
    return analytics.get_model_status()


@app.get("/api/reports/{report_name}/download")
def download_report(report_name: str, user=Depends(auth.current_user)):
    deny_unscoped_regional(user)
    path = analytics.download_path(report_name)
    if path is None:
        raise HTTPException(status_code=404, detail="Report not available")
    database.audit("report_export", user["id"], "report", report_name)
    return FileResponse(path, media_type="text/csv", filename=path.name)


@app.get("/")
def home():
    return RedirectResponse("/app/index.html")


app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
