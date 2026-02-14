import discord
from discord.ext import commands
import database
import random
import time

# نظام اللفل معطل حالياً بناءً على طلب المستخدم
ENABLED = False

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cooldowns = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if not ENABLED:
            return
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        current_time = time.time()
        
        # 60s cooldown for XP
        if user_id in self._cooldowns and current_time - self._cooldowns[user_id] < 60:
            return

        self._cooldowns[user_id] = current_time

        user_data = await database.get_user(user_id)
        if not user_data:
            await database.create_user(user_id)
            user_data = await database.get_user(user_id)

        current_xp = user_data[2]
        current_lvl = user_data[3]
        
        xp_gain = random.randint(5, 15)
        new_xp = current_xp + xp_gain
        
        # Level up logic: level = floor(0.1 * sqrt(xp)) or similar
        # Simple level up: (level + 1) * 100
        next_lvl_xp = (current_lvl + 1) * 100
        
        if new_xp >= next_lvl_xp:
            new_lvl = current_lvl + 1
            await database.update_level(user_id, new_lvl)
            await database.add_xp(user_id, xp_gain)
            
            # الحصول على قناة اللفل المخصصة
            guild_settings = await database.get_guild_settings(message.guild.id)
            target_channel = message.channel
            if guild_settings and guild_settings[1]:
                lvl_chan = message.guild.get_channel(guild_settings[1])
                if lvl_chan:
                    target_channel = lvl_chan

            try:
                await target_channel.send(f"🎉 مبروك {message.author.mention}! لقد ارتفع مستواك إلى المستوى **{new_lvl}**!")
            except:
                pass
        else:
            await database.add_xp(user_id, xp_gain)

    @commands.hybrid_command(name='rank', aliases=['level'], help='عرض مستواك الحالي')
    async def rank(self, ctx, member: discord.Member = None):
        if not ENABLED:
            return await ctx.send("❌ نظام اللفل معطل حالياً.")
        member = member or ctx.author
        if member.bot:
            return await ctx.send("❌ البوتات ليس لديها مستوى.")

        user_data = await database.get_user(member.id)
        if not user_data:
            await database.create_user(member.id)
            user_data = await database.get_user(member.id)

        xp = user_data[2]
        lvl = user_data[3]
        next_lvl_xp = (lvl + 1) * 100

        embed = discord.Embed(title=f"Rank - {member.display_name}", color=0x3498db)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="المستوى (Level)", value=f"**{lvl}**", inline=True)
        embed.add_field(name="الخبرة (XP)", value=f"**{xp} / {next_lvl_xp}**", inline=True)
        
        # Progress bar (visual)
        progress = int((xp / next_lvl_xp) * 10)
        bar = "🟦" * progress + "⬜" * (10 - progress)
        embed.add_field(name="التقدم", value=bar, inline=False)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='top', aliases=['lb', 'leaderboard'], help='عرض قائمة المتصدرين')
    async def leaderboard(self, ctx):
        if not ENABLED:
            return await ctx.send("❌ نظام اللفل معطل حالياً.")
        async with database.aiosqlite.connect(database.DB_PATH) as db:
            async with db.execute('SELECT user_id, xp, level FROM users ORDER BY xp DESC LIMIT 10') as cursor:
                top_users = await cursor.fetchall()

        if not top_users:
            return await ctx.send("لا يوجد بيانات لعرضها بعد.")

        description = ""
        for i, (uid, xp, lvl) in enumerate(top_users, 1):
            user = self.bot.get_user(uid)
            name = user.name if user else f"Unknown ({uid})"
            description += f"**#{i}** | {name} - Level: `{lvl}` | XP: `{xp}`\n"

        embed = discord.Embed(title="🏆 قائمة المتصدرين (Level)", description=description, color=0xf1c40f)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='setlevelingchannel', help='تحديد قناة إشعارات اللفل')
    @commands.has_permissions(administrator=True)
    async def set_level_channel(self, ctx, channel: discord.TextChannel):
        if not ENABLED:
            return await ctx.send("❌ نظام اللفل معطل حالياً.")
        await database.set_leveling_channel(ctx.guild.id, channel.id)
        await ctx.send(f"✅ تم تحديد قناة {channel.mention} لإرسال إشعارات لفل مستوى الأعضاء.")

async def setup(bot):
    if ENABLED:
        await bot.add_cog(Leveling(bot))
    else:
        print("Leveling system is DISABLED.")
