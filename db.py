import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

# Turso принимает HTTP-запросы по этому адресу (заменяем libsql:// на https://)
TURSO_URL = os.getenv("TURSO_URL", "").replace("libsql://", "https://") + "/v2/pipeline"
TURSO_TOKEN = os.getenv("TURSO_TOKEN")

headers = {
    "Authorization": f"Bearer {TURSO_TOKEN}",
    "Content-Type": "application/json"
}


async def execute_sql(sql: str, params: list = None):
    """Отправляет SQL-запрос напрямую в Turso по HTTP"""
    args = []
    if params:
        for p in params:
            if isinstance(p, int):
                args.append({"type": "integer", "value": p})
            elif p is None:
                args.append({"type": "null"})
            else:
                args.append({"type": "text", "value": str(p)})

    payload = {
        "requests": [
            {"type": "execute", "stmt": {"sql": sql, "args": args}},
            {"type": "close"}
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(TURSO_URL, headers=headers, json=payload) as response:
            data = await response.json()

            # Если Turso вернул ошибку
            if data.get("results", [{}])[0].get("type") == "error":
                print(f"Ошибка SQL: {data}")
                return []

            result = data["results"][0]["response"]["result"]
            cols = [col["name"] for col in result["cols"]]
            rows = result["rows"]

            # Превращаем строки в словари
            return [dict(zip(cols, row)) for row in rows]


# --- ВСЕ ФУНКЦИИ ТЕПЕРЬ ПРОСТО ВЫЗЫВАЮТ execute_sql ---

async def init_db():
    await execute_sql("""
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


async def get_all_movies():
    return await execute_sql("SELECT * FROM movies ORDER BY id DESC")


async def get_movie_by_id(movie_id: int):
    rows = await execute_sql("SELECT * FROM movies WHERE id = ?", [movie_id])
    return rows[0] if rows else None


async def add_movie_full(title, year, genre, description, poster_path, video_path):
    await execute_sql(
        "INSERT INTO movies (title, year, genre, description, poster_path, video_path) VALUES (?, ?, ?, ?, ?, ?)",
        [title, year, genre, description, poster_path, video_path]
    )


async def update_movie(movie_id, title, year, genre, description, poster_path, video_path):
    await execute_sql(
        "UPDATE movies SET title=?, year=?, genre=?, description=?, poster_path=?, video_path=? WHERE id=?",
        [title, year, genre, description, poster_path, video_path, movie_id]
    )


async def delete_movie(movie_id: int):
    await execute_sql("DELETE FROM movies WHERE id = ?", [movie_id])


# --- Для бота ---
async def search_movies(query: str):
    return await execute_sql(
        "SELECT id, title, year FROM movies WHERE LOWER(title) LIKE LOWER(?) LIMIT 5",
        [f"%{query}%"]
    )


async def add_movie(title, year, genre, description):
    await execute_sql(
        "INSERT INTO movies (title, year, genre, description) VALUES (?, ?, ?, ?)",
        [title, year, genre, description]
    )


async def get_movies(limit: int = 10):
    return await execute_sql("SELECT id, title, year FROM movies ORDER BY id DESC LIMIT ?", [limit])