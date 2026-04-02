from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
import os, uvicorn

ROOT = os.path.dirname(os.path.abspath(__file__))
app = FastAPI()

PAGES = {
    "/": "index.html",
    "/editor": "editor.html",
    "/identity": "identity.html",
    "/recorder": "recorder.html",
}

for route, filename in PAGES.items():
    path = os.path.join(ROOT, filename)
    app.get(route)(lambda p=path: FileResponse(p))

@app.get("/{path:path}")
async def static(path: str):
    full = os.path.join(ROOT, path)
    if os.path.isfile(full):
        return FileResponse(full)
    return Response(status_code=404)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
