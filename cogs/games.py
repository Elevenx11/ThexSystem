import discord
from discord.ext import commands
import random
import asyncio
import database

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='rps', help='لعبة حجرة ورقة مقص')
    async def rps(self, ctx, choice: str):
        choices = ['حجرة', 'ورقة', 'مقص']
        bot_choice = random.choice(choices)
        
        user_choice = choice.lower()
        if user_choice not in choices:
            await ctx.send(f"❌ اختيار خاطئ! يرجى اختيار: {', '.join(choices)}")
            return

        result = ""
        if user_choice == bot_choice:
            result = "تعادل! 🤝"
        elif (user_choice == 'حجرة' and bot_choice == 'مقص') or \
             (user_choice == 'ورقة' and bot_choice == 'حجرة') or \
             (user_choice == 'مقص' and bot_choice == 'ورقة'):
            result = "أنت فزت! 🎉"
        else:
            result = "أنا فزت! 🤖"

        embed = discord.Embed(title="حجرة ورقة مقص", color=0xf1c40f)
        embed.add_field(name="اختيارك", value=user_choice, inline=True)
        embed.add_field(name="اختياري", value=bot_choice, inline=True)
        embed.add_field(name="النتيجة", value=result, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='coin', aliases=['flip'], help='رمي عملة')
    async def coin(self, ctx):
        result = random.choice(['وجه', 'كتابة'])
        await ctx.send(f'🪙 النتيجة هي: **{result}**')

    @commands.hybrid_command(name='roll', help='رمي نرد (رقم من 1 إلى 100)')
    async def roll(self, ctx):
        result = random.randint(1, 100)
        await ctx.send(f'🎲 الرقم: **{result}**')

    @commands.hybrid_command(name='math', help='لعبة رياضيات سريعة')
    async def math_game(self, ctx):
        num1 = random.randint(1, 20)
        num2 = random.randint(1, 20)
        op = random.choice(['+', '-', '*'])
        
        if op == '+': ans = num1 + num2
        elif op == '-': ans = num1 - num2
        else: ans = num1 * num2

        await ctx.send(f'🔢 حل المسألة: **{num1} {op} {num2}**؟ (لديك 10 ثواني)')

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=10.0)
            if int(msg.content) == ans:
                await ctx.send('✅ إجابة صحيحة! بطل!')
            else:
                await ctx.send(f'❌ إجابة خاطئة. الجواب الصحيح هو {ans}')
        except asyncio.TimeoutError:
            await ctx.send(f'⏰ انتهى الوقت! الجواب هو {ans}')

    @commands.hybrid_command(name='slots', help='لعبة السلوت (القمار البريء)')
    async def slots(self, ctx):
        emojis = "🍎🍊🍇🍒💎"
        result = [random.choice(emojis) for _ in range(3)]
        
        slot_machine = f"**[ {' '.join(result)} ]**"
        
        if result[0] == result[1] == result[2]:
            await ctx.send(f"{slot_machine}\n🎉 مبروك! لقد فزت!")
        else:
            await ctx.send(f"{slot_machine}\n❌ حظاً أوفر في المرة القادمة.")

    @commands.hybrid_command(name='roulette', help='لعبة الروليت الجماعية (20 مقعد)')
    async def roulette(self, ctx):
        embed = discord.Embed(
            title="🎮 روليت الجماعية",
            description="اضغط على الزر أدناه لاختيار مقعدك!\nتحتاج اللعبة إلى 3 أشخاص على الأقل للبدء.\nسيغلق التسجيل بعد 60 ثانية.",
            color=discord.Color.purple()
        )
        view = RouletteLobbyView(ctx, self.bot)
        await ctx.send(embed=embed, view=view)

class RouletteSeatButton(discord.ui.Button):
    def __init__(self, seat_number):
        super().__init__(style=discord.ButtonStyle.secondary, label=str(seat_number), row=(seat_number-1)//5)
        self.seat_number = seat_number

    async def callback(self, interaction: discord.Interaction):
        view: RouletteLobbyView = self.view
        if interaction.user in view.players.values():
            return await interaction.response.send_message("أنت مسجل بالفعل في مقعد آخر!", ephemeral=True)
            
        if self.seat_number in view.players:
            return await interaction.response.send_message("هذا المقعد محجوز بالفعل!", ephemeral=True)

        view.players[self.seat_number] = interaction.user
        self.label = interaction.user.display_name[:10] # اختصار الاسم ليتناسب مع الزر
        self.style = discord.ButtonStyle.green
        self.disabled = True
        
        await interaction.response.edit_message(view=view)

class RouletteLobbyView(discord.ui.View):
    def __init__(self, ctx, bot):
        super().__init__(timeout=65)
        self.ctx = ctx
        self.bot = bot
        self.players = {} # {seat_number: member}
        self.seats_count = 20
        for i in range(1, self.seats_count + 1):
            self.add_item(RouletteSeatButton(i))

    async def on_timeout(self):
        if len(self.players) < 3:
            return await self.ctx.send("❌ تم إلغاء اللعبة لعدم اكتمال الحد الأدنى من اللاعبين (3 لاعبين).")
        
        await self.ctx.send("🏁 انتهى وقت التسجيل! تبدأ اللعبة الآن...")
        await self.run_game()

    async def run_game(self):
        active_players = list(self.players.values())
        
        while len(active_players) > 1:
            picker = random.choice(active_players)
            others = [p for p in active_players if p != picker]
            
            embed = discord.Embed(
                title="🔄 دور الروليت يدور...",
                description=f"الروليت وقفت عند: {picker.mention}\n\nيجب عليه الآن اختيار شخص ليخرجه من اللعبة!",
                color=discord.Color.orange()
            )
            
            view = RouletteEliminateView(picker, others)
            msg = await self.ctx.send(content=picker.mention, embed=embed, view=view)
            
            # انتظار اختيار الشخص
            timed_out = await view.wait()
            
            if timed_out or not view.selected_target:
                # إذا تأخر نختار شخص عشوائي يخرج
                target = random.choice(others)
                await self.ctx.send(f"⏰ تأخر {picker.mention} في الاختيار، تم إخراج {target.mention} عشوائياً!")
            else:
                target = view.selected_target
                await self.ctx.send(f"🔥 {picker.mention} اختار إخراج {target.mention}!")
            
            active_players.remove(target)
            await asyncio.sleep(2)

        winner = active_players[0]
        final_embed = discord.Embed(
            title="🏆 نهاية اللعبة",
            description=f"مبروك للفائز الوحيد في الروليت: {winner.mention}! 🎉",
            color=discord.Color.gold()
        )
        await self.ctx.send(embed=final_embed)

class RouletteEliminateView(discord.ui.View):
    def __init__(self, picker, others):
        super().__init__(timeout=30)
        self.picker = picker
        self.others = others
        self.selected_target = None
        
        # إضافة قائمة اختيار للأهداف
        options = [
            discord.SelectOption(label=p.display_name, value=str(p.id)) 
            for p in others[:25] # ديسكورد يسمح بـ 25 خيار كحد أقصى
        ]
        
        select = discord.ui.Select(placeholder="اختر الشخص الذي تريد إخراجه...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.picker:
            return await interaction.response.send_message("هذا المنيو ليس لك!", ephemeral=True)
            
        target_id = int(interaction.data['values'][0])
        self.selected_target = next(p for p in self.others if p.id == target_id)
        
        # تعطيل القائمة بعد الاختيار
        for child in self.children:
            child.disabled = True
            
        await interaction.response.edit_message(view=self)
        self.stop()

    @commands.hybrid_command(name='fast', help='أسرع شخص يكتب الكلمة')
    async def fast(self, ctx):
        words = ["مستشفى", "كمبيوتر", "مدرسة", "سيارة", "طائرة", "برمجة", "تكنولوجيا", "امارات", "سعودية", "كويت"]
        target = random.choice(words)
        
        embed = discord.Embed(title="أسرع شخص يكتب الكلمة", description=f"اكتب الكلمة التالية بأسرع ما يمكن:\n\n**{target}**", color=discord.Color.gold())
        await ctx.send(embed=embed)

        def check(m):
            return m.channel == ctx.channel and m.content == target and not m.author.bot

        start_time = asyncio.get_event_loop().time()
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=15.0)
            end_time = asyncio.get_event_loop().time()
            time_taken = round(end_time - start_time, 2)
            await ctx.send(f"🎉 كفو {msg.author.mention}! كتبت الكلمة في {time_taken} ثانية.")
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ انتهى الوقت! لم يكتب أحد الكلمة `{target}`.")

    @commands.hybrid_command(name='guess', help='لعبة تخمين الرقم (مافيا الأرقام)')
    async def guess(self, ctx):
        number = random.randint(1, 50)
        await ctx.send("🕵️ لقد اخترت رقماً بين 1 و 50. لديكم 30 ثانية لتخمينه!")

        def check(m):
            return m.channel == ctx.channel and m.content.isdigit() and not m.author.bot

        while True:
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                guess = int(msg.content)
                
                if guess == number:
                    await ctx.send(f"🎯 مبروك {msg.author.mention}! الرقم الصحيح هو {number}.")
                    break
                elif guess < number:
                    await ctx.send(f"⬆️ أكبر من {guess}!")
                else:
                    await ctx.send(f"⬇️ أصغر من {guess}!")
            except asyncio.TimeoutError:
                await ctx.send(f"⏰ انتهى الوقت! لم يحزر أحد. الرقم كان {number}.")
                break

    @commands.hybrid_command(name='xo', help='لعبة إكس أو (Tic-Tac-Toe)')
    async def xo(self, ctx, member: discord.Member):
        if member == ctx.author:
            return await ctx.send("❌ لا يمكنك اللعب ضد نفسك.")
        if member.bot:
            return await ctx.send("❌ لا يمكنك اللعب ضد بوت.")
            
        view = TIC_TAC_TOE_View(ctx.author, member)
        await ctx.send(f"🎮 {ctx.author.mention} ضد {member.mention}! يبدأ {ctx.author.mention} (❌)", view=view)

class TIC_TAC_TOE_Button(discord.ui.Button):
    def __init__(self, x, y):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TIC_TAC_TOE_View = self.view
        if interaction.user != view.current_player:
            return await interaction.response.send_message("انتظر دورك!", ephemeral=True)

        if view.board[self.y][self.x] != 0:
            return await interaction.response.send_message("هذا المربع مشغول!", ephemeral=True)

        char = "❌" if view.current_player == view.p1 else "⭕"
        view.board[self.y][self.x] = 1 if view.current_player == view.p1 else 2
        self.label = char
        self.style = discord.ButtonStyle.danger if char == "❌" else discord.ButtonStyle.success
        self.disabled = True

        winner = view.check_winner()
        if winner:
            for child in view.children:
                child.disabled = True
            if winner == "draw":
                content = "🤝 تعادل!"
            else:
                content = f"🎉 الفائز هو {view.current_player.mention}!"
            await interaction.response.edit_message(content=content, view=view)
            view.stop()
        else:
            view.current_player = view.p2 if view.current_player == view.p1 else view.p1
            await interaction.response.edit_message(content=f"دور {view.current_player.mention} ({'❌' if view.current_player == view.p1 else '⭕'})", view=view)

class TIC_TAC_TOE_View(discord.ui.View):
    def __init__(self, p1, p2):
        super().__init__(timeout=60)
        self.p1 = p1
        self.p2 = p2
        self.current_player = p1
        self.board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        for y in range(3):
            for x in range(3):
                self.add_item(TIC_TAC_TOE_Button(x, y))

    def check_winner(self):
        # Rows, Cols, Diagonals
        lines = []
        for i in range(3):
            lines.append(self.board[i]) # rows
            lines.append([self.board[0][i], self.board[1][i], self.board[2][i]]) # cols
        lines.append([self.board[0][0], self.board[1][1], self.board[2][2]]) # diag 1
        lines.append([self.board[0][2], self.board[1][1], self.board[2][0]]) # diag 2

        for line in lines:
            if line[0] != 0 and line[0] == line[1] == line[2]:
                return line[0]

        if all(cell != 0 for row in self.board for cell in row):
            return "draw"
        return None

async def setup(bot):
    await bot.add_cog(Games(bot))
