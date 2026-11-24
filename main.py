import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
import aiosqlite
from fastapi import FastAPI, Request, Form, Depends, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
DB_NAME = "kino.db"
ADMIN_PASSWORD = "admin25802580"


@asynccontextmanager
async def init_db(app: FastAPI):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                year INTEGER NOT NULL,
                genre TEXT NOT NULL,
                poster_path TEXT,
                video_path TEXT,
                description TEXT
            )
        """)
        await db.commit()
        yield


app = FastAPI(lifespan=init_db)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


async def get_db():
    db = await aiosqlite.connect(DB_NAME)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def save_upload_file(upload_file: UploadFile) -> str:
    if not upload_file or not upload_file.filename:
        return None

    # Убрал дублирование импортов (они уже есть в начале файла)
    file_extension = os.path.splitext(upload_file.filename)[1]
    safe_name = f"{uuid.uuid4().hex}{file_extension}"
    file_path = BASE_DIR / "static" / "uploads" / safe_name

    with open(file_path, "wb") as f:
        content = await upload_file.read()
        f.write(content)

    return f"/static/uploads/{safe_name}"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: aiosqlite.Connection = Depends(get_db)):
    is_admin = request.cookies.get("is_admin") == "true"
    async with db.execute("SELECT * FROM movies ORDER BY id DESC") as cursor:
        rows = await cursor.fetchall()
    movies = [dict(row) for row in rows]

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
        request: Request,
        title: str = Form(...),
        year: int = Form(...),
        genre: str = Form(...),
        description: str = Form(None),
        poster: UploadFile = File(None),
        video: UploadFile = File(None),
        db: aiosqlite.Connection = Depends(get_db)
):
    if request.cookies.get("is_admin") != "true":
        return RedirectResponse(url="/login", status_code=303)

    poster_path = await save_upload_file(poster)
    video_path = await save_upload_file(video)

    await db.execute(
        "INSERT INTO movies (title, year, genre, description, poster_path, video_path) VALUES (?, ?, ?, ?, ?, ?)",
        (title, year, genre, description, poster_path, video_path)
    )
    await db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.post("/login")
async def proccess_login(response: RedirectResponse, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        redirect = RedirectResponse(url="/", status_code=303)
        redirect.set_cookie(key="is_admin", value="true", httponly=True)
        return redirect
    return RedirectResponse(url="/login", status_code=303)


@app.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    redirect = RedirectResponse(url="/", status_code=303)
    redirect.delete_cookie(key="is_admin")
    return redirect


@app.get("/movie/{movie_id}", response_class=HTMLResponse)
async def movie_detail(request: Request, movie_id: int, db: aiosqlite.Connection = Depends(get_db)):
    is_admin = request.cookies.get("is_admin") == "true"
    async with db.execute("SELECT * FROM movies WHERE id = ?", (movie_id,)) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return HTMLResponse("<h1>Фильм не найден</h1><a href='/'>На главную</a>", status_code=404)

    return templates.TemplateResponse(
        request=request, name="movie.html", context={"movie": dict(row), "is_admin": is_admin}
    )


@app.post("/movie/{movie_id}/delete")
async def delete_movie(request: Request, movie_id: int, db: aiosqlite.Connection = Depends(get_db)):
    if request.cookies.get("is_admin") != "true":
        return RedirectResponse(url="/login", status_code=303)

    async with db.execute("SELECT poster_path, video_path FROM movies WHERE id = ?", (movie_id,)) as cursor:
        row = await cursor.fetchone()

    if row:
        # Исправил кортеж для цикла
        for file_url in (row["poster_path"], row["video_path"]):
            if file_url:
                file_path = BASE_DIR / file_url.lstrip("/")
                if file_path.exists():
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"Не удалось удалить файл: {file_path}: {e}")

        await db.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
        await db.commit()

    return RedirectResponse(url="/", status_code=303)


@app.get("/movie/{movie_id}/edit", response_class=HTMLResponse)
async def edit_movie(request: Request, movie_id: int, db: aiosqlite.Connection = Depends(get_db)):
    if request.cookies.get("is_admin") != "true":
        return RedirectResponse(url="/login", status_code=303)

    async with db.execute("SELECT * FROM movies WHERE id = ?", (movie_id,)) as cursor:
        row = await cursor.fetchone()

    if not row:
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="edit.html", # <-- ИСПРАВЛЕНО
        context={"movie": dict(row)}
    )


@app.post("/movie/{movie_id}/edit")
async def edit_movie_post(
    movie_id: int,
    request: Request,
    title: str = Form(...),
    year: int = Form(...),
    genre: str = Form(...),
    description: str = Form(None),
    poster: UploadFile = File(None),
    video: UploadFile = File(None),
    db: aiosqlite.Connection = Depends(get_db)
):
    if request.cookies.get("is_admin") != "true":
        return RedirectResponse(url="/login", status_code=303)

    async with db.execute("SELECT poster_path, video_path FROM movies WHERE id = ?", (movie_id,)) as cursor:
        row = await cursor.fetchone()


    if not row:
        return RedirectResponse(url="/", status_code=303)

    old_poster = row["poster_path"]
    old_video = row["video_path"]

    new_poster = await save_upload_file(poster)
    poster_path = new_poster if new_poster else old_poster

    new_video = await save_upload_file(video)
    video_path = new_video if new_video else old_video

    await db.execute("""
        UPDATE movies 
        SET title = ?, year = ?, genre = ?, description = ?, poster_path = ?, video_path = ? 
        WHERE id = ?
    """, (title, year, genre, description, poster_path, video_path, movie_id))
    await db.commit()

    if new_poster and old_poster:
        old_p_path = BASE_DIR / old_poster.lstrip("/")
        if old_p_path.exists(): os.remove(old_p_path)

    if new_video and old_video:
        old_v_path = BASE_DIR / old_video.lstrip("/")
        if old_v_path.exists(): os.remove(old_v_path)

    return RedirectResponse(url=f"/movie/{movie_id}", status_code=303)