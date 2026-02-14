import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="broadcast", description="إرسال رسالة برودكاست لكل أعضاء السيرفر في الخاص")
    @app_commands.describe(message="الرسالة التي تريد إرسالها")
    @app_commands.checks.has_permissions(administrator=True)
    async def broadcast(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message("🚀 جارٍ البدء في إرسال البرودكاست... قد يستغرق هذا وقتاً طويلاً حسب عدد الأعضاء.", ephemeral=True)
        
        guild = interaction.guild
        members = guild.members
        success = 0
        failed = 0
        
        for member in members:
            if member.bot:
                continue
            
            try:
                embed = discord.Embed(
                    title=f"رسالة من سيرفر {guild.name}",
                    description=message,
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now() if 'datetime' in globals() else None
                )
                embed.set_footer(text=f"Sent by {interaction.user.display_name}")
                await member.send(embed=embed)
                success += 1
                await asyncio.sleep(1) # تأخير لتجنب الـ Rate Limit
            except:
                failed += 1
                
        await interaction.followup.send(f"✅ انتهى البرودكاست!\n**تم الإرسال بنجاح:** {success}\n**فشل الإرسال (الخاص مغلق):** {failed}", ephemeral=True)

    @app_commands.command(name="add-alias", description="إضافة اختصار لأمر معين")
    @app_commands.describe(command_name="اسم الأمر الأصلي", alias="الاختصار الجديد")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_alias(self, interaction: discord.Interaction, command_name: str, alias: str):
        import database
        # التأكد من وجود الأمر
        cmd = self.bot.get_command(command_name)
        if not cmd:
            return await interaction.response.send_message(f"❌ الأمر `{command_name}` غير موجود.", ephemeral=True)
            
        await database.add_alias(interaction.guild.id, alias, command_name)
        await interaction.response.send_message(f"✅ تم إضافة الاختصار `{alias}` للأمر `{command_name}`.")

    @app_commands.command(name="remove-alias", description="إزالة اختصار لأمر")
    @app_commands.describe(alias="الاختصار المراد حذفه")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_alias(self, interaction: discord.Interaction, alias: str):
        import database
        await database.remove_alias(interaction.guild.id, alias)
        await interaction.response.send_message(f"✅ تم إزالة الاختصار `{alias}`.")

    @app_commands.command(name="sync", description="تحديث قوائم الأوامر في السيرفر")
    @app_commands.checks.has_permissions(administrator=True)
    async def sync(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            # هذه الحركة تجبر ديسكورد على تحديث القوائم في السيرفر الحالي فوراً
            self.bot.tree.copy_global_to(guild=interaction.guild)
            await self.bot.tree.sync(guild=interaction.guild)
            await interaction.followup.send("✅ تم تحديث قائمة الأوامر والخيارات بنجاح! جرب استخدام `/set-log` الآن.")
        except Exception as e:
            await interaction.followup.send(f"❌ فشل التحديث: {e}")

async def setup(bot):
    await bot.add_cog(Admin(bot))
