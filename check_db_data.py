import asyncio
import aiosqlite

async def check_data():
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute("SELECT * FROM ticket_settings") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                print(row)

asyncio.run(check_data())
