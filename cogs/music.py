"""Cog musik: slash commands, UI buttons, antrean, auto-disconnect, Spotify background resolver."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import cast

import discord
import requests
import wavelink
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("musicbot.music")

ALONE_TIMEOUT = 60
PAGE_SIZE = 10
EMBED_COLOR = discord.Color.blurple()


# ----------------------------------------------------------------- helpers
def fmt_time(ms: int) -> str:
    s = int(ms // 1000)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_clock(ms: int) -> str:
    """Format MM:SS (selalu 2 digit), mis. 00:53 / 03:13."""
    m, s = divmod(int(ms // 1000), 60)
    return f"{m:02d}:{s:02d}"


def progress_bar(pos: int, length: int, size: int = 16) -> str:
    """Contoh: ▬▬▬▬🔘▬▬▬▬▬▬▬▬▬▬▬▬ (posisi dihitung dari pos/length)."""
    if length <= 0:
        return "🔴 LIVE"
    filled = min(size - 1, int(size * pos / length))
    return "▬" * filled + "🔘" + "▬" * (size - filled - 1)


QUEUE_PREVIEW = 10
LOOP_LABELS = {
    wavelink.QueueMode.normal: "Off",
    wavelink.QueueMode.loop: "Track",
    wavelink.QueueMode.loop_all: "Queue",
}
LOOP_CYCLE = {  # Off -> Track -> Queue -> Off
    wavelink.QueueMode.normal: wavelink.QueueMode.loop,
    wavelink.QueueMode.loop: wavelink.QueueMode.loop_all,
    wavelink.QueueMode.loop_all: wavelink.QueueMode.normal,
}
SOURCE_LABELS = {
    "youtube": "YouTube",
    "youtubemusic": "YouTube Music",
    "soundcloud": "SoundCloud",
    "spotify": "Spotify via Audio Resolver",
}

# Daftar filter untuk menyortir hasil non-orisinil
JUNK_KEYWORDS = (
    "remix", "cover", "slowed", "reverb", "sped up", "speed up",
    "bass boosted", "karaoke", "instrumental", "tribute", "live session",
    "live version", "parody", "acoustic cover"
)


def error_embed(msg: str) -> discord.Embed:
    return discord.Embed(description=f"❌ {msg}", color=discord.Color.red())


def info_embed(msg: str) -> discord.Embed:
    return discord.Embed(description=msg, color=EMBED_COLOR)


def build_now_playing(player: wavelink.Player) -> discord.Embed:
    track = player.current
    if track is None:
        return info_embed("Tidak ada lagu yang sedang diputar.")

    source = SOURCE_LABELS.get((track.source or "").lower(), (track.source or "Unknown").title())
    status = "🟡 Dijeda" if player.paused else "🟢 Sedang Diputar"
    embed = discord.Embed(
        title=track.title[:256],
        url=track.uri or None,
        color=EMBED_COLOR,
    )
    embed.set_author(name=f"{status} | 🟢 {source}")

    pos = min(player.position, track.length) if track.length else player.position
    total = "LIVE" if track.is_stream else fmt_clock(track.length)
    embed.description = (
        f"**{track.author}**\n"
        f"`{fmt_clock(pos)}` {progress_bar(pos, track.length)} `{total}`"
    )

    embed.add_field(name="📑 Antrean", value=f"`{len(player.queue)} Lagu`")
    embed.add_field(name="🔁 Mode", value=f"`{LOOP_LABELS[player.queue.mode]}`")
    embed.add_field(
        name="📻 Autoplay",
        value=f"`{'Aktif' if player.autoplay == wavelink.AutoPlayMode.enabled else 'Nonaktif'}`",
    )

    if track.artwork:
        embed.set_thumbnail(url=track.artwork)

    requester_id = getattr(track.extras, "requester", None)
    member = player.guild.get_member(requester_id) if requester_id else None
    footer = f"Diminta oleh @{member.name if member else 'unknown'} • Wavelink v3 • Lavalink v4"
    embed.set_footer(text=footer, icon_url=member.display_avatar.url if member else None)
    return embed


def get_player(interaction: discord.Interaction) -> wavelink.Player | None:
    return cast(wavelink.Player, interaction.guild.voice_client) if interaction.guild else None


async def check_user_in_vc(interaction: discord.Interaction, player: wavelink.Player | None) -> bool:
    msg = None
    if player is None or not player.connected:
        msg = "Bot tidak sedang berada di voice channel."
    elif not isinstance(interaction.user, discord.Member) or interaction.user.voice is None \
            or interaction.user.voice.channel != player.channel:
        msg = f"Kamu harus berada di {player.channel.mention} untuk memakai kontrol ini."
    if msg:
        if interaction.response.is_done():
            await interaction.followup.send(embed=error_embed(msg), ephemeral=True)
        else:
            await interaction.response.send_message(embed=error_embed(msg), ephemeral=True)
        return False
    return True


# ------------------------------------------------------------------- views
class NowPlayingView(discord.ui.View):
    """Kontrol Now Playing: Row 0 = playback, Row 1 = mode & antrean."""

    def __init__(self, player: wavelink.Player | None = None) -> None:
        super().__init__(timeout=None)
        if player is not None:
            self.sync(player)

    def sync(self, player: wavelink.Player) -> None:
        if player.paused:
            self.btn_pause.label, self.btn_pause.emoji = "Resume", "▶️"
        else:
            self.btn_pause.label, self.btn_pause.emoji = "Pause", "⏸️"
        self.btn_repeat.label = f"Repeat: {LOOP_LABELS[player.queue.mode]}"
        autoplay_on = player.autoplay == wavelink.AutoPlayMode.enabled
        self.btn_autoplay.style = discord.ButtonStyle.success if autoplay_on else discord.ButtonStyle.secondary
        self.btn_autoplay.label = f"Autoplay: {'On' if autoplay_on else 'Off'}"
        self.btn_queue.label = f"Queue ({len(player.queue)})"

    async def update_ui(self, interaction: discord.Interaction, player: wavelink.Player) -> None:
        self.sync(player)
        await interaction.response.edit_message(embed=build_now_playing(player), view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await check_user_in_vc(interaction, get_player(interaction))

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        log.exception("Error pada tombol %s", item, exc_info=error)
        embed = error_embed(f"Terjadi kesalahan: `{error}`")
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(emoji="⏮️", label="Prev", style=discord.ButtonStyle.secondary,
                       custom_id="music_btn_prev", row=0)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        player = get_player(interaction)
        prev = getattr(player, "prev_track", None)
        if player.current and (player.position > 5000 or prev is None):
            await player.seek(0)
        elif prev is not None:
            if player.current:
                player.queue.put_at(0, player.current)
            await player.play(prev)
        await self.update_ui(interaction, player)

    @discord.ui.button(emoji="⏸️", label="Pause", style=discord.ButtonStyle.primary,
                       custom_id="music_btn_pause", row=0)
    async def btn_pause(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        player = get_player(interaction)
        await player.pause(not player.paused)
        await self.update_ui(interaction, player)

    @discord.ui.button(emoji="⏭️", label="Skip", style=discord.ButtonStyle.secondary,
                       custom_id="music_btn_skip", row=0)
    async def btn_skip(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        player = get_player(interaction)
        await player.skip(force=True)
        await self.update_ui(interaction, player)

    @discord.ui.button(emoji="⏹️", label="Stop", style=discord.ButtonStyle.danger,
                       custom_id="music_btn_stop", row=0)
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        player = get_player(interaction)
        player.queue.clear()
        cog = interaction.client.get_cog("Music")
        if cog is not None:
            cog.np_messages.pop(interaction.guild.id, None)
        await player.disconnect()
        await interaction.response.edit_message(content="⏹️ Pemutaran dihentikan dan antrean dikosongkan.",
                                                embed=None, view=None)

    @discord.ui.button(emoji="🔀", label="Shuffle", style=discord.ButtonStyle.secondary,
                       custom_id="music_btn_shuffle", row=1)
    async def btn_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        player = get_player(interaction)
        count = len(player.queue)
        if count > 1:
            player.queue.shuffle()
            confirm = info_embed(f"🔀 Antrean diacak (**{count}** lagu).")
        else:
            confirm = error_embed("Antrean terlalu pendek untuk diacak.")
        await self.update_ui(interaction, player)
        await interaction.followup.send(embed=confirm, ephemeral=True)

    @discord.ui.button(emoji="🔁", label="Repeat: Off", style=discord.ButtonStyle.secondary,
                       custom_id="music_btn_repeat", row=1)
    async def btn_repeat(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        player = get_player(interaction)
        player.queue.mode = LOOP_CYCLE[player.queue.mode]
        await self.update_ui(interaction, player)

    @discord.ui.button(emoji="📻", label="Autoplay: Off", style=discord.ButtonStyle.secondary,
                       custom_id="music_btn_autoplay", row=1)
    async def btn_autoplay(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        player = get_player(interaction)
        if player.autoplay == wavelink.AutoPlayMode.enabled:
            player.autoplay = wavelink.AutoPlayMode.disabled
        else:
            player.autoplay = wavelink.AutoPlayMode.enabled
        await self.update_ui(interaction, player)

    @discord.ui.button(emoji="📜", label="Queue (0)", style=discord.ButtonStyle.secondary,
                       custom_id="music_btn_queue", row=1)
    async def btn_queue(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        player = get_player(interaction)
        upcoming = list(player.queue)[:QUEUE_PREVIEW]
        lines = [f"`{i}.` [{t.title[:55]}]({t.uri}) — `{fmt_time(t.length)}`"
                 for i, t in enumerate(upcoming, start=1)]
        embed = discord.Embed(title="📜 Antrean Teratas", color=EMBED_COLOR,
                              description="\n".join(lines) or "*Antrean kosong*")
        if len(player.queue) > QUEUE_PREVIEW:
            embed.set_footer(text=f"...dan {len(player.queue) - QUEUE_PREVIEW} lagu lainnya • gunakan /queue")
        await self.update_ui(interaction, player)
        await interaction.followup.send(embed=embed, ephemeral=True)


class QueueView(discord.ui.View):
    def __init__(self, player: wavelink.Player, author_id: int) -> None:
        super().__init__(timeout=120)
        self.player, self.author_id, self.page = player, author_id, 0
        self.message: discord.Message | None = None
        self._sync()

    @property
    def pages(self) -> int:
        return max(1, -(-len(self.player.queue) // PAGE_SIZE))

    def _sync() -> None:
        self.page = min(self.page, self.pages - 1)
        self.prev.disabled = self.page <= 0
        self.next.disabled = self.page >= self.pages - 1

    def embed(self) -> discord.Embed:
        q = self.player.queue
        e = discord.Embed(title="📜 Antrean Lagu", color=EMBED_COLOR)
        if self.player.current:
            e.add_field(name="Sedang diputar",
                        value=f"[{self.player.current.title}]({self.player.current.uri})", inline=False)
        start = self.page * PAGE_SIZE
        lines = [
            f"`{i}.` [{t.title[:60]}]({t.uri}) — `{fmt_time(t.length)}`"
            for i, t in enumerate(list(q)[start:start + PAGE_SIZE], start=start + 1)
        ]
        e.add_field(name="Berikutnya", value="\n".join(lines) or "*Antrean kosong*", inline=False)
        total = sum(t.length for t in q)
        e.set_footer(text=f"Halaman {self.page + 1}/{self.pages} • {len(q)} lagu • {fmt_time(total)}")
        return e

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=error_embed("Hanya pemanggil command yang bisa mengganti halaman."), ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page -= 1
        self._sync()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page += 1
        self._sync()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def on_timeout(self) -> None:
        for c in self.children:
            c.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


# --------------------------------------------------------------------- cog
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.np_messages: dict[int, discord.Message] = {}
        self.alone_tasks: dict[int, asyncio.Task] = {}
        bot.add_view(NowPlayingView())

    async def cog_unload(self) -> None:
        for t in self.alone_tasks.values():
            t.cancel()

    # -------- Algoritma Filter Orisinil/Official
    async def _search_track(self, query: str) -> list[wavelink.Playable] | wavelink.Playlist | None:
        """Mencari audio orisinil resmi dan membuang versi remix/cover/edits."""
        # 1. URL langsung
        if query.startswith("http://") or query.startswith("https://"):
            try:
                res = await wavelink.Playable.search(query)
                if res:
                    return res
            except Exception:
                pass

        query_lower = query.lower()

        def pick_best_original(track_list: list[wavelink.Playable]) -> list[wavelink.Playable]:
            for t in track_list:
                t_title = t.title.lower()
                is_clean = True
                for junk in JUNK_KEYWORDS:
                    if junk in t_title and junk not in query_lower:
                        is_clean = False
                        break
                if is_clean:
                    return [t]
            return [track_list[0]]

        search_candidates = [f"{query} Official", query]
        for q in search_candidates:
            try:
                results = await wavelink.Playable.search(q, source=wavelink.TrackSource.SoundCloud)
                if not results:
                    continue
                if isinstance(results, wavelink.Playlist):
                    return results
                return pick_best_original(results)
            except Exception:
                continue

        return None

    # -------- wavelink events
    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        player = payload.player
        if player is None:
            return
        await self._clear_np(player.guild.id)
        channel = getattr(player, "text_channel", None)
        if channel:
            try:
                self.np_messages[player.guild.id] = await channel.send(
                    embed=build_now_playing(player), view=NowPlayingView(player))
            except discord.HTTPException:
                log.warning("Tidak bisa mengirim pesan Now Playing")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
        player = payload.player
        if player is None:
            return

        if payload.track is not None:
            player.prev_track = payload.track

        # Jangan proses jika track diganti atau dihentikan manual
        reason = getattr(payload, "reason", "")
        if reason in ("REPLACED", "CLEANUP", "STOPPED"):
            return

        # Jika antrean masih ada, wavelink otomatis memutar lagu berikutnya
        if not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)
        else:
            await self._clear_np(player.guild.id)

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload) -> None:
        player = payload.player
        channel = getattr(player, "text_channel", None) if player else None
        log.error("Track exception: %s", payload.exception)
        if channel and payload.track:
            await channel.send(embed=error_embed(
                f"Gagal memutar **{payload.track.title}**: audio tidak dapat diakses. "
                "Lanjut ke lagu berikutnya."))

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, payload: wavelink.TrackStuckEventPayload) -> None:
        if payload.player:
            await payload.player.skip(force=True)

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player) -> None:
        channel = getattr(player, "text_channel", None)
        if channel:
            await channel.send(embed=info_embed("👋 Keluar karena tidak ada aktivitas."))
        await self._clear_np(player.guild.id)
        await player.disconnect()

    async def _clear_np(self, guild_id: int) -> None:
        msg = self.np_messages.pop(guild_id, None)
        if msg:
            try:
                await msg.edit(view=None)
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState) -> None:
        guild = member.guild
        player = cast(wavelink.Player | None, guild.voice_client)
        if player is None or not player.connected:
            self._cancel_alone(guild.id)
            return
        humans = [m for m in player.channel.members if not m.bot]
        if humans:
            self._cancel_alone(guild.id)
        elif guild.id not in self.alone_tasks:
            self.alone_tasks[guild.id] = asyncio.create_task(self._alone_countdown(player))

    def _cancel_alone(self, guild_id: int) -> None:
        task = self.alone_tasks.pop(guild_id, None)
        if task:
            task.cancel()

    async def _alone_countdown(self, player: wavelink.Player) -> None:
        try:
            await asyncio.sleep(ALONE_TIMEOUT)
        except asyncio.CancelledError:
            return
        self.alone_tasks.pop(player.guild.id, None)
        if player.connected:
            channel = getattr(player, "text_channel", None)
            if channel:
                await channel.send(embed=info_embed(
                    f"👋 Keluar karena sendirian di voice channel selama {ALONE_TIMEOUT} detik."))
            player.queue.clear()
            await self._clear_np(player.guild.id)
            await player.disconnect()

    # -------- Spotify Embed HTML/JSON Parser
    async def _scrape_spotify(self, url: str) -> list[str]:
        clean_url = url.split("?")[0]
        loop = asyncio.get_running_loop()

        def fetch() -> list[str]:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
            res = []
            embed_url = clean_url.replace("open.spotify.com/", "open.spotify.com/embed/")
            try:
                r = requests.get(embed_url, headers=headers, timeout=10)
                if r.status_code != 200:
                    return res
                html = r.text
            except Exception:
                return res

            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
            if match:
                try:
                    data = json.loads(match.group(1))
                    entity = data.get("props", {}).get("pageProps", {}).get("state", {}).get("data", {}).get("entity", {})
                    track_list = entity.get("trackList", [])
                    for t in track_list:
                        title = t.get("title")
                        subtitle = t.get("subtitle", "")
                        if title:
                            res.append(f"{title} {subtitle}".strip())
                    if res:
                        return res
                except Exception:
                    pass

            titles = re.findall(r'"title":\s*"([^"]+)",\s*"subtitle":\s*"([^"]+)"', html)
            for t_title, t_sub in titles:
                if t_title not in ["Spotify", ""]:
                    res.append(f"{t_title} {t_sub}".strip())

            return res

        try:
            return await loop.run_in_executor(None, fetch)
        except Exception:
            log.exception("Gagal resolve Spotify")
            return []

    # -------- commands
    @app_commands.command(name="play", description="Putar lagu dari judul atau URL")
    @app_commands.describe(query="Judul lagu atau URL (SoundCloud / Spotify)")
    @app_commands.guild_only()
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        member = interaction.user
        if not isinstance(member, discord.Member) or member.voice is None or member.voice.channel is None:
            return await interaction.response.send_message(
                embed=error_embed("Kamu harus masuk voice channel dulu."), ephemeral=True)
        await interaction.response.defer()

        target_channel = member.voice.channel
        player = cast(wavelink.Player | None, interaction.guild.voice_client)

        if player is None:
            perms = target_channel.permissions_for(interaction.guild.me)
            if not (perms.connect and perms.speak):
                return await interaction.followup.send(embed=error_embed(
                    f"Aku tidak punya izin **Connect/Speak** di {target_channel.mention}."))
            try:
                player = await target_channel.connect(cls=wavelink.Player, self_deaf=True)
                player.channel = target_channel
            except Exception as e:
                log.exception("Gagal join VC")
                return await interaction.followup.send(embed=error_embed(f"Gagal masuk voice channel: `{e}`"))
            player.autoplay = wavelink.AutoPlayMode.disabled
            player.inactive_timeout = 300
            await player.set_volume(50)
        elif player.channel != target_channel:
            return await interaction.followup.send(embed=error_embed(
                f"Aku sedang dipakai di {player.channel.mention}."))

        player.text_channel = interaction.channel
        clean_query = query.strip()

        # LINK SPOTIFY (Diputar instan + background queue loader)
        if "open.spotify.com" in clean_query:
            spotify_queries = await self._scrape_spotify(clean_query)
            if not spotify_queries:
                return await interaction.followup.send(embed=error_embed("Gagal membaca link Spotify."))

            first_query = spotify_queries[0]
            res_first = await self._search_track(first_query)

            if not res_first:
                return await interaction.followup.send(embed=error_embed(f"Tidak dapat menemukan audio untuk `{first_query}`."))

            first_track = res_first[0] if isinstance(res_first, list) else res_first
            first_track.extras = {"requester": member.id}

            if not player.playing and not player.paused:
                await player.play(first_track)
            else:
                player.queue.put(first_track)

            if len(spotify_queries) == 1:
                return await interaction.followup.send(embed=info_embed(
                    f"✅ Ditambahkan: **[{first_track.title}]({first_track.uri})** — `{fmt_time(first_track.length)}`"))

            msg = await interaction.followup.send(embed=info_embed(
                f"🎶 Memutar **[{first_track.title}]({first_track.uri})**, memasukkan {len(spotify_queries)-1} lagu playlist ke antrean..."))

            async def load_remaining():
                count = 1
                for q in spotify_queries[1:]:
                    try:
                        res = await self._search_track(q)
                        if res:
                            t = res[0] if isinstance(res, list) else res
                            t.extras = {"requester": member.id}
                            player.queue.put(t)
                            count += 1
                    except Exception:
                        continue
                try:
                    await msg.edit(embed=info_embed(f"📚 Berhasil menambahkan **{count} lagu** ke antrean!"))
                except Exception:
                    pass

            asyncio.create_task(load_remaining())
            return

        # PENCARIAN TEKS BIASA
        try:
            tracks = await self._search_track(clean_query)
        except wavelink.LavalinkLoadException as e:
            return await interaction.followup.send(embed=error_embed(f"Gagal memuat: `{e.error}`"))
        except Exception as e:
            log.exception("Search error")
            return await interaction.followup.send(embed=error_embed(f"Tidak bisa menghubungi server audio: `{e}`"))

        if not tracks:
            return await interaction.followup.send(embed=error_embed(f"Tidak ada hasil untuk `{query}`."))

        if isinstance(tracks, wavelink.Playlist):
            for t in tracks:
                t.extras = {"requester": member.id}
            added = player.queue.put(tracks)
            msg = f"📚 Menambahkan playlist **{tracks.name}** ({added} lagu)"
            await interaction.followup.send(embed=info_embed(msg))
            if not player.playing and not player.paused:
                await player.play(player.queue.get())
        else:
            track = tracks[0] if isinstance(tracks, list) else tracks
            track.extras = {"requester": member.id}
            msg = f"✅ Ditambahkan: **[{track.title}]({track.uri})** — `{fmt_time(track.length)}`"
            await interaction.followup.send(embed=info_embed(msg))

            if not player.playing and not player.paused:
                await player.play(track)
            else:
                player.queue.put(track)

    @app_commands.command(name="skip", description="Lewati lagu saat ini")
    @app_commands.guild_only()
    async def skip(self, interaction: discord.Interaction) -> None:
        player = get_player(interaction)
        if not await check_user_in_vc(interaction, player):
            return
        if not player.current:
            return await interaction.response.send_message(embed=error_embed("Tidak ada lagu diputar."), ephemeral=True)
        title = player.current.title
        await player.skip(force=True)
        await interaction.response.send_message(embed=info_embed(f"⏭️ Melewati **{title}**"))

    @app_commands.command(name="pause", description="Jeda lagu")
    @app_commands.guild_only()
    async def pause(self, interaction: discord.Interaction) -> None:
        player = get_player(interaction)
        if not await check_user_in_vc(interaction, player):
            return
        if player.paused:
            return await interaction.response.send_message(embed=error_embed("Sudah dijeda."), ephemeral=True)
        await player.pause(True)
        await interaction.response.send_message(embed=info_embed("⏸️ Dijeda."))

    @app_commands.command(name="resume", description="Lanjutkan lagu")
    @app_commands.guild_only()
    async def resume(self, interaction: discord.Interaction) -> None:
        player = get_player(interaction)
        if not await check_user_in_vc(interaction, player):
            return
        if not player.paused:
            return await interaction.response.send_message(embed=error_embed("Lagu tidak sedang dijeda."), ephemeral=True)
        await player.pause(False)
        await interaction.response.send_message(embed=info_embed("▶️ Dilanjutkan."))

    @app_commands.command(name="stop", description="Hentikan musik, kosongkan antrean, dan keluar")
    @app_commands.guild_only()
    async def stop(self, interaction: discord.Interaction) -> None:
        player = get_player(interaction)
        if not await check_user_in_vc(interaction, player):
            return
        player.queue.clear()
        await self._clear_np(interaction.guild.id)
        await player.disconnect()
        await interaction.response.send_message(embed=info_embed("⏹️ Musik dihentikan."))

    @app_commands.command(name="queue", description="Tampilkan antrean lagu")
    @app_commands.guild_only()
    async def queue(self, interaction: discord.Interaction) -> None:
        player = get_player(interaction)
        if player is None or (not player.current and not player.queue):
            return await interaction.response.send_message(embed=error_embed("Antrean kosong."), ephemeral=True)
        view = QueueView(player, interaction.user.id)
        await interaction.response.send_message(embed=view.embed(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="volume", description="Atur volume (1-100)")
    @app_commands.describe(level="Volume 1-100")
    @app_commands.guild_only()
    async def volume(self, interaction: discord.Interaction, level: app_commands.Range[int, 1, 100]) -> None:
        player = get_player(interaction)
        if not await check_user_in_vc(interaction, player):
            return
        await player.set_volume(level)
        await interaction.response.send_message(embed=info_embed(f"🔊 Volume diatur ke **{level}%**"))

    @app_commands.command(name="nowplaying", description="Info lagu yang sedang diputar")
    @app_commands.guild_only()
    async def nowplaying(self, interaction: discord.Interaction) -> None:
        player = get_player(interaction)
        if player is None or not player.current:
            return await interaction.response.send_message(embed=error_embed("Tidak ada lagu diputar."), ephemeral=True)
        await interaction.response.send_message(embed=build_now_playing(player), view=NowPlayingView(player))

    @app_commands.command(name="loop", description="Atur mode loop")
    @app_commands.describe(mode="Mode loop")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Off", value="off"),
        app_commands.Choice(name="Track (lagu ini)", value="track"),
        app_commands.Choice(name="Queue (seluruh antrean)", value="queue"),
    ])
    @app_commands.guild_only()
    async def loop(self, interaction: discord.Interaction, mode: app_commands.Choice[str]) -> None:
        player = get_player(interaction)
        if not await check_user_in_vc(interaction, player):
            return
        player.queue.mode = {
            "off": wavelink.QueueMode.normal,
            "track": wavelink.QueueMode.loop,
            "queue": wavelink.QueueMode.loop_all,
        }[mode.value]
        await interaction.response.send_message(embed=info_embed(f"🔁 Loop: **{mode.name}**"))

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        log.exception("Command error", exc_info=error)
        embed = error_embed(f"Terjadi kesalahan: `{error}`")
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))