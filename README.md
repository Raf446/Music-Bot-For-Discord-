<div align="center">

# 🎵 Raf Music — Discord Music Bot

An advanced, high-performance Discord Music Bot built with **Python**, **discord.py (v2.x)**, and **Wavelink (v3.x)** powered by **Lavalink v4**.

![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![discord.py](https://img.shields.io/badge/discord.py-v2.x-5865F2?style=for-the-badge&logo=discord&logoColor=white)
![Wavelink](https://img.shields.io/badge/Wavelink-v3.x-00D26A?style=for-the-badge)
![Lavalink](https://img.shields.io/badge/Lavalink-v4.x-FF3366?style=for-the-badge)
![License](https://img.shields.io/badge/Status-Active%20Dev-blue?style=for-the-badge)

<br/>

> Pemutar musik Discord interaktif dengan antarmuka dinamis (*Interactive Embed & Buttons*), resolver playlist Spotify instan tanpa API key, filter lagu orisinil anti-remix, dan playback stabil via SoundCloud.

</div>

---

## ✨ Fitur Unggulan

- 🎛️ **Modern Interactive UI**: Desain pesan *Now Playing* dilengkapi tombol navigasi interaktif (*Previous, Play/Pause, Skip, Stop, Shuffle, Loop, Autoplay, Queue*).
- 🎯 **Smart Original Track Filter**: Algoritma cerdas yang otomatis menyaring rekaman non-orisinil (*remix, cover, slowed+reverb, bass boosted, sped up, karaoke, instrumental*) agar lagu yang diputar selalu versi resmi/rilis studio.
- 🟢 **Fast Spotify Resolution**: Membaca tautan track dan playlist Spotify secara langsung menggunakan teknik scraping embed publik tanpa memerlukan akun developer Spotify.
- ⚡ **Background Queue Loader**: Saat memutar playlist Spotify berukuran besar, lagu pertama langsung diputar seketika sementara sisa trek dimuat di latar belakang.
- 🛡️ **Stable Audio Provider**: Menggunakan SoundCloud sebagai resolver audio utama untuk menghindari proteksi bot detection / error status 400 YouTube.
- ⏱️ **Auto Inactive & Alone Timeout**: Bot otomatis memutuskan koneksi voice channel jika tidak ada aktivitas atau ditinggal sendirian di dalam voice room untuk menghemat resource.

---

## 🕹️ Tombol Interaktif (Now Playing Controller)

| Baris | Tombol | Fungsi |
| :---: | :--- | :--- |
| **Row 0** | `⏮️ Prev` | Mengulang lagu dari awal (`00:00`) atau memutar trek sebelumnya |
| **Row 0** | `⏯️ Pause / Resume` | Menjeda atau melanjutkan lagu secara real-time |
| **Row 0** | `⏭️ Skip` | Melompat ke antrean berikutnya |
| **Row 0** | `⏹️ Stop` | Menghentikan musik, mengosongkan antrean, dan keluar dari VC |
| **Row 1** | `🔀 Shuffle` | Mengacak urutan antrean trek lagu |
| **Row 1** | `🔁 Repeat` | Siklus mode loop: **Off** ➔ **Track** ➔ **Queue** ➔ **Off** |
| **Row 1** | `📻 Autoplay` | Menyalakan/mematikan rekomendasi lagu otomatis saat antrean habis (Testing) |
| **Row 1** | `📜 Queue` | Menampilkan pratinjau daftar lagu antrean (privat / ephemeral) |

---

## 📋 Daftar Perintah (Slash Commands)

| Command | Penjelasan |
| :--- | :--- |
| `/play <query/url>` | Memutar lagu dari judul teks atau tautan langsung (SoundCloud / Spotify) |
| `/pause` | Menjeda pemutaran lagu |
| `/resume` | Melanjutkan kembali lagu yang dijeda |
| `/skip` | Melewati lagu yang sedang diputar |
| `/stop` | Menghentikan musik, mengosongkan antrean, dan keluar dari VC |
| `/queue` | Menampilkan daftar antrean lengkap dengan sistem halaman (pagination) |
| `/nowplaying` | Menampilkan info pemutaran saat ini beserta tombol kontrol interaktif |
| `/volume <1-100>` | Mengatur volume suara pemutar musik |
| `/loop <mode>` | Memilih mode pengulangan lagu (`off`, `track`, `queue`) |

---

## 📂 Struktur Direktori

```text
Music-Bot-For-Discord-/
├── cogs/
│   └── music.py           # Core logic: playback, UI View, slash command, smart filter
├── lavalink/
│   ├── application.yml    # Konfigurasi Lavalink node & port
│   └── plugins/           # Plugin eksternal Lavalink
├── .env.example           # Template variabel lingkungan
├── .gitignore             # Pengaman token dan file sensitif
├── main.py                # Bot launcher & gateway handler
├── requirements.txt       # Dependencies Python
├── Start.bat              # Script launcher (Lavalink + Bot)
└── README.md              # Dokumentasi projek