import discord
from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.hybrid_command(name='avatar', help='عرض صورة البروفايل')
    async def avatar(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        embed = discord.Embed(title=f"Avatar of {member.name}", color=member.color)
        embed.set_image(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='user', aliases=['info', 'whois'], help='معلومات عن العضو')
    async def user_info(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        
        embed = discord.Embed(title=f'User Info - {member.name}', color=member.color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name='ID', value=member.id, inline=True)
        embed.add_field(name='Name', value=member.display_name, inline=True)
        embed.add_field(name='Joined At', value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name='Created At', value=member.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name=f'Roles ({len(roles)})', value=' '.join(roles) if roles else "No roles", inline=False)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='server', help='معلومات عن السيرفر')
    async def server_info(self, ctx):
        guild = ctx.guild
        embed = discord.Embed(title=f'{guild.name} Info', description='معلومات عامة', color=discord.Color.blue())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(name='Owner', value=guild.owner.mention, inline=True)
        embed.add_field(name='Members', value=guild.member_count, inline=True)
        embed.add_field(name='Channels', value=len(guild.channels), inline=True)
        embed.add_field(name='Roles', value=len(guild.roles), inline=True)
        embed.set_footer(text=f'ID: {guild.id} | Created: {guild.created_at.strftime("%Y-%m-%d")}')
        
        await ctx.send(embed=embed)
        
    @commands.hybrid_command(name='say', help='يكرر البوت كلامك')
    @commands.has_permissions(manage_messages=True)
    async def say(self, ctx, *, message: str):
        if ctx.interaction:
            await ctx.send(message)
        else:
            await ctx.message.delete()
            await ctx.send(message)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
            
        if message.content.strip() == "-خط":
            try:
                await message.delete()
            except:
                pass
            await message.channel.send("https://cdn.discordapp.com/attachments/1455710696905113651/1469733008344088907/InShot_20260206_021756302.png?ex=6988bb07&is=69876987&hm=3327b6f2c2df030475909f5d8cf8ffa79db1053011c287e838e584a25f02858b")

async def setup(bot):
    await bot.add_cog(General(bot))
