import asyncio
from app.database import async_session
from sqlalchemy import text

async def check():
    async with async_session() as s:
        r = await s.execute(text("SELECT COUNT(*) FROM playlist_tracks"))
        print("Total tracks in DB:", r.scalar())
        r2 = await s.execute(text("SELECT file_url, title, artist FROM playlist_tracks"))
        for row in r2.fetchall():
            print(f"  {row[2]} - {row[1]} | {row[0]}")

asyncio.run(check())
