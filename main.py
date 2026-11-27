import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse
from db import init_db, get_all_movies, get_movie_by_id, add_movie_full, update_movie, delete_movie

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
ADMIN_PASSWORD = "admin25802580"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


async def save_upload_file(upload_file: UploadFile) -> str:
    if not upload_file or not upload_file.filename:
        return None
    file_extension = os.path.splitext(upload_file.filename)[1]
    safe_name = f"{uuid.uuid4().hex}{file_extension}"
    file_path = BASE_DIR / "static" / "uploads" / safe_name
    with open(file_path, "wb") as f:
        content = await upload_file.read()
        f.write(content)
    return f"/static/uploads/{safe_name}"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    is_admin = request.cookies.get("is_admin") == "true"
    movies = await get_all_movies()  # Берем из db.py
    return templates.TemplateResponse(
        request=request, name="index.html", context={"movies": movies, "is_admin": is_admin}
    )


@app.get("/add", response_class=HTMLResponse)
async def add(request: Request):
    if request.cookies.get("is_admin") != "true":
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="add.html")


@app.post("/add")
async def add_post(
        request: Request, title: str = Form(...), year: int = Form(...), genre: str = Form(...),
        description: str = Form(None), poster: UploadFile = File(None), video: UploadFile = File(None)
):
    if request.cookies.get("is_admin") != "true":
        return RedirectResponse(url="/login", status_code=303)

    poster_path = await save_upload_file(poster)
    video_path = await save_upload_file(video)

    await add_movie_full(title, year, genre, description, poster_path, video_path)  # Берем из db.py
    return RedirectResponse(url="/", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.post("/login")
async def proccess_login(password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        redirect = RedirectResponse(url="/", status_code=303)
        redirect.set_cookie(key="is_admin", value="true", httponly=True)
        return redirect
    return RedirectResponse(url="/login", status_code=303)


@app.get("/logout")
async def logout():
    redirect = RedirectResponse(url="/", status_code=303)
    redirect.delete_cookie(key="is_admin")
    return redirect


@app.get("/movie/{movie_id}", response_class=HTMLResponse)
async def movie_detail(request: Request, movie_id: int):
    is_admin = request.cookies.get("is_admin") == "true"
    movie = await get_movie_by_id(movie_id)  # Берем из db.py
    if not movie:
        return HTMLResponse("<h1>Фильм не найден</h1><a href='/'>На главную</a>", status_code=404)
    return templates.TemplateResponse(
        request=request, name="movie.html", context={"movie": movie, "is_admin": is_admin}
    )


@app.post("/movie/{movie_id}/delete")
async def delete_movie_route(request: Request, movie_id: int):
    if request.cookies.get("is_admin") != "true":
        return RedirectResponse(url="/login", status_code=303)

    movie = await get_movie_by_id(movie_id)
    if movie:
        # Удаляем локальные файлы (если сайт запущен локально)
        for file_url in (movie["poster_path"], movie["video_path"]):
            if file_url:
                file_path = BASE_DIR / file_url.lstrip("/")
                if file_path.exists():
                    os.remove(file_path)
        await delete_movie(movie_id)  # Берем из db.py
    return RedirectResponse(url="/", status_code=303)


@app.get("/movie/{movie_id}/edit", response_class=HTMLResponse)
async def edit_movie(movie_id: int, request: Request):
    if request.cookies.get("is_admin") != "true":
        return RedirectResponse(url="/login", status_code=303)
    movie = await get_movie_by_id(movie_id)
    if not movie:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request=request, name="edit.html", context={"movie": movie})


@app.post("/movie/{movie_id}/edit")
async def edit_movie_post(
        movie_id: int, request: Request, title: str = Form(...), year: int = Form(...), genre: str = Form(...),
        description: str = Form(None), poster: UploadFile = File(None), video: UploadFile = File(None)
):
    if request.cookies.get("is_admin") != "true":
        return RedirectResponse(url="/login", status_code=303)

    old_movie = await get_movie_by_id(movie_id)
    if not old_movie:
        return RedirectResponse(url="/", status_code=303)

    new_poster = await save_upload_file(poster)
    poster_path = new_poster if new_poster else old_movie["poster_path"]

    new_video = await save_upload_file(video)
    video_path = new_video if new_video else old_movie["video_path"]

    await update_movie(movie_id, title, year, genre, description, poster_path, video_path)  # Берем из db.py

    return RedirectResponse(url=f"/movie/{movie_id}", status_code=303)