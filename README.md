# 🎞️ Tubit

<p align="center">
   <img src="assets/Tubit.png" width="350">
</p>

<p align="center">
   Fast • Simple • Reliable
</p>

**Tubit** is a modern Python desktop application for downloading videos from **YouTube** and **Instagram** using **yt-dlp** and **FFmpeg**. It automatically fetches every available format, lets you filter by **Video**, **Video Only**, or **Audio Only**, and intelligently merges separate video and audio streams when required.

---

## ✨ Features

- 📺 Download videos from **YouTube**.
- 📸 Download videos from **Instagram**.
- 🎥 Fetch all available video and audio formats in one click.
- 🎛️ Filter formats by **Video**, **Video Only**, or **Audio Only**.
- 🎯 Pick the exact quality, extension, and codec from a visual format grid.
- 📁 Choose where downloaded files are saved.
- 🔍 Smart deduplication so you never see the same format twice.
- 🔊 Automatically merges video and audio using **FFmpeg** when necessary.
- ⚡ Real-time download progress with speed and ETA.
- 🖥️ Modern, responsive desktop interface built with **PySide6** (fetching and downloading run on background threads, so the UI never freezes).
- 📦 Supports MP4 and WebM formats.
- 🔍 Displays video information including:
  - Thumbnail
  - Title
  - Channel/Uploader
  - Duration

---

## 🧩 Tech Stack

- **Language:** Python
- **GUI:** PySide6 (Qt)
- **Downloader:** yt-dlp
- **Media Processing:** FFmpeg

---

<p align="center">
  <img src="assets/Tubit_main_window.png" alt="Tubit Main Window" width="900">
</p>

---

## 🚀 How to Use

1. Launch **Tubit**.
2. Paste a supported YouTube or Instagram URL into the URL field.
3. Click **Fetch Available Formats**.
4. Once formats load, choose a mode:
   - **Video** — video + best matching audio
   - **Video Only** — video stream only
   - **Audio Only** — audio stream only
5. Select your preferred quality/format card (shows resolution, extension, codec, and file size).
6. (Optional) Click **Browse** to choose a save location — defaults to your **Downloads** folder.
7. Click **Download** and watch live progress, speed, and ETA.
8. Tubit will automatically:
   - Merge best audio with video (Video mode)
   - Download only the video stream (Video Only mode)
   - Download only the audio stream (Audio Only mode)

---

## 🌐 Supported Websites

Currently supported:

- ✅ YouTube
- ✅ Instagram

More websites supported by **yt-dlp** may be added in future updates.

---

## 🔧 Requirements

- Python 3.9+

- Windows:
  - No additional setup required — FFmpeg is bundled with the release.
  - When run from source, Tubit checks for `yt-dlp` and `PySide6` on startup and installs anything missing automatically.

- Linux:
  - Run `run.sh` to install all required dependencies, including FFmpeg.
  - Tubit also checks for `yt-dlp` and `PySide6` on startup and installs anything missing automatically.

---

## 📥 FFmpeg

Tubit uses **FFmpeg** to merge separate video and audio streams for high-quality downloads.

### Windows

The official Windows release bundles **FFmpeg** automatically, so no additional installation is required. When running from source, Tubit will copy the bundled `ffmpeg` folder to `C:\ffmpeg` and add it to your user `PATH` automatically if it isn't already available.

If you prefer using your own FFmpeg installation, you can download it from:

https://ffmpeg.org/download.html

### Linux

Run the provided installation script to install FFmpeg and all required dependencies:

```bash
./run.sh
```

To verify that FFmpeg is installed correctly:

```bash
ffmpeg -version
```

---

## 🚧 Roadmap

Planned features:

- Playlist downloading
- Download history
- Subtitle downloading
- Thumbnail embedding
- Batch downloads

---

## 📜 License

This project is licensed under the **MIT License**.

Please also comply with the licenses of:

- yt-dlp
- FFmpeg

---

## 🙏 Credits

- **yt-dlp** — https://github.com/yt-dlp/yt-dlp
- **FFmpeg** — https://ffmpeg.org

---

## 👨‍💻 Developed By

**Lovepreet Singh (Money-Ape)**

GitHub:
https://github.com/Money-Ape

---

⭐ If you find Tubit useful, consider giving the repository a star!