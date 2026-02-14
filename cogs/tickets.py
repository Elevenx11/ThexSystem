import discord
from discord.ext import commands
from discord import app_commands
import database
import datetime
import io
import os

class TicketActionsView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="استلام التذكرة", style=discord.ButtonStyle.green, custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            return
        settings = await database.get_ticket_settings(interaction.guild.id)
        if not settings:
            return await interaction.followup.send("لم يتم العثور على إعدادات التذاكر.", ephemeral=True)
        
        staff_role_id = settings['staff_role_id']
        staff_app_role_id = settings['staff_app_role_id']
        staff_role = interaction.guild.get_role(staff_role_id)
        staff_app_role = interaction.guild.get_role(staff_app_role_id)
        
        is_staff = (staff_role in interaction.user.roles) or (staff_app_role in interaction.user.roles if staff_app_role else False)
        if not is_staff and not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("عذراً، هذا الزر مخصص للطاقم الإداري فقط.", ephemeral=True)
        
        embed = interaction.message.embeds[0]
        # التحقق مما إذا كانت التذكرة مستلمة بالفعل
        for field in embed.fields:
            if field.name == "تم الاستلام بواسطة":
                return await interaction.followup.send("هذه التذكرة مستلمة بالفعل.", ephemeral=True)

        embed.add_field(name="تم الاستلام بواسطة", value=interaction.user.mention, inline=False)
        button.disabled = True
        button.label = "تم الاستلام"
        
        # منع باقي الإدارة من رؤية التذكرة بشكل قطعي
        overwrites = interaction.channel.overwrites
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=False)
        if staff_app_role:
            overwrites[staff_app_role] = discord.PermissionOverwrite(read_messages=False)
        
        # إضافة صلاحية الشخص الذي استلم التذكرة فقط
        overwrites[interaction.user] = discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, manage_channels=False)
        
        await interaction.channel.edit(overwrites=overwrites)
        await interaction.edit_original_response(embed=embed, view=self)
        await interaction.channel.send(f"✅ تم استلام التذكرة بواسطة {interaction.user.mention}\n(هذه التذكرة الآن مخفية عن باقي الإدارة)")

    @discord.ui.button(label="إضافة عضو", style=discord.ButtonStyle.secondary, custom_id="add_member")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await database.get_ticket_settings(interaction.guild.id)
        if not settings:
            return await interaction.response.send_message("لم يتم العثور على إعدادات التذاكر.", ephemeral=True)
        
        staff_role_id = settings['staff_role_id']
        staff_app_role_id = settings['staff_app_role_id']
        staff_role = interaction.guild.get_role(staff_role_id)
        staff_app_role = interaction.guild.get_role(staff_app_role_id)
        
        is_staff = (staff_role in interaction.user.roles) or (staff_app_role in interaction.user.roles if staff_app_role else False)
        if not is_staff and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("عذراً، هذا الزر مخصص للطاقم الإداري فقط.", ephemeral=True)
            
        await interaction.response.send_message("يرجى اختيار العضو الذي تريد إضافته لهذه التذكرة:", view=AddMemberSelectView(), ephemeral=True)

    @discord.ui.button(label="إغلاق التذكرة", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        content = "هل أنت متأكد من إغلاق التذكرة؟"
        view = ConfirmCloseView(self.bot)
        if interaction.response.is_done():
            await interaction.followup.send(content, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(content, view=view, ephemeral=True)

class AddMemberSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="اختر العضو المراد إضافته...")
    async def select_user(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        user = select.values[0]
        if user.bot:
            return await interaction.response.send_message("لا يمكنك إضافة بوتات.", ephemeral=True)
            
        overwrites = interaction.channel.overwrites
        overwrites[user] = discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True)
        
        await interaction.channel.edit(overwrites=overwrites)
        await interaction.response.send_message(f"✅ تم إضافة {user.mention} إلى التذكرة.")
        await interaction.channel.send(f"🔔 تم إضافة {user.mention} للمشاركة في هذه التذكرة بواسطة {interaction.user.mention}")

class ConfirmCloseView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot

    @discord.ui.button(label="نعم، أغلق", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # Removed the backup processing message as requested

        
        channel = interaction.channel
        messages = []
        async for message in channel.history(limit=None, oldest_first=True):
            time = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            messages.append(f"[{time}] {message.author}: {message.content}")
        
        transcript_content = "\n".join(messages)
        file = discord.File(io.BytesIO(transcript_content.encode('utf-8-sig')), filename=f"transcript-{channel.name}.txt")
        
        settings = await database.get_ticket_settings(interaction.guild.id)
        if settings and settings['logs_channel_id']: # logs_channel_id
            log_channel = interaction.guild.get_channel(settings['logs_channel_id'])
            if log_channel:
                embed = discord.Embed(
                    title="تذكرة مغلقة",
                    description=f"اسم التذكرة: {channel.name}\nأغلقها: {interaction.user.mention}",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.now()
                )
                await log_channel.send(embed=embed, file=file)
        
        # Removed the deletion countdown message as requested

        await discord.utils.sleep_until(datetime.datetime.now() + datetime.timedelta(seconds=5))
        await channel.delete()

class TicketTypeSelect(discord.ui.Select):
    def __init__(self, bot):
        options = [
            discord.SelectOption(label="استفسار", emoji="❓", description="فتح تذكرة استفسار عام", value="inquiry"),
            discord.SelectOption(label="شكوى", emoji="⚠️", description="فتح تذكرة لتقديم شكوى", value="complaint"),
            discord.SelectOption(label="طلب توثيق بنات", emoji="👸", description="فتح تذكرة لتوثيق حسابات البنات", value="girl_verification"),
            discord.SelectOption(label="تقديم ادارة", emoji="👮", description="فتح تذكرة للتقديم على الرتب الإدارية", value="staff_app"),
        ]
        super().__init__(placeholder="اختر نوع التذكرة لفتحها مباشرة...", options=options, custom_id="ticket_type_select_main")
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        # تصفير القائمة فوراً للسماح للمستخدم باختيار نفس النوع مرة أخرى
        try:
            await interaction.response.edit_message(view=TicketOpenView(self.bot))
        except:
            pass

        settings = await database.get_ticket_settings(interaction.guild.id)
        if not settings:
            return await interaction.followup.send("لم يتم إعداد نظام التذاكر في هذا السيرفر.", ephemeral=True)
            
        ticket_type = self.values[0]
        type_labels = {
            "inquiry": "استفسار",
            "complaint": "شكوى",
            "girl_verification": "طلب توثيق بنات",
            "staff_app": "تقديم ادارة"
        }
        
        guild = interaction.guild
        category_id = settings['category_id']
        staff_role_id = settings['staff_role_id']
        staff_app_role_id = settings['staff_app_role_id']
        inquiry_role_id = settings['inquiry_role_id']
        complaint_role_id = settings['complaint_role_id']
        girl_verif_role_id = settings['girl_verif_role_id']
        
        category = guild.get_channel(category_id)
        if not category:
            return await interaction.followup.send("فئة التذاكر المحددة غير موجودة.", ephemeral=True)

        # منع فتح أكثر من تذكرة
        for channel in category.text_channels:
            if channel.topic == str(interaction.user.id):
                return await interaction.followup.send(f"لديك تذكرة مفتوحة بالفعل: {channel.mention}", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }

        staff_role = guild.get_role(staff_role_id)
        staff_app_role = guild.get_role(staff_app_role_id) if staff_app_role_id else None
        inquiry_role = guild.get_role(inquiry_role_id) if inquiry_role_id else None
        complaint_role = guild.get_role(complaint_role_id) if complaint_role_id else None
        girl_verif_role = guild.get_role(girl_verif_role_id) if girl_verif_role_id else None
        
        target_staff_role = None
        
        # منطق تحديد الرتب وحقوق الوصول حسب النوع
        roles_to_hide = [staff_role, staff_app_role, inquiry_role, complaint_role, girl_verif_role]
        
        if ticket_type == "staff_app":
            target_staff_role = staff_app_role
        elif ticket_type == "inquiry":
            target_staff_role = inquiry_role or staff_role
        elif ticket_type == "complaint":
            target_staff_role = complaint_role or staff_role
        elif ticket_type == "girl_verification":
            target_staff_role = girl_verif_role or staff_role
            
        if target_staff_role:
            overwrites[target_staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True)
            # إخفاء التذكرة عن باقي الرتب المتخصصة
            for r in roles_to_hide:
                if r and r != target_staff_role:
                    overwrites[r] = discord.PermissionOverwrite(read_messages=False)
        else:
            # افتراضياً للإدارة العامة
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True)
                target_staff_role = staff_role

        # الحصول على رقم التذكرة الجديد
        ticket_number = await database.get_and_increment_ticket_count(guild.id)
        channel_name = f"ticket--{ticket_number:03d}"

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=str(interaction.user.id),
            reason=f"Ticket {ticket_type} opened by {interaction.user}"
        )

        # إرسال رسالة النجاح في الشات وحذفها بعد 10 ثوانٍ
        success_msg = await interaction.followup.send(f"✅ تم فتح تذكرتك بنجاح: {ticket_channel.mention}", ephemeral=False)
        
        try:
            await success_msg.delete(delay=10)
        except:
            pass

        embed = discord.Embed(
            title=f"تذكرة جديدة: {type_labels[ticket_type]}",
            description=f"مرحباً بك {interaction.user.mention} في نظام الدعم الفني.\n\n**النوع:** {type_labels[ticket_type]}\n**الحالة:** في انتظار استلام الإدارة\n\nيرجى كتابة طلبك بوضوح وسيتم الرد عليك قريباً في حال تم استلام التذكرة من قبل أحد المشرفين.",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        embed.set_footer(text=f"User ID: {interaction.user.id}")
        
        await ticket_channel.send(
            content=f"{interaction.user.mention} {target_staff_role.mention if target_staff_role else ''}",
            embed=embed,
            view=TicketActionsView(self.bot)
        )

class TicketOpenView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(TicketTypeSelect(bot))

# إضافة decorator يدوي لأن discord.py يتطلب تعريف معالج الأخطاء بشكل خاص في الـ Cog
def cog_app_command_error(func):
    return func

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(TicketOpenView(self.bot))
        self.bot.add_view(TicketActionsView(self.bot))

    ticket_group = app_commands.Group(name="ticket", description="إعدادات نظام التذاكر")

    @ticket_group.command(name="setup", description="إعداد نظام التذاكر")
    @app_commands.describe(
        category="الفئة التي ستفتح فيها التذاكر",
        logs="قناة سجلات التذاكر",
        staff_role="الرتبة الإدارية العامة",
        staff_app_role="الرتبة الخاصة بطلبات التقديم",
        inquiry_role="رتبة الاستفسارات",
        complaint_role="رتبة الشكاوى",
        girl_verif_role="رتبة توثيق البنات"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction, 
              category: discord.CategoryChannel, 
              logs: discord.TextChannel, 
              staff_role: discord.Role, 
              staff_app_role: discord.Role,
              inquiry_role: discord.Role = None,
              complaint_role: discord.Role = None,
              girl_verif_role: discord.Role = None):
        
        await database.set_ticket_settings(
            interaction.guild.id, category.id, logs.id, staff_role.id, staff_app_role.id,
            inquiry_role.id if inquiry_role else None,
            complaint_role.id if complaint_role else None,
            girl_verif_role.id if girl_verif_role else None
        )
        
        embed = discord.Embed(
            title="✅ تم الإعداد بنجاح",
            description=(
                f"**الفئة:** {category.mention}\n"
                f"**السجلات:** {logs.mention}\n"
                f"**الإدارة العامة:** {staff_role.mention}\n"
                f"**إدارة التقديم:** {staff_app_role.mention}\n"
                f"**رتبة الاستفسار:** {inquiry_role.mention if inquiry_role else 'غير محدد'}\n"
                f"**رتبة الشكاوى:** {complaint_role.mention if complaint_role else 'غير محدد'}\n"
                f"**رتبة البنات:** {girl_verif_role.mention if girl_verif_role else 'غير محدد'}"
            ),
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @ticket_group.command(name="panel", description="إرسال لوحة فتح التذاكر الاحترافية")
    @app_commands.checks.has_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫 نظام الدعم الفني",
            description="لفتح تذكرة مباشرة، يرجى اختيار القسم المناسب من القائمة المنسدلة أدناه.\n\nسيتم إنشاء قناة خاصة للتحدث مع الطاقم المختص.",
            color=0x2b2d31 # لون ديسكورد الغامق
        )
        embed.set_footer(text="Thex System - Professional Ticket System")
        # لا حاجة لإرسال رسالة "تم إرسال اللوحة" في بعض الأحيان، لكن بما أنه تفاعل سلاش يفضل الرد بشيء
        await interaction.response.send_message("تم إرسال لوحة التذاكر.", ephemeral=True)
        await interaction.channel.send(embed=embed, view=TicketOpenView(self.bot))

    @cog_app_command_error
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            msg = f"❌ عذراً {interaction.user.mention}، هذا الأمر يتطلب صلاحية `Administrator` (مدير سيرفر)."
        else:
            print(f"App Command Error: {error}")
            msg = f"⚠️ حدث خطأ أثناء تنفيذ الأمر: {error}"

        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except:
            # إذا فشل كل شيء (مثلاً التفاعل انتهى وقته تماماً)
            pass

async def setup(bot):
    cog = Tickets(bot)
    await bot.add_cog(cog)
    # ربط معالج الأخطاء بشجرة الأوامر لهذا الـ Cog
    bot.tree.on_error = cog.on_app_command_error
