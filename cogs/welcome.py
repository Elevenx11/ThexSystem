import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
import aiohttp

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def create_welcome_card(self, member):
        # Load background
        try:
            background = Image.open("welcome.png").convert("RGBA")
        except:
            # Fallback if image not found
            background = Image.new("RGBA", (1024, 500), (47, 49, 54, 255))

        # Size of background
        width, height = background.size

        # Load avatar
        avatar_url = member.display_avatar.url
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as resp:
                if resp.status == 200:
                    avatar_bytes = await resp.read()
                    avatar_image = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
                else:
                    avatar_image = Image.new("RGBA", (200, 200), (255, 255, 255, 255))

        # Resize avatar and make it circular
        avatar_size = 180
        avatar_image = avatar_image.resize((avatar_size, avatar_size))
        
        # Create mask for circular avatar
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, avatar_size, avatar_size), fill=255)
        
        output_avatar = ImageOps.fit(avatar_image, mask.size, centering=(0.5, 0.5))
        output_avatar.putalpha(mask)

        # Paste avatar onto background (centered)
        avatar_x = (width - avatar_size) // 2
        avatar_y = (height - avatar_size) // 2 + 50 # Slightly below center
        background.paste(output_avatar, (avatar_x, avatar_y), output_avatar)

        # Draw text
        draw = ImageDraw.Draw(background)
        
        # Try to find a font
        try:
            font_title = ImageFont.truetype("arial.ttf", 60)
            font_subtitle = ImageFont.truetype("arial.ttf", 40)
        except:
            font_title = ImageFont.load_default()
            font_subtitle = ImageFont.load_default()

        # Welcome text is already in background, let's add username
        name_text = f"{member.name}"
        member_text = f"Member #{member.guild.member_count}"
        
        # Calculate text position
        name_bbox = draw.textbbox((0, 0), name_text, font=font_title)
        name_w = name_bbox[2] - name_bbox[0]
        name_x = (width - name_w) // 2
        name_y = avatar_y + avatar_size + 20
        
        member_bbox = draw.textbbox((0, 0), member_text, font=font_subtitle)
        member_w = member_bbox[2] - member_bbox[0]
        member_x = (width - member_w) // 2
        member_y = name_y + 70

        # Draw shadow then text
        draw.text((name_x+2, name_y+2), name_text, font=font_title, fill=(0, 0, 0, 150))
        draw.text((name_x, name_y), name_text, font=font_title, fill=(255, 255, 255, 255))
        
        draw.text((member_x+2, member_y+2), member_text, font=font_subtitle, fill=(0, 0, 0, 150))
        draw.text((member_x, member_y), member_text, font=font_subtitle, fill=(200, 200, 200, 255))

        # Save to buffer
        buffer = io.BytesIO()
        background.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = discord.utils.get(member.guild.text_channels, name="welcome") or \
                  discord.utils.get(member.guild.text_channels, name="general") or \
                  discord.utils.get(member.guild.text_channels, name="ترحيب")
        
        if channel:
            buffer = await self.create_welcome_card(member)
            file = discord.File(fp=buffer, filename="welcome.png")
            
            embed = discord.Embed(
                title=f"أهلاً بك في {member.guild.name}!",
                description=f"مرحباً بك {member.mention} في سيرفرنا المتواضع. نتمنى لك وقتاً ممتعاً!",
                color=0x9b59b6
            )
            embed.set_image(url="attachment://welcome.png")
            embed.set_footer(text=f"ID: {member.id}")
            
            await channel.send(embed=embed, file=file)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
