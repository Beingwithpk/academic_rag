from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.db import init_tables
from src.routes.auth import router as auth_router
from src.routes.courses import router as courses_router
from src.routes.notes import router as notes_router
from src.routes.chat import router as chat_router

app = FastAPI(
    title="Academic RAG & Management System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_tables()

# Register API Routers
app.include_router(auth_router)
app.include_router(courses_router)
app.include_router(notes_router)
app.include_router(chat_router)

# Mount frontend static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")