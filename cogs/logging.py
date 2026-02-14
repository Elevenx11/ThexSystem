import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import database

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._deleted_messages = set() # مخزن مؤقت لمنع تكرار لوق الحذف
        self._edited_messages = {} # مخزن مؤقت لمنع تكرار لوق التعديل لنفس النص

    async def get_channel(self, guild, channel_id_key):
        if not guild: return None
        settings = await database.get_logging_settings(guild.id)
        if settings and settings.get(channel_id_key):
            return guild.get_channel(settings.get(channel_id_key))
        
        # Fallback to old behavior if not set
        return discord.utils.get(guild.text_channels, name="logs") or \
               discord.utils.get(guild.text_channels, name="log") or \
               discord.utils.get(guild.text_channels, name="بصمة")

    # Configuration Commands
    @app_commands.command(name="set-log", description="تحديد قناة لنوع معين من اللوقات")
    @app_commands.describe(
        log_type="نوع اللوق المحدد",
        channel="القناة التي سيتم إرسال اللوق إليها"
    )
    @app_commands.choices(log_type=[
        app_commands.Choice(name="رسائل محذوفة ومعدلة", value="msg_log_id"),
        app_commands.Choice(name="رتب (إنشاء، حذف، تعديل)", value="role_log_id"),
        app_commands.Choice(name="تعديلات السيرفر والأعضاء", value="server_log_id"),
        app_commands.Choice(name="رومات (إنشاء، حذف، تعديل)", value="room_log_id"),
        app_commands.Choice(name="رومات صوتية (دخول، خروج، سحب، ميوت)", value="voice_log_id"),
        app_commands.Choice(name="عقوبات (تايم أوت، طرد، بند)", value="mod_log_id"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def set_log(self, interaction: discord.Interaction, log_type: str, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        await database.set_logging_channel(interaction.guild.id, log_type, channel.id)
        
        log_type_names = {
            "msg_log_id": "الرسائل",
            "role_log_id": "الرتب",
            "server_log_id": "السيرفر والاعضاء",
            "room_log_id": "الرومات",
            "voice_log_id": "الرومات الصوتية",
            "mod_log_id": "العقوبات"
        }
        
        embed = discord.Embed(
            title="✅ تم تحديث الإعدادات",
            description=f"تم تحديد قناة {channel.mention} للوقات **{log_type_names[log_type]}**.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)

    # --- Message Events ---
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or message.guild is None: return
        log_channel = await self.get_channel(message.guild, "msg_log_id")
        if not log_channel: return

        deleter = "غير معروف (ربما صاحب الرسالة)"
        try:
            async for entry in message.guild.audit_logs(limit=1, action=discord.AuditLogAction.message_delete):
                if entry.target.id == message.author.id and (discord.utils.utcnow() - entry.created_at).total_seconds() < 5:
                    deleter = entry.user.mention
                    break
        except:
            pass

        if message.id in self._deleted_messages: return
        self._deleted_messages.add(message.id)
        # إزالة المعرف بعد 5 ثواني لتوفير الذاكرة
        self.bot.loop.call_later(5, lambda: self._deleted_messages.discard(message.id))

        embed = discord.Embed(title="🗑️ رسالة محذوفة", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.set_author(name=f"{message.author}", icon_url=message.author.display_avatar.url)
        embed.add_field(name="القناة", value=message.channel.mention, inline=True)
        embed.add_field(name="حذف بواسطة", value=deleter, inline=True)
        embed.add_field(name="محتوى الرسالة", value=message.content or "لا يوجد نص (ممكن صورة)", inline=False)
        embed.set_footer(text=f"User ID: {message.author.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content: return
        log_channel = await self.get_channel(before.guild, "msg_log_id")
        if not log_channel: return

        # منع تكرار الوبر المتصل بالروابط (Unfurl)
        msg_key = f"{before.id}:{after.content}"
        if self._edited_messages.get(before.id) == after.content: return
        self._edited_messages[before.id] = after.content
        self.bot.loop.call_later(5, lambda: self._edited_messages.pop(before.id, None))

        embed = discord.Embed(title="📝 رسالة معدلة", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
        embed.set_author(name=f"{before.author}", icon_url=before.author.display_avatar.url)
        embed.add_field(name="القناة", value=before.channel.mention, inline=True)
        embed.add_field(name="الرابط", value=f"[انتقل للرسالة]({after.jump_url})", inline=True)
        embed.add_field(name="قبل", value=before.content[:1024] or "بدون نص", inline=False)
        embed.add_field(name="بعد", value=after.content[:1024] or "بدون نص", inline=False)
        embed.set_footer(text=f"User ID: {before.author.id}")
        await log_channel.send(embed=embed)

    # --- Member Events (Timeouts included) ---
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Timeout Check
        if before.timed_out_until != after.timed_out_until:
            log_channel = await self.get_channel(after.guild, "mod_log_id")
            if not log_channel: return

            if after.timed_out_until:
                # Member got timed out
                moderator = "غير معروف"
                duration = after.timed_out_until - discord.utils.utcnow()
                minutes = round(duration.total_seconds() / 60)
                
                try:
                    async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                        if entry.target.id == after.id and hasattr(entry.after, 'communication_disabled_until'):
                            moderator = entry.user.mention
                            break
                except:
                    pass

                embed = discord.Embed(title="⏳ تم إعطاء تايم أوت", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
                embed.set_author(name=f"{after}", icon_url=after.display_avatar.url)
                embed.add_field(name="بواسطة", value=moderator, inline=True)
                embed.add_field(name="المدة", value=f"{minutes} دقيقة", inline=True)
                embed.add_field(name="ينتهي في", value=discord.utils.format_dt(after.timed_out_until, style='R'), inline=False)
                await log_channel.send(embed=embed)
            else:
                # Timeout removed
                moderator = "غير معروف"
                try:
                    async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                        if entry.target.id == after.id and entry.before.communication_disabled_until and not entry.after.communication_disabled_until:
                            moderator = entry.user.mention
                            break
                except:
                    pass
                
                embed = discord.Embed(title="🔊 تم إزالة التايم أوت", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                embed.set_author(name=f"{after}", icon_url=after.display_avatar.url)
                embed.add_field(name="بواسطة", value=moderator, inline=True)
                await log_channel.send(embed=embed)

        # Role Changes Check
        if before.roles != after.roles:
            log_channel = await self.get_channel(after.guild, "role_log_id")
            if not log_channel: return

            added_roles = [role for role in after.roles if role not in before.roles]
            removed_roles = [role for role in before.roles if role not in after.roles]

            if added_roles or removed_roles:
                moderator = "غير معروف"
                try:
                    async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                        if entry.target.id == after.id:
                            moderator = entry.user.mention
                            break
                except:
                    pass
                
                embed = discord.Embed(title="🎭 تحديث رتب عضو", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
                embed.set_author(name=f"{after}", icon_url=after.display_avatar.url)
                embed.add_field(name="بواسطة", value=moderator, inline=True)
                if added_roles:
                    embed.add_field(name="رتب مضافة", value=" ".join([role.mention for role in added_roles]), inline=False)
                if removed_roles:
                    embed.add_field(name="رتب مزالة", value=" ".join([role.mention for role in removed_roles]), inline=False)
                await log_channel.send(embed=embed)

        # Nickname Change Check
        if before.display_name != after.display_name:
            log_channel = await self.get_channel(after.guild, "server_log_id")
            if log_channel:
                embed = discord.Embed(title="🏷️ تغيير النيك نيم", color=discord.Color.light_grey(), timestamp=discord.utils.utcnow())
                embed.set_author(name=f"{after}", icon_url=after.display_avatar.url)
                embed.add_field(name="قبل", value=before.display_name, inline=True)
                embed.add_field(name="بعد", value=after.display_name, inline=True)
                await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        voice_log = await self.get_channel(member.guild, "voice_log_id")
        mod_log = await self.get_channel(member.guild, "mod_log_id")

        if not voice_log and not mod_log: return

        # 1. Join / Leave / Move
        if before.channel != after.channel:
            if before.channel is None: # Join
                embed = discord.Embed(title="🔊 دخول روم صوتي", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                embed.set_author(name=f"{member}", icon_url=member.display_avatar.url)
                embed.add_field(name="الروم", value=after.channel.mention, inline=True)
                if voice_log: await voice_log.send(embed=embed)
            elif after.channel is None: # Leave or Disconnect
                # Check for Disconnect (Kick from voice)
                moderator = None
                try:
                    async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_disconnect):
                        if entry.target.id == member.id and (discord.utils.utcnow() - entry.created_at).total_seconds() < 5:
                            moderator = entry.user
                            break
                except: pass

                if moderator and mod_log:
                    embed = discord.Embed(title="🚫 طرد من الروم الصوتي", color=discord.Color.red(), timestamp=discord.utils.utcnow())
                    embed.set_author(name=f"{member}", icon_url=member.display_avatar.url)
                    embed.add_field(name="بواسطة", value=moderator.mention, inline=True)
                    embed.add_field(name="الروم كان", value=before.channel.mention, inline=True)
                    await mod_log.send(embed=embed)
                elif voice_log:
                    embed = discord.Embed(title="🔻 خروج من روم صوتي", color=discord.Color.red(), timestamp=discord.utils.utcnow())
                    embed.set_author(name=f"{member}", icon_url=member.display_avatar.url)
                    embed.add_field(name="الروم", value=before.channel.mention, inline=True)
                    await voice_log.send(embed=embed)
            else: # Move
                moderator = None
                try:
                    async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_move):
                        if (discord.utils.utcnow() - entry.created_at).total_seconds() < 5:
                            moderator = entry.user
                            break
                except: pass

                if voice_log:
                    embed = discord.Embed(title="🔄 سحب / انتقال", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
                    embed.set_author(name=f"{member}", icon_url=member.display_avatar.url)
                    if moderator:
                        embed.add_field(name="بواسطة", value=moderator.mention, inline=False)
                    embed.add_field(name="من", value=before.channel.mention, inline=True)
                    embed.add_field(name="إلى", value=after.channel.mention, inline=True)
                    await voice_log.send(embed=embed)

        # 2. Server Mute / Deafen
        if (before.mute != after.mute) or (before.deaf != after.deaf):
            if mod_log:
                action = ""
                if before.mute != after.mute:
                    action = "إغلاق المايك (Mute)" if after.mute else "فتح المايك (Unmute)"
                else:
                    action = "إغلاق السماعة (Deafen)" if after.deaf else "فتح السماعة (Undeafen)"
                
                moderator = "غير معروف"
                try:
                    async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                        if entry.target.id == member.id and (discord.utils.utcnow() - entry.created_at).total_seconds() < 5:
                            moderator = entry.user.mention
                            break
                except: pass

                embed = discord.Embed(title=f"🎙️ تحديث حالة صوتية", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
                embed.set_author(name=f"{member}", icon_url=member.display_avatar.url)
                embed.add_field(name="الإجراء", value=action, inline=True)
                embed.add_field(name="بواسطة", value=moderator, inline=True)
                await mod_log.send(embed=embed)

        # 3. Private / Self Mute/Deafen (Optional log to room_log)
        if (before.self_mute != after.self_mute) or (before.self_deaf != after.self_deaf):
             if voice_log:
                status = "ميوت خاص" if after.self_mute else "إزالة ميوت خاص"
                if before.self_deaf != after.self_deaf:
                    status = "ديفن خاص" if after.self_deaf else "إزالة ديفن خاص"
                
                embed = discord.Embed(description=f"👤 {member.mention} قام بـ **{status}**.", color=discord.Color.light_grey(), timestamp=discord.utils.utcnow())
                await voice_log.send(embed=embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        if not messages: return
        guild = messages[0].guild
        log_channel = await self.get_channel(guild, "msg_log_id")
        if not log_channel: return

        embed = discord.Embed(title="🗑️ حذف رسائل بالجملة (Bulk)", color=discord.Color.dark_red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="القناة", value=messages[0].channel.mention, inline=True)
        embed.add_field(name="العدد", value=len(messages), inline=True)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        log_channel = await self.get_channel(after, "server_log_id")
        if not log_channel: return

        embed = discord.Embed(title="⚙️ تحديث إعدادات السيرفر", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
        
        changes = False
        if before.name != after.name:
            embed.add_field(name="تغيير الاسم", value=f"قبل: {before.name}\nبعد: {after.name}", inline=False)
            changes = True
        if before.icon != after.icon:
            embed.add_field(name="تغيير الأيقونة", value="تم تحديث أيقونة السيرفر", inline=False)
            changes = True
            
        if changes:
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        log_channel = await self.get_channel(member.guild, "server_log_id")
        if not log_channel: return

        embed = discord.Embed(title="📥 دخول عضو", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.set_author(name=f"{member}", icon_url=member.display_avatar.url)
        embed.add_field(name="عمر الحساب", value=discord.utils.format_dt(member.created_at, style='R'), inline=True)
        embed.set_footer(text=f"ID: {member.id} | عضو رقم {member.guild.member_count}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        # Check for Kick
        log_channel_mod = await self.get_channel(member.guild, "mod_log_id")
        if log_channel_mod:
            try:
                async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                    if entry.target.id == member.id and (discord.utils.utcnow() - entry.created_at).total_seconds() < 10:
                        embed = discord.Embed(title="👢 تم طرد عضو", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
                        embed.set_author(name=f"{member}", icon_url=member.display_avatar.url)
                        embed.add_field(name="بواسطة", value=entry.user.mention, inline=True)
                        embed.add_field(name="السبب", value=entry.reason or "غير محدد", inline=True)
                        embed.set_footer(text=f"ID: {member.id}")
                        await log_channel_mod.send(embed=embed)
                        break
            except:
                pass

        log_channel = await self.get_channel(member.guild, "server_log_id")
        if not log_channel: return

        embed = discord.Embed(title="📤 خروج عضو", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.set_author(name=f"{member}", icon_url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id} | المتبقي {member.guild.member_count}")
        await log_channel.send(embed=embed)

    # --- Role Events ---
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        log_channel = await self.get_channel(role.guild, "role_log_id")
        if not log_channel: return

        moderator = "غير معروف"
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
                if entry.target.id == role.id:
                    moderator = entry.user.mention
                    break
        except:
            pass

        embed = discord.Embed(title="🆕 إنشاء رتبة", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="الرتبة", value=role.mention, inline=True)
        embed.add_field(name="بواسطة", value=moderator, inline=True)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        log_channel = await self.get_channel(role.guild, "role_log_id")
        if not log_channel: return

        moderator = "غير معروف"
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                if entry.target.id == role.id:
                    moderator = entry.user.mention
                    break
        except:
            pass

        embed = discord.Embed(title="🔥 حذف رتبة", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="اسم الرتبة", value=role.name, inline=True)
        embed.add_field(name="بواسطة", value=moderator, inline=True)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        log_channel = await self.get_channel(after.guild, "role_log_id")
        if not log_channel: return

        embed = discord.Embed(title="♻️ تحديث رتبة", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
        embed.add_field(name="الرتبة", value=after.mention, inline=False)
        
        changes = False
        if before.name != after.name:
            embed.add_field(name="تغيير الاسم", value=f"قبل: {before.name}\nبعد: {after.name}", inline=False)
            changes = True
        if before.color != after.color:
            embed.add_field(name="تغيير اللون", value=f"قبل: {before.color}\nبعد: {after.color}", inline=False)
            changes = True
            
        if changes:
            await log_channel.send(embed=embed)

        # Role Permissions Change
        if before.permissions != after.permissions:
            embed = discord.Embed(title="🛡️ تحديث صلاحيات رتبة", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
            embed.add_field(name="الرتبة", value=after.mention)
            await log_channel.send(embed=embed)

    # --- Channel Events ---
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        log_channel = await self.get_channel(channel.guild, "room_log_id")
        if not log_channel: return

        moderator = "غير معروف"
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
                if entry.target.id == channel.id:
                    moderator = entry.user.mention
                    break
        except:
            pass

        embed = discord.Embed(title="📂 إنشاء قناة", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="القناة", value=channel.mention, inline=True)
        embed.add_field(name="النوع", value=str(channel.type), inline=True)
        embed.add_field(name="بواسطة", value=moderator, inline=True)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        log_channel = await self.get_channel(channel.guild, "room_log_id")
        if not log_channel: return

        moderator = "غير معروف"
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id:
                    moderator = entry.user.mention
                    break
        except:
            pass

        embed = discord.Embed(title="💥 حذف قناة", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="اسم القناة", value=channel.name, inline=True)
        embed.add_field(name="بواسطة", value=moderator, inline=True)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        log_channel = await self.get_channel(after.guild, "room_log_id")
        if not log_channel: return

        embed = discord.Embed(title="⚙️ تحديث قناة", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
        embed.add_field(name="القناة", value=after.mention, inline=False)
        
        changes = False
        if before.name != after.name:
            embed.add_field(name="تغيير الاسم", value=f"قبل: {before.name}\nبعد: {after.name}", inline=False)
            changes = True
        if before.category != after.category:
            embed.add_field(name="تغيير التصنيف", value=f"قبل: {before.category}\nبعد: {after.category}", inline=False)
            changes = True
            
        if changes:
            await log_channel.send(embed=embed)

    # --- Moderation ---
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        log_channel = await self.get_channel(guild, "mod_log_id")
        if not log_channel: return

        moderator = "غير معروف"
        reason = "غير محدد"
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    moderator = entry.user.mention
                    reason = entry.reason or "غير محدد"
                    break
        except:
            pass

        embed = discord.Embed(title="🔨 تم حظر عضو (BAN)", color=discord.Color.dark_red(), timestamp=discord.utils.utcnow())
        embed.set_author(name=f"{user}", icon_url=user.display_avatar.url if user.display_avatar else None)
        embed.add_field(name="بواسطة", value=moderator, inline=True)
        embed.add_field(name="السبب", value=reason, inline=True)
        embed.set_footer(text=f"ID: {user.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        log_channel = await self.get_channel(guild, "mod_log_id")
        if not log_channel: return

        moderator = "غير معروف"
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.unban):
                if entry.target.id == user.id:
                    moderator = entry.user.mention
                    break
        except:
            pass

        embed = discord.Embed(title="🔓 تم فك حظر عضو", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
        embed.set_author(name=f"{user}", icon_url=user.display_avatar.url if user.display_avatar else None)
        embed.add_field(name="بواسطة", value=moderator, inline=True)
        embed.set_footer(text=f"ID: {user.id}")
        await log_channel.send(embed=embed)

    # --- New Detailed Events ---
    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        log_channel = await self.get_channel(guild, "server_log_id")
        if not log_channel: return

        if len(before) < len(after): # Added
            new_emoji = [e for e in after if e not in before][0]
            embed = discord.Embed(title="🆕 إضافة إيموجي", color=discord.Color.green(), timestamp=discord.utils.utcnow())
            embed.set_thumbnail(url=new_emoji.url)
            embed.add_field(name="الاسم", value=new_emoji.name)
            await log_channel.send(embed=embed)
        elif len(before) > len(after): # Removed
            old_emoji = [e for e in before if e not in after][0]
            embed = discord.Embed(title="🗑️ حذف إيموجي", color=discord.Color.red(), timestamp=discord.utils.utcnow())
            embed.set_thumbnail(url=old_emoji.url)
            embed.add_field(name="الاسم", value=old_emoji.name)
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        log_channel = await self.get_channel(invite.guild, "server_log_id")
        if not log_channel: return

        embed = discord.Embed(title="✉️ إنشاء رابط دعوة", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
        embed.add_field(name="الرابط", value=invite.url)
        embed.add_field(name="بواسطة", value=invite.inviter.mention)
        embed.add_field(name="الروم", value=invite.channel.mention)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        log_channel = await self.get_channel(invite.guild, "server_log_id")
        if not log_channel: return

        embed = discord.Embed(title="🗑️ حذف رابط دعوة", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
        embed.add_field(name="الرابط", value=invite.url)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        log_channel = await self.get_channel(channel.guild, "server_log_id")
        if not log_channel: return

        embed = discord.Embed(title="⚓ تحديث Webhooks", color=discord.Color.purple(), timestamp=discord.utils.utcnow())
        embed.add_field(name="القناة", value=channel.mention)
        await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Logging(bot))
