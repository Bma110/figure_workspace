from fastapi import FastAPI

app = FastAPI(title="Figure Workspace", version="0.1.0")


@app.get("/api/health")
def health():
    return {"ok": True}
