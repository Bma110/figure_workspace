from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fw.api import router

app = FastAPI(title="Figure Workspace", version="0.1.0")
app.include_router(router)


@app.get("/api/health")
def health():
    return {"ok": True}


# 静态托管（index.html 等）——前端目录任务前留空不影响接口测试
from pathlib import Path  # noqa: E402
_static = Path(__file__).resolve().parent / "static"
_static.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
