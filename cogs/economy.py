import discord
from discord.ext import commands
import database
from datetime import datetime, timedelta
import random

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await database.init_db()

    @commands.hybrid_command(name='credits', aliases=['credit', 'bal', 'balance'], help='عرض الرصيد الخاص بك أو رصيد عضو آخر')
    async def credits(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        if member.bot:
            return await ctx.send("❌ البوتات ليس لديها رصيد.")

        user_data = await database.get_user(member.id)
        if not user_data:
            await database.create_user(member.id)
            user_data = await database.get_user(member.id)

        balance = user_data[1]  # credits column
        
        embed = discord.Embed(
            description=f"💰 **{member.display_name}**, رصيدك هو: `${balance}`",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='daily', help='الحصول على المكافأة اليومية')
    @commands.cooldown(1, 86400, commands.BucketType.user) # 24 hours cooldown
    async def daily(self, ctx):
        user_data = await database.get_user(ctx.author.id)
        if not user_data:
            await database.create_user(ctx.author.id)
            user_data = await database.get_user(ctx.author.id)

        amount = random.randint(200, 1000)
        await database.update_credits(ctx.author.id, amount)
        
        embed = discord.Embed(
            description=f"✅ **{ctx.author.display_name}**, لقد حصلت على `${amount}` مكافأة يومية!",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @daily.error
    async def daily_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            seconds = int(error.retry_after)
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            await ctx.send(f"⏳ يمكنك الحصول على المكافأة اليومية بعد: `{hours}h {minutes}m {seconds}s`", ephemeral=True)

    @commands.hybrid_command(name='give', aliases=['transfer', 'pay'], help='تحويل رصيد لعضو آخر')
    async def give(self, ctx, member: discord.Member, amount: int):
        if member == ctx.author:
            return await ctx.send("❌ لا يمكنك تحويل رصيد لنفسك.")
        if member.bot:
            return await ctx.send("❌ لا يمكنك تحويل رصيد لبوت.")
        if amount <= 0:
            return await ctx.send("❌ المبلغ يجب أن يكون أكبر من صفر.")

        author_data = await database.get_user(ctx.author.id)
        if not author_data or author_data[1] < amount:
            return await ctx.send("❌ ليس لديك رصيد كافٍ.")

        # Ensure receiver exists in DB
        receiver_data = await database.get_user(member.id)
        if not receiver_data:
            await database.create_user(member.id)

        # Process transfer
        await database.update_credits(ctx.author.id, -amount)
        await database.update_credits(member.id, amount)

        await ctx.send(f"✅ **{ctx.author.display_name}**, تم تحويل `${amount}` إلى {member.mention} بنجاح.")

async def setup(bot):
    await bot.add_cog(Economy(bot))
