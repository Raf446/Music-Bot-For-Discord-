"""Entry point bot musik Discord (discord.py + Wavelink + Lavalink v4)."""
import asyncio
import logging
import os

import discord
import wavelink
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("musicbot")

TOKEN = os.getenv("DISCORD_TOKEN")
LAVALINK_URI = os.getenv("LAVALINK_URI", "http://127.0.0.1:2333")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")  # opsional: sync instan ke 1 server


class MusicBot(commands.Bot):
    def __init__(self) -> None:
        # Gunakan Intents.all() agar semua handshake voice dan gateway diterima penuh
        intents = discord.Intents.all()
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self) -> None:
        # 1) Hubungkan ke Lavalink
        node = wavelink.Node(
            uri=LAVALINK_URI,
            password=LAVALINK_PASSWORD,
            inactive_player_timeout=300,
        )
        try:
            await wavelink.Pool.connect(nodes=[node], client=self, cache_capacity=100)
        except Exception:
            log.exception("Gagal terhubung ke Lavalink. Pastikan server Lavalink sudah jalan.")

        # 2) Load cogs
        await self.load_extension("cogs.music")

        # 3) Sync slash commands
        if DEV_GUILD_ID:
            guild = discord.Object(id=int(DEV_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self) -> None:
        log.info("Login sebagai %s (%s)", self.user, self.user.id)
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/play"))

    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        log.info("Lavalink node '%s' siap (resumed=%s)", payload.node.identifier, payload.resumed)


async def main() -> None:
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN belum diisi di file .env")
    async with MusicBot() as bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())