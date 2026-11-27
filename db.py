import os
from dotenv import load_dotenv
import libsql_client

load_dotenv()

TURSO_URL = os.getenv("TURSO_URL")
TURSO_TOKEN = os.getenv("TURSO_TOKEN")

print(f"DEBUG RENDER: URL = '{TURSO_URL}'")
print(f"DEBUG RENDER: TOKEN = {'ЕСТЬ' if TURSO_TOKEN else 'НЕТ'}")

def get_client():
    return libsql_client.create_client(url=TURSO_URL, auth_token=TURSO_TOKEN)

def to_dict(result):
    """Превращает ответ Turso в список словарей"""
    return [dict(zip(result.columns, row)) for row in result.rows]


async def init_db():
    client = get_client()
    try:
        await client.execute("""
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
    finally:
        await client.close()

async def delete_movie(movie_id: int):
    """Удаляет фильм по ID"""
    client = get_client()
    try:
        await client.execute("DELETE FROM movies WHERE id = ?", [movie_id])
    finally:
        await client.close()

# --- ФУНКЦИИ ДЛЯ БОТА (bot.py) ---

async def search_movies(query: str):
    """Ищет фильмы по названию (для поиска в боте)"""
    client = get_client()
    try:
        result = await client.execute(
            "SELECT id, title, year FROM movies WHERE LOWER(title) LIKE LOWER(?) LIMIT 5",
            [f"%{query}%"]
        )
        return to_dict(result)
    finally:
        await client.close()

async def add_movie(title: str, year: int, genre: str, description: str):
    """Добавляет фильм без файлов (из бота)"""
    client = get_client()
    try:
        await client.execute(
            "INSERT INTO movies (title, year, genre, description) VALUES (?, ?, ?, ?)",
            [title, year, genre, description]
        )
    finally:
        await client.close()

async def get_movies(limit: int = 10):
    """Получает последние фильмы (для списка удаления в боте)"""
    client = get_client()
    try:
        result = await client.execute("SELECT id, title, year FROM movies ORDER BY id DESC LIMIT ?", [limit])
        return to_dict(result)
    finally:
        await client.close()

# --- ФУНКЦИИ ДЛЯ САЙТА (main.py) ---

async def get_all_movies():
    """Получает ВСЕ фильмы (для главной страницы сайта)"""
    client = get_client()
    try:
        result = await client.execute("SELECT * FROM movies ORDER BY id DESC")
        return to_dict(result)
    finally:
        await client.close()

async def get_movie_by_id(movie_id: int):
    """Получает один фильм по ID (для страницы фильма и редактирования)"""
    client = get_client()
    try:
        result = await client.execute("SELECT * FROM movies WHERE id = ?", [movie_id])
        data = to_dict(result)
        return data[0] if data else None
    finally:
        await client.close()

async def add_movie_full(title, year, genre, description, poster_path, video_path):
    """Добавляет фильм с файлами (из формы на сайте)"""
    client = get_client()
    try:
        await client.execute(
            "INSERT INTO movies (title, year, genre, description, poster_path, video_path) VALUES (?, ?, ?, ?, ?, ?)",
            [title, year, genre, description, poster_path, video_path]
        )
    finally:
        await client.close()

async def update_movie(movie_id, title, year, genre, description, poster_path, video_path):
    """Обновляет фильм (при редактировании на сайте)"""
    client = get_client()
    try:
        await client.execute(
            "UPDATE movies SET title=?, year=?, genre=?, description=?, poster_path=?, video_path=? WHERE id=?",
            [title, year, genre, description, poster_path, video_path, movie_id]
        )
    finally:
        await client.close()