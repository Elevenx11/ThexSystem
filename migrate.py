import asyncio
import database

async def run_migration():
    await database.init_db()
    print("Migration check done.")

asyncio.run(run_migration())
