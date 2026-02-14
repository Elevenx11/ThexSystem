import discord
from discord.ext import commands
import datetime

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='kick', help='طرد عضو من السيرفر')
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = None):
        await member.kick(reason=reason)
        await ctx.send(f'✅ تم طرد {member.mention} للسبب: {reason}')

    @commands.hybrid_command(name='ban', help='حظر عضو من السيرفر')
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = None):
        await member.ban(reason=reason)
        await ctx.send(f'⛔ تم حظر {member.mention} للسبب: {reason}')

    @commands.hybrid_command(name='unban', help='إزالة الحظر عن عضو')
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, *, member_id: str):
        try:
            user = await self.bot.fetch_user(int(member_id))
            await ctx.guild.unban(user)
            await ctx.send(f'✅ تم إزالة الحظر عن {user.mention}')
        except Exception as e:
            await ctx.send(f'❌ حدث خطأ: {e}')

    @commands.hybrid_command(name='purge', aliases=['clear'], help='مسح عدد معين من الرسائل')
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        await ctx.channel.purge(limit=amount + 1)
        # رسالة مؤقتة وتختفي
        await ctx.send(f'🧹 تم مسح {amount} رسالة.', delete_after=5)

    @commands.hybrid_command(name='mute', help='إسكات عضو (Timeout) لمدة معينة بالدقائق')
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, minutes: int, *, reason: str = "No reason"):
        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await ctx.send(f'🔇 تم إسكات {member.mention} لمدة {minutes} دقيقة. السبب: {reason}')

    @commands.hybrid_command(name='unmute', help='إزالة الإسكات عن عضو')
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member):
        await member.timeout(None)
        await ctx.send(f'🔊 تم إزالة الإسكات عن {member.mention}')

    @commands.hybrid_command(name='lock', help='قفل الروم لمنع الكتابة')
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(f'🔒 تم قفل القناة {ctx.channel.mention}')

    @commands.hybrid_command(name='unlock', help='فتح الروم للكتابة')
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
        await ctx.send(f'🔓 تم فتح القناة {ctx.channel.mention}')

    @commands.hybrid_command(name='slowmode', help='تفعيل وضع البطء في القناة')
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int):
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send(f'⏳ تم ضبط وضع البطء إلى {seconds} ثانية.')

    @commands.hybrid_command(name='nick', help='تغيير لقب عضو')
    @commands.has_permissions(manage_nicknames=True)
    async def nick(self, ctx, member: discord.Member, *, nickname: str = None):
        await member.edit(nick=nickname)
        await ctx.send(f'✅ تم تغيير لقب {member.mention} إلى {nickname or "الافتراضي"}.')

    # Basic Auto-Mod: Anti-link (Optional, can be disabled)
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.author.guild_permissions.manage_messages:
            return
        
        # Simple anti-link (covers common patterns)
        links = ["http://", "https://", "discord.gg/"]
        if any(link in message.content for link in links):
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention}, يمنع إرسال الروابط في هذا السيرفر!", delete_after=5)

    # Error Handling for permissions
    @kick.error
    @ban.error
    @purge.error
    @mute.error
    @lock.error
    @unlock.error
    async def mod_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ ليس لديك الصلاحيات الكافية لاستخدام هذا الأمر.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ يرجى التأكد من كتابة الأمر بشكل صحيح وتحديد العضو/العدد.")

    @commands.hybrid_command(name='warn', help='تحذير عضو')
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "بدون سبب"):
        import database
        await database.add_warning(ctx.guild.id, member.id, ctx.author.id, reason)
        
        # Log to mod_log if exists
        logging_cog = self.bot.get_cog('Logging')
        if logging_cog:
            log_channel = await logging_cog.get_channel(ctx.guild, "mod_log_id")
            if log_channel:
                embed = discord.Embed(title="⚠️ تحذير جديد", color=discord.Color.gold(), timestamp=discord.utils.utcnow())
                embed.set_author(name=f"{member}", icon_url=member.display_avatar.url)
                embed.add_field(name="بواسطة", value=ctx.author.mention, inline=True)
                embed.add_field(name="السبب", value=reason, inline=True)
                embed.set_footer(text=f"ID: {member.id}")
                await log_channel.send(embed=embed)

        await ctx.send(f'⚠️ تم تحذير {member.mention}. السبب: {reason}')

    @commands.hybrid_command(name='warnings', help='عرض تحذيرات عضو')
    @commands.has_permissions(moderate_members=True)
    async def warnings(self, ctx, member: discord.Member):
        import database
        warns = await database.get_warnings(ctx.guild.id, member.id)
        if not warns:
            return await ctx.send(f"✅ لا يوجد تحذيرات لـ {member.mention}.")
            
        embed = discord.Embed(title=f"📋 تحذيرات {member}", color=discord.Color.orange())
        for i, warn in enumerate(warns, 1):
            moderator = ctx.guild.get_member(warn['moderator_id'])
            mod_text = moderator.mention if moderator else f"ID: {warn['moderator_id']}"
            embed.add_field(
                name=f"تحذير {i}", 
                value=f"**بواسطة:** {mod_text}\n**السبب:** {warn['reason']}\n**التوقيت:** <t:{int(datetime.datetime.fromisoformat(warn['timestamp']).timestamp())}:R>", 
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='clearwarns', help='مسح جميع تحذيرات عضو')
    @commands.has_permissions(administrator=True)
    async def clearwarns(self, ctx, member: discord.Member):
        import database
        await database.clear_warnings(ctx.guild.id, member.id)
        await ctx.send(f"✅ تم مسح جميع تحذيرات {member.mention}.")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
