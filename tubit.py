import importlib.util, subprocess as cmd, platform, os, re, shutil, sys

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

FFMPEG_DIR = resource_path("ffmpeg/bin")
FFMPEG_EXE = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
FFPROBE_EXE = os.path.join(FFMPEG_DIR, "ffprobe.exe")

def get_ffmpeg_loc():
    # Bundled FFmpeg (Windows executable)
    if os.path.isdir(FFMPEG_DIR):
        return FFMPEG_DIR

    # Linux / macOS system ffmpeg
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return os.path.dirname(ffmpeg)
    
    return None

def money_ape():
    print(r" __  __                              _                 ")
    print(r"|  \/  | ___  _ __   ___ _   _      / \   _ __   ___   ")
    print(r"| |\/| |/ _ \| '_ \ / _ \ | | |____/ _ \ | '_ \ / _ \  ")
    print(r"| |  | | (_) | | | |  __/ |_| |___/ ___ \| |_) |  __/  ")
    print(r"|_|  |_|\___/|_| |_|\___|\___,|  /_/   \_\ .__/ \___|  ")
    print(r"                         |___/           |_|           ")
    print("\033[1;32m\n                   Github : Money-Ape {verison : 1.1}")

money_ape()

current_os = platform.system()

def OS_platform_verify():

    os_var = current_os
    if os_var == "Windows":
        print(f"Platform Detected.! = {os_var}\n")
        module_names = ["yt_dlp", "PySide6"]
        for module_name in module_names:
            if importlib.util.find_spec(module_name) is not None:
                print(f"{module_name}.......ok")
                print(f"{module_name} is already installed.\n")
            else:
                print(f"{module_name}.......Error")
                print(f"{module_name} is not installed.\nInstalling...")
                try:
                    cmd.run([sys.executable, "-m", "pip", "install", module_name, "--quiet"], check=True)
                    print(f"{module_name} installed successfully.\n")
                except cmd.CalledProcessError:
                    print(f"Failed to install {module_name}.\n")

        setup_ffmpeg()
    
    elif os_var == "Linux":
        print(f"Platform Detected.! = {os_var}\n")
        module_names = ["yt_dlp", "PySide6"]
        for module_name in module_names:
            if importlib.util.find_spec(module_name) is not None:
                print(f"{module_name}.......ok")
                print(f"{module_name} is already installed.\n")
            else:
                print(f"{module_name}.......Error")
                print(f"{module_name} is not installed.\nInstalling...")
                try:
                    cmd.run([sys.executable, "-m", "pip", "install", module_name, "--quiet"], check=True)
                    print(f"{module_name} installed successfully.\n")
                except cmd.CalledProcessError:
                    print(f"Failed to install {module_name}.\n")
    else:
        print("Your Operating System isn't compatible for PYTUBE.!!")

def setup_ffmpeg():
    import winreg

    if shutil.which("ffmpeg"): # If Available already
        print("ffmpeg.......ok")
        print("ffmpeg is already available.\n")
        return
    
    source = os.path.join(os.getcwd(), "ffmpeg")
    dest = r"C:\ffmpeg"
    if not os.path.isdir(source):
        print("Bundled FFmpeg folder not found.")
        return
    if not os.path.exists(dest): # Copy only if not already copied
        print("Installing FFmpeg...")
        cmd.run(["robocopy", source, dest, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS", "/NP"])

    current_path = os.environ.get("PATH", "")
    ffmpeg_bin = r"C:\ffmpeg\bin"
    if ffmpeg_bin.lower() not in current_path.lower():
        print("Adding FFmpeg to PATH...")
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, "Environment", 0,
            winreg.KEY_ALL_ACCESS
        )
        try:
            value, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            value = ""
        if ffmpeg_bin.lower() not in value.lower():
            value += ";" + ffmpeg_bin
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, value)
        
        winreg.CloseKey(key)
        print("Restart Windows Terminal for PATH changes.")
    print("ffmpeg setup complete.\n")


OS_platform_verify()

import yt_dlp
from PySide6.QtCore import (QObject, QThread, Signal)

def format_file_size(size):
    if size is None:
        return "Unknown"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    for unit in units:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    
    return f"{size:.2f} PB"

class FetchWorker(QThread):
    finished = Signal(dict, list)
    error = Signal(str)

    def __init__(self, url):
        super().__init__()

        self.url = url

    def run(self):
        try:
            opts = {
                "quiet" : True,
                "skip_download" : True
            }
            with yt_dlp.YoutubeDL(opts) as tubit_ydl:
                info = tubit_ydl.extract_info(self.url, download=False)

            if not info:
                raise ValueError("Could not extract video information.")

            formats = []
            seen = set()
            for fmt in info.get("formats", []):
                if not fmt.get("format_id"):
                    continue

                if fmt.get("protocol") == "mhtml":
                    continue

                height = fmt.get("height")
                filesize = fmt.get("filesize_approx", fmt.get("filesize"))
                vcodec = fmt.get("vcodec", "none")
                acodec = fmt.get("acodec", "none")

                key = (
                    height,
                    fmt.get("ext"),
                    vcodec, acodec
                )
                if key in seen:
                    continue

                seen.add(key)

                formats.append({
                    "format_id" : fmt["format_id"],
                    "quality" : f"{height}p"

                    if height else "Audio",
                    "extension" : fmt.get("ext", "Unknown").upper(),

                    "size" : format_file_size(filesize),
                    "codec" : vcodec,
                    "height" : height or 0,
                    "has_audio" : acodec != "none",
                    "has_video" : vcodec != "none",
                })

            formats.sort(key=lambda x: (
                not x["has_video"], -x["height"]
                )
            )
            self.finished.emit(info, formats)
        
        except Exception as e:
            self.error.emit(str(e))

# ==================================================
# Backend

class TubitBack(QObject):
    formats_loaded = Signal(dict, list)
    error = Signal(str)

    download_progress = Signal(float, str)
    download_finished = Signal()
    download_error = Signal(str)

    def __init__(self):
        super().__init__()

        self.fetch_worker = None
        self.download_worker = None

    def fetch_formats(self, url):
        if self.fetch_worker and self.fetch_worker.isRunning():
            return

        self.fetch_worker = FetchWorker(url)

        self.fetch_worker.finished.connect(self.formats_loaded.emit)
        self.fetch_worker.error.connect(self.error.emit)

        # Cleanup
        self.fetch_worker.finished.connect(self.fetch_worker.deleteLater)
        self.fetch_worker.error.connect(self.fetch_worker.deleteLater)

        self.fetch_worker.finished.connect(lambda: setattr(self, "fetch_worker", None))
        self.fetch_worker.error.connect(lambda: setattr(self, "fetch_worker", None))

        self.fetch_worker.start()

    def download(self, url, format_id, download_dir):
        if self.download_worker and self.download_worker.isRunning():
            return

        self.download_worker = DownloadWorker(url, format_id, download_dir)

        self.download_worker.progress.connect(self.download_progress.emit)
        self.download_worker.finished.connect(self.download_finished.emit)
        self.download_worker.error.connect(self.download_error.emit)

        # Cleanup
        self.download_worker.finished.connect(self.download_worker.deleteLater)
        self.download_worker.error.connect(self.download_worker.deleteLater)

        self.download_worker.finished.connect(lambda: setattr(self, "download_worker", None))
        self.download_worker.error.connect(lambda: setattr(self, "download_worker", None))

        self.download_worker.start()

    def stop(self):
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.fetch_worker.wait()

        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.wait()

class DownloadWorker(QThread):
    progress = Signal(float, str)

    finished = Signal()
    error = Signal(str)

    def __init__(self, url, format_id, download_dir):
        super().__init__()

        self.url = url
        self.format_id = format_id
        self.download_dir = download_dir

    def progress_hook(self, d):
        if d["status"] == "downloading":
            ansi = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
            percent_text = ansi.sub("", d.get("_percent_str", "0%"))
            match = re.search(r"(\d+(?:\.\d+)?)", percent_text)
            value = float(match.group(1)) if match else 0.0

            speed = ansi.sub("", d.get("_speed_str", ""))
            eta = ansi.sub("", d.get("_eta_str", ""))

            status = f"{value:.1f}%"

            if speed:
                status += f" • {speed}"

            if eta:
                status += f" • ETA {eta}"
            
            self.progress.emit(value, status)

    def run(self):
        try:
            opts = {
                "format" : self.format_id,
                "merge_output_format" : "mp4",
                "outtmpl" : os.path.join(self.download_dir, "%(title)s.%(ext)s"),
                "progress_hooks" : [self.progress_hook],
                "windowsfilenames" : True,
                "concurrent_fragment_downloads" : 4,
            }

            ffmpeg = get_ffmpeg_loc()
            if ffmpeg:
                opts["ffmpeg_location"] = ffmpeg

            success = False
            with yt_dlp.YoutubeDL(opts) as tubit_ydl:
                tubit_ydl.download([self.url])
                success = True

            if success:
                self.finished.emit() # Only now is the worker truly finished.
        
        except Exception as e:
            self.error.emit(str(e))