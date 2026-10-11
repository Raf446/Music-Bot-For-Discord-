# Discord Music Bot (discord.py + Wavelink + Lavalink v4)

## Struktur
```
discord-music-bot/
├── main.py
├── cogs/music.py
├── lavalink/
│   ├── application.yml
│   └── plugins/            # dibuat otomatis
├── .env.example  -> salin ke .env
└── requirements.txt
```

## Prasyarat
- Python 3.10+
- **Java 17+** (untuk Lavalink v4; cek `java -version`). Unduh: https://adoptium.net
- **FFmpeg tidak diperlukan** — Lavalink melakukan decoding/encoding sendiri. (`discord.py[voice]` hanya butuh PyNaCl, otomatis terpasang.)

## Instalasi
1. Buat bot di https://discord.com/developers/applications → Bot → salin token.
   Invite dengan scope `bot applications.commands` dan izin *Connect, Speak, Send Messages, Embed Links*.
2. Unduh `Lavalink.jar` (v4) dari https://github.com/lavalink-devs/Lavalink/releases dan taruh di folder `lavalink/`.
3. Edit `lavalink/application.yml`: isi `clientId/clientSecret` Spotify (atau set `spotify: false`), dan ganti password.
4. Python:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate        # Linux/mac: source .venv/bin/activate
   pip install -r requirements.txt
   copy .env.example .env        # lalu isi DISCORD_TOKEN & password
   ```

## Menjalankan
Terminal 1 (Lavalink; plugin diunduh saat pertama kali):
```bash
cd lavalink
java -Xmx512m -jar Lavalink.jar
```
Tunggu log `Lavalink is ready to accept connections.`

Terminal 2:
```bash
python main.py
```

## Command
`/play` `/skip` `/pause` `/resume` `/stop` `/queue` `/volume` `/nowplaying` `/loop`

## Catatan anti-ban YouTube
- Memakai plugin **youtube-source** (bukan source bawaan yang sudah rusak).
- Jika muncul "Sign in to confirm you're not a bot": aktifkan `oauth` (akun burner, bukan akun utama) dan/atau isi `pot` di `application.yml`, lalu jalankan ulang. Lihat https://github.com/lavalink-devs/youtube-source
- Jalankan dari IP VPS/datacenter lebih rawan diblok daripada IP rumahan; SoundCloud (`scsearch:`) jadi fallback.
- Versi plugin berubah cepat, cek rilis terbaru di repo masing-masing bila gagal memuat.

## Fitur resilience
- Auto-disconnect 60 dtk jika sendirian di VC (`ALONE_TIMEOUT`), dan 5 menit jika idle.
- Pesan error untuk: user tidak di VC, izin kurang, join gagal, track tidak ditemukan, node Lavalink mati, track error/stuck (otomatis skip).
