import asyncio
import aiosqlite

async def check_table():
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute("PRAGMA table_info(ticket_settings);") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                print(row)

asyncio.run(check_table())
