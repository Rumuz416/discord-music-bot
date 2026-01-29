import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio

# --- AYARLAR ---
TOKEN = "MTQ1ODgyMjA5NzUwNDU2NzQ3OQ.GKA4Ys.5W7fK_ueWWLoURxwXZRTYL3CU8RRoSv1s_HIOI"
YDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': 'True', 'quiet': True, 'default_search': 'ytsearch5'}
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

class MusicManager:
    def __init__(self):
        self.queue = []      # Sıradaki şarkıların linkleri
        self.titles = []     # Sıradaki şarkıların isimleri (Göstermek için)
        self.current_track = None
        self.loop = False

guild_data = {}

def get_data(guild_id):
    if guild_id not in guild_data:
        guild_data[guild_id] = MusicManager()
    return guild_data[guild_id]

# --- ARAMA VE SEÇİM MENÜSÜ ---
class SearchSelectView(discord.ui.View):
    def __init__(self, options, search_query, bot):
        super().__init__(timeout=60)
        self.search_query = search_query
        self.bot = bot
        
        # Seçim Menüsü
        select = discord.ui.Select(placeholder="🎵 Şarkını seç...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        data = get_data(interaction.guild.id)
        url = interaction.data['values'][0]
        
        # Şarkı bilgilerini al
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info['title']

        data.queue.append(url)
        data.titles.append(title)

        if not interaction.guild.voice_client.is_playing() and not interaction.guild.voice_client.is_paused():
            await play_music(interaction)
        else:
            await interaction.followup.send(f"✅ **Sıraya Eklendi:** {title}", ephemeral=True)

    @discord.ui.button(label="🔄 Yeniden Ara", style=discord.ButtonStyle.gray)
    async def re_search(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Beğenmezse aynı sorguyla tekrar arama yapar (veya kullanıcı yeni /menü atabilir)
        await interaction.response.send_message(f"'{self.search_query}' için sonuçlar tazeleniyor...", ephemeral=True)

# --- ANA KONTROL PANELİ ---
class ControlPanel(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="⏯️", style=discord.ButtonStyle.green)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc.is_playing(): vc.pause()
        elif vc.is_paused(): vc.resume()
        await interaction.response.defer()

    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.blurple)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc: vc.stop()
        await interaction.response.defer()

    @discord.ui.button(label="🔄", style=discord.ButtonStyle.gray)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_data(self.guild_id)
        data.loop = not data.loop
        await interaction.response.send_message(f"Döngü: {'Açık' if data.loop else 'Kapalı'}", ephemeral=True)

    @discord.ui.button(label="🗑️", style=discord.ButtonStyle.danger)
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_data(self.guild_id)
        data.queue.clear()
        data.titles.clear()
        await interaction.response.send_message("Çalma listesi temizlendi!", ephemeral=True)

# --- MÜZİK MOTORU ---
async def play_music(interaction):
    data = get_data(interaction.guild.id)
    vc = interaction.guild.voice_client

    if not data.queue:
        data.current_track = None
        return

    current_url = data.queue.pop(0)
    current_title = data.titles.pop(0)
    data.current_track = (current_url, current_title)

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(current_url, download=False)
        stream_url = info['url']

    def after_finished(error):
        if data.loop and data.current_track:
            data.queue.insert(0, data.current_track[0])
            data.titles.insert(0, data.current_track[1])
        
        coro = play_music(interaction)
        asyncio.run_coroutine_threadsafe(coro, interaction.client.loop)

    vc.play(discord.FFmpegOpusAudio(stream_url, **FFMPEG_OPTIONS), after=after_finished)
    
    embed = discord.Embed(title="🎶 Şu an Çalıyor", description=current_title, color=discord.Color.blue())
    await interaction.followup.send(embed=embed, view=ControlPanel(interaction.guild.id))

# --- BOT KOMUTLARI ---
class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        await self.tree.sync()

bot = MusicBot()

@bot.tree.command(name="menü", description="Şarkı arar ve seçim menüsü sunar.")
async def menu(interaction: discord.Interaction, arama: str):
    await interaction.response.defer()
    
    if not interaction.user.voice:
        return await interaction.followup.send("Ses kanalında değilsin!")

    if not interaction.guild.voice_client:
        await interaction.user.voice.channel.connect()

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        results = ydl.extract_info(f"ytsearch5:{arama}", download=False)['entries']
    
    options = [discord.SelectOption(label=r['title'][:100], value=r['webpage_url']) for r in results]
    view = SearchSelectView(options, arama, bot)
    await interaction.followup.send(f"🔎 '{arama}' için sonuçlar:", view=view)

@bot.tree.command(name="çalma_listesi", description="Sıradaki şarkıları gösterir.")
async def q_list(interaction: discord.Interaction):
    data = get_data(interaction.guild.id)
    if not data.titles:
        return await interaction.response.send_message("Liste şu an boş.")
    
    liste = "\n".join([f"{i+1}. {t}" for i, t in enumerate(data.titles)])
    await interaction.response.send_message(f"📜 **Sıradaki Şarkılar:**\n{liste}")

@bot.tree.command(name="dur", description="Botu kanaldan çıkarır.")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("Görüşürüz!")

bot.run(TOKEN)
