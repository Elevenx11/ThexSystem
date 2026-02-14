import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

# إعدادات البوت
TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('PREFIX', '!')

# تفعيل الـ Intents (مهم جداً للميزات الجديدة)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=PREFIX, intents=intents, help_command=None)

    async def setup_hook(self):
        # تحميل ملفات الـ Cogs (الإضافات)
        import database
        await database.init_db()
        
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded extension: {filename}')
        
        # مزامنة أوامر السلاش
        await self.tree.sync() 

    async def on_ready(self):
        print(f'{self.user} is connected and ready!')
        print(f'ID: {self.user.id}')
        await self.change_presence(activity=discord.Game(name=f"{PREFIX}help | Pro Server Bot"))

    async def on_message(self, message):
        if message.author.bot or not message.guild or not message.content:
            return
            
        prefix = await self.get_prefix(message)
        if isinstance(prefix, list): prefix = prefix[0]
        
        content = message.content
        parts = content.split()
        if not parts: return
        
        first_word = parts[0]
        alias_to_check = None
        
        # Check if it starts with prefix (e.g., !kick)
        if content.startswith(prefix):
            alias_to_check = first_word[len(prefix):]
        else:
            # Check if it's a plain word alias (e.g., طرد)
            alias_to_check = first_word
            
        if alias_to_check:
            import database
            aliases = await database.get_aliases(message.guild.id)
            for row in aliases:
                if row['alias'] == alias_to_check:
                    actual_command = row['command_name']
                    # Reconstruct message with the real command and prefix
                    message.content = prefix + actual_command + content[len(first_word):]
                    break
        
        await self.process_commands(message)

bot = MyBot()

@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="🤖 نظام المساعدة المتكامل",
        description=f"مرحباً بك! أنا بوتك الخاص والمطور لسيرفركم.\nبادئة البوت البرمجية هي: `{PREFIX}`",
        color=discord.Color.from_rgb(47, 49, 54)
    )
    
    embed.add_field(
        name="🛡️ الإدارة (Moderation)", 
        value="`kick`, `ban`, `unban`, `purge`, `mute`, `unmute`, `lock`, `unlock`, `say`"
    )
    
    embed.add_field(
        name="💰 الاقتصاد (Economy)", 
        value="`credits`, `daily`, `give`"
    )
    
    # embed.add_field(
    #     name="🏆 التفاعل والمستوى (Leveling)", 
    #     value="`rank`, `top`"
    # )
    
    embed.add_field(
        name="🎮 الألعاب (Games)", 
        value="`ping`, `rps`, `coin`, `roll`, `math`"
    )
    
    embed.add_field(
        name="ℹ️ عام (General)", 
        value="`user`, `server`, `avatar`"
    )
    
    embed.set_footer(text="للحصول على المساعدة في أمر معين، تواصل مع الإدارة.", icon_url=bot.user.display_avatar.url)
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    
    await ctx.send(embed=embed)

if __name__ == '__main__':
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in .env file.")
    else:
        bot.run(TOKEN)
