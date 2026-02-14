import aiosqlite
import asyncpg
import os
import discord
from dotenv import load_dotenv

load_dotenv()

DB_PATH = 'bot_database.db'
DATABASE_URL = os.getenv('DATABASE_URL')

# Global pool for PostgreSQL
_pool = None

async def get_connection():
    if DATABASE_URL:
        global _pool
        if _pool is None:
            _pool = await asyncpg.create_pool(DATABASE_URL)
        return _pool
    else:
        return await aiosqlite.connect(DB_PATH)

async def execute(query, *args):
    if DATABASE_URL:
        pool = await get_connection()
        async with pool.acquire() as conn:
            # PostgreSQL uses $1, $2 instead of ?
            query = query.replace('?', '${}')
            query = query.format(*range(1, 100)) # Simple hack for small queries
            await conn.execute(query, *args)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(query, args)
            await db.commit()

# --- Refactoring to a cleaner structure ---

class Database:
    def __init__(self):
        self.is_pg = DATABASE_URL is not None
        self.pool = None

    async def connect(self):
        if self.is_pg and not self.pool:
            self.pool = await asyncpg.create_pool(DATABASE_URL)

    def _convert_query(self, query):
        if not self.is_pg:
            return query
        # Convert ? to $1, $2, etc.
        count = 1
        while '?' in query:
            query = query.replace('?', f'${count}', 1)
            count += 1
        return query

    async def execute(self, query, *args):
        await self.connect()
        query = self._convert_query(query)
        if self.is_pg:
            async with self.pool.acquire() as conn:
                await conn.execute(query, *args)
        else:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(query, args)
                await db.commit()

    async def fetchone(self, query, *args):
        await self.connect()
        query = self._convert_query(query)
        if self.is_pg:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
        else:
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, args) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None

    async def fetchall(self, query, *args):
        await self.connect()
        query = self._convert_query(query)
        if self.is_pg:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *args)
                return [dict(r) for r in rows]
        else:
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, args) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(r) for r in rows]

db_manager = Database()

async def init_db():
    # Initial tables setup
    queries = [
        '''CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            credits INTEGER DEFAULT 0,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            last_daily TEXT,
            rep INTEGER DEFAULT 0
        )''',
        '''CREATE TABLE IF NOT EXISTS ticket_settings (
            guild_id BIGINT PRIMARY KEY,
            category_id BIGINT,
            logs_channel_id BIGINT,
            staff_role_id BIGINT,
            staff_app_role_id BIGINT,
            inquiry_role_id BIGINT,
            complaint_role_id BIGINT,
            girl_verif_role_id BIGINT
        )''',
        '''CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id BIGINT PRIMARY KEY,
            leveling_channel_id BIGINT,
            ticket_counter INTEGER DEFAULT 0
        )''',
        '''CREATE TABLE IF NOT EXISTS logging_settings (
            guild_id BIGINT PRIMARY KEY,
            msg_log_id BIGINT,
            role_log_id BIGINT,
            server_log_id BIGINT,
            room_log_id BIGINT,
            voice_log_id BIGINT,
            mod_log_id BIGINT
        )''',
        '''CREATE TABLE IF NOT EXISTS warnings (
            warn_id SERIAL PRIMARY KEY if_pg,
            guild_id BIGINT,
            user_id BIGINT,
            moderator_id BIGINT,
            reason TEXT,
            timestamp TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS command_aliases (
            guild_id BIGINT,
            alias TEXT,
            command_name TEXT,
            PRIMARY KEY (guild_id, alias)
        )'''
    ]
    
    # Simple fix for SERIAL vs AUTOINCREMENT
    for q in queries:
        if db_manager.is_pg:
            q = q.replace('SERIAL PRIMARY KEY if_pg', 'SERIAL PRIMARY KEY')
            q = q.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
        else:
            q = q.replace('SERIAL PRIMARY KEY if_pg', 'INTEGER PRIMARY KEY AUTOINCREMENT')
            q = q.replace('BIGINT', 'INTEGER') # SQLite works with INTEGER for IDs
        await db_manager.execute(q)

    # Migrations for SQLite (PG usually starts fresh or handles this via external tools, but we can add basic check)
    if not db_manager.is_pg:
        async with aiosqlite.connect(DB_PATH) as db:
            # Check logging_settings
            async with db.execute("PRAGMA table_info(logging_settings)") as cursor:
                columns = [column[1] for column in await cursor.fetchall()]
                if 'voice_log_id' not in columns:
                    await db.execute('ALTER TABLE logging_settings ADD COLUMN voice_log_id INTEGER')
                    await db.commit()
            
            # Check ticket_settings
            async with db.execute("PRAGMA table_info(ticket_settings)") as cursor:
                columns = [column[1] for column in await cursor.fetchall()]
                to_add = {
                    'staff_app_role_id': 'INTEGER',
                    'inquiry_role_id': 'INTEGER',
                    'complaint_role_id': 'INTEGER',
                    'girl_verif_role_id': 'INTEGER'
                }
                for col, type in to_add.items():
                    if col not in columns:
                        await db.execute(f'ALTER TABLE ticket_settings ADD COLUMN {col} {type}')
                await db.commit()

# Helper functions mapped to the new db_manager
async def get_ticket_settings(guild_id):
    return await db_manager.fetchone('SELECT * FROM ticket_settings WHERE guild_id = ?', guild_id)

async def set_ticket_settings(guild_id, category_id, logs_channel_id, staff_role_id, staff_app_role_id, inquiry_role_id=None, complaint_role_id=None, girl_verif_role_id=None):
    if db_manager.is_pg:
        query = '''INSERT INTO ticket_settings (guild_id, category_id, logs_channel_id, staff_role_id, staff_app_role_id, inquiry_role_id, complaint_role_id, girl_verif_role_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(guild_id) DO UPDATE SET 
                   category_id=EXCLUDED.category_id, logs_channel_id=EXCLUDED.logs_channel_id, 
                   staff_role_id=EXCLUDED.staff_role_id, staff_app_role_id=EXCLUDED.staff_app_role_id,
                   inquiry_role_id=EXCLUDED.inquiry_role_id, complaint_role_id=EXCLUDED.complaint_role_id,
                   girl_verif_role_id=EXCLUDED.girl_verif_role_id'''
    else:
        query = 'INSERT OR REPLACE INTO ticket_settings (guild_id, category_id, logs_channel_id, staff_role_id, staff_app_role_id, inquiry_role_id, complaint_role_id, girl_verif_role_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
    await db_manager.execute(query, guild_id, category_id, logs_channel_id, staff_role_id, staff_app_role_id, inquiry_role_id, complaint_role_id, girl_verif_role_id)

async def get_guild_settings(guild_id):
    return await db_manager.fetchone('SELECT * FROM guild_settings WHERE guild_id = ?', guild_id)

async def set_leveling_channel(guild_id, channel_id):
    if db_manager.is_pg:
        query = 'INSERT INTO guild_settings (guild_id, leveling_channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET leveling_channel_id = EXCLUDED.leveling_channel_id'
    else:
        query = 'INSERT INTO guild_settings (guild_id, leveling_channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET leveling_channel_id = EXCLUDED.leveling_channel_id'
    await db_manager.execute(query, guild_id, channel_id)

async def get_and_increment_ticket_count(guild_id):
    row = await db_manager.fetchone('SELECT ticket_counter FROM guild_settings WHERE guild_id = ?', guild_id)
    if row is None:
        new_count = 1
        await db_manager.execute('INSERT INTO guild_settings (guild_id, ticket_counter) VALUES (?, ?)', guild_id, new_count)
    else:
        new_count = (row['ticket_counter'] or 0) + 1
        await db_manager.execute('UPDATE guild_settings SET ticket_counter = ? WHERE guild_id = ?', new_count, guild_id)
    return new_count

async def get_user(user_id):
    return await db_manager.fetchone('SELECT * FROM users WHERE user_id = ?', user_id)

async def create_user(user_id):
    if db_manager.is_pg:
        await db_manager.execute('INSERT INTO users (user_id) VALUES (?) ON CONFLICT DO NOTHING', user_id)
    else:
        await db_manager.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', user_id)

async def update_credits(user_id, amount):
    await db_manager.execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', amount, user_id)

async def set_last_daily(user_id, date_str):
    await db_manager.execute('UPDATE users SET last_daily = ? WHERE user_id = ?', date_str, user_id)

async def add_xp(user_id, amount):
    await db_manager.execute('UPDATE users SET xp = xp + ? WHERE user_id = ?', amount, user_id)

async def update_level(user_id, level):
    await db_manager.execute('UPDATE users SET level = ? WHERE user_id = ?', level, user_id)

async def get_logging_settings(guild_id):
    return await db_manager.fetchone('SELECT * FROM logging_settings WHERE guild_id = ?', guild_id)

async def set_logging_channel(guild_id, log_type, channel_id):
    valid_types = ['msg_log_id', 'role_log_id', 'server_log_id', 'room_log_id', 'voice_log_id', 'mod_log_id']
    if log_type not in valid_types: return False
    
    if db_manager.is_pg:
        query = f'INSERT INTO logging_settings (guild_id, {log_type}) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET {log_type} = EXCLUDED.{log_type}'
    else:
        query = f'INSERT INTO logging_settings (guild_id, {log_type}) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET {log_type} = EXCLUDED.{log_type}'
    await db_manager.execute(query, guild_id, channel_id)
    return True

async def add_warning(guild_id, user_id, moderator_id, reason):
    await db_manager.execute('''
        INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', guild_id, user_id, moderator_id, reason, discord.utils.utcnow().isoformat())

async def get_warnings(guild_id, user_id):
    return await db_manager.fetchall('SELECT * FROM warnings WHERE guild_id = ? AND user_id = ?', guild_id, user_id)

async def clear_warnings(guild_id, user_id):
    await db_manager.execute('DELETE FROM warnings WHERE guild_id = ? AND user_id = ?', guild_id, user_id)

async def add_alias(guild_id, alias, command_name):
    if db_manager.is_pg:
        query = 'INSERT INTO command_aliases (guild_id, alias, command_name) VALUES (?, ?, ?) ON CONFLICT(guild_id, alias) DO UPDATE SET command_name = EXCLUDED.command_name'
    else:
        query = 'INSERT OR REPLACE INTO command_aliases (guild_id, alias, command_name) VALUES (?, ?, ?)'
    await db_manager.execute(query, guild_id, alias, command_name)

async def remove_alias(guild_id, alias):
    await db_manager.execute('DELETE FROM command_aliases WHERE guild_id = ? AND alias = ?', guild_id, alias)

async def get_aliases(guild_id):
    return await db_manager.fetchall('SELECT * FROM command_aliases WHERE guild_id = ?', guild_id)
