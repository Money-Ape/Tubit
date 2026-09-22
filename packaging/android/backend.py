import os, re, sys, threading, yt_dlp, traceback, shutil, subprocess, mimetypes
from kivy.clock import Clock
from kivy.utils import platform

print("=" * 50)
print("Platform :", platform)
print("Python   :", sys.version)
print("yt-dlp   :", yt_dlp.version.__version__)
print("=" * 50)

ALLOW_STREAM_MERGE = True

def resource_path(relative_path):
    """Same helper as tubit.py/gui.py, for locating bundled assets (e.g. the
    app icon) whether running from source or a packaged build."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# ==================================================
# Android storage / permissions helpers
# ==================================================
def get_download_dir():
    if platform == "android":
        download_dir = "/storage/emulated/0/Download/Tubit"
        try:
            os.makedirs(download_dir, exist_ok=True)
        except Exception as e:
            print(f"[Storage] Could not pre-create {download_dir}: {e}")
    else:
        download_dir = os.path.join(os.path.expanduser("~"), "Downloads", "Tubit")
        os.makedirs(download_dir, exist_ok=True)

    return download_dir

def get_temp_download_dir():
    """Private, always-writable scratch folder where yt-dlp actually
    writes files. No permission ever needed here on any Android
    version. Finished files get moved out via publish_to_public_downloads()."""

    if platform == "android":
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            base = activity.getExternalFilesDir(None).getAbsolutePath()
        except Exception as e:
            print(f"[Storage] Could not resolve app-specific dir, using home: {e}")
            base = os.path.expanduser("~")
        temp_dir = os.path.join(base, "tmp_downloads")
    else:
        temp_dir = os.path.join(os.path.expanduser("~"), ".tubit_tmp")

    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

def get_android_sdk_int():
    try:
        from jnius import autoclass

        VERSION = autoclass("android.os.Build$VERSION")
        return int(VERSION.SDK_INT)
    except Exception as e:
        print(f"[Storage] Could not read SDK version: {e}")
        return 0

def publish_to_public_downloads(local_path):
    """Move a finished file from private temp storage into the public
    Download/Tubit folder, the same way real Android apps do it: via
    MediaStore on API 29+ (no permission needed, no popup), falling
    back to the classic WRITE_EXTERNAL_STORAGE permission + direct
    write on API < 29 (pre-scoped-storage devices).

    Returns the resulting display path on success, or None on failure
    (in which case the file is left in temp storage untouched)."""

    display_name = os.path.basename(local_path)
    mime_type = mimetypes.guess_type(display_name)[0] or "application/octet-stream"

    if platform != "android":
        dest_dir = os.path.join(os.path.expanduser("~"), "Downloads", "Tubit")
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, display_name)
        shutil.move(local_path, dest_path)
        return dest_path

    try:
        from jnius import autoclass

        sdk_int = get_android_sdk_int()
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        resolver = activity.getContentResolver()

        if sdk_int >= 29:
            MediaStoreDownloads = autoclass("android.provider.MediaStore$Downloads")
            ContentValues = autoclass("android.content.ContentValues")

            values = ContentValues()
            values.put("_display_name", display_name)
            values.put("mime_type", mime_type)
            values.put("relative_path", "Download/Tubit")

            item_uri = resolver.insert(MediaStoreDownloads.EXTERNAL_CONTENT_URI, values)
            if item_uri is None:
                raise RuntimeError("MediaStore insert returned a null Uri")

            out_stream = resolver.openOutputStream(item_uri)
            try:
                with open(local_path, "rb") as f:
                    while True:
                        chunk = f.read(1024 * 1024)
                        if not chunk:
                            break
                        out_stream.write(chunk)
                out_stream.flush()
            finally:
                out_stream.close()

            os.remove(local_path)
            return "/storage/emulated/0/Download/Tubit/" + display_name

        else:
            from android.permissions import Permission, request_permissions, check_permission

            if not check_permission(Permission.WRITE_EXTERNAL_STORAGE):
                request_permissions([
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE,
                ])

            dest_dir = "/storage/emulated/0/Download/Tubit"
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, display_name)
            shutil.move(local_path, dest_path)
            return dest_path

    except Exception as e:
        print(f"[Storage] Could not publish {display_name} to public Downloads: {e}")
        return None

# ==================================================
# ffmpeg binary location
# ==================================================
def get_ffmpeg_path():
    if platform == "android":
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            native_lib_dir = PythonActivity.mActivity.getApplicationInfo().nativeLibraryDir
            ffmpeg_path = os.path.join(native_lib_dir, "libffmpegbin.so")

            if os.path.exists(ffmpeg_path):
                return ffmpeg_path

            print(f"[ffmpeg] Expected binary not found at {ffmpeg_path}")
            return None

        except Exception as e:
            error_mesg = str(e)
            print(f"[ffmpeg] Could not resolve native lib dir: {error_mesg}")
            return None

    return "ffmpeg"

def get_ffprobe_path():
    if platform == "android":
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            native_lib_dir = PythonActivity.mActivity.getApplicationInfo().nativeLibraryDir
            ffprobe_path = os.path.join(native_lib_dir, "libffprobebin.so")

            return ffprobe_path if os.path.exists(ffprobe_path) else None

        except Exception as e:
            print(f"[ffprobe] Could not resolve native lib dir: {e}")
            return None

    return "ffprobe"

_FFMPEG_BIN_DIR = None

def prepare_ffmpeg_location():
    global _FFMPEG_BIN_DIR

    if platform != "android":
        return get_ffmpeg_path()

    if _FFMPEG_BIN_DIR and os.path.isdir(_FFMPEG_BIN_DIR):
        return _FFMPEG_BIN_DIR

    ffmpeg_bin = get_ffmpeg_path()
    if not ffmpeg_bin or not os.path.exists(ffmpeg_bin):
        print("[ffmpeg] No bundled ffmpeg binary available; leaving ffmpeg_location unset")
        return None

    ffprobe_bin = get_ffprobe_path() or ffmpeg_bin
    if ffprobe_bin == ffmpeg_bin:
        print("[ffprobe] No bundled libffprobebin.so found - reusing the ffmpeg "
              "binary under the 'ffprobe' name. This stops the exec-on-missing-path "
              "crash, but real ffprobe-only features (accurate duration/format "
              "probing) won't work until a real ffprobe binary is bundled.")

    try:
        if platform == "android":
            try:
                from jnius import autoclass

                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                activity = PythonActivity.mActivity
                base = activity.getFilesDir().getAbsolutePath()
            except Exception as e:
                print(f"[ffmpeg] Could not resolve internal files dir, falling back: {e}")
                base = os.path.dirname(get_temp_download_dir())
        else:
            base = os.path.dirname(get_temp_download_dir())

        bin_dir = os.path.join(base, "ffmpeg_bin")
        os.makedirs(bin_dir, exist_ok=True)

        for name, source in (("ffmpeg", ffmpeg_bin), ("ffprobe", ffprobe_bin)):
            link_path = os.path.join(bin_dir, name)
            if os.path.exists(link_path) or os.path.islink(link_path):
                # Re-link if it's pointing at the wrong source (e.g. a real
                # ffprobe binary was added after the placeholder was created).
                if os.path.realpath(link_path) == os.path.realpath(source):
                    continue
                os.remove(link_path)
            try:
                os.symlink(source, link_path)
            except OSError:
                shutil.copy2(source, link_path)
            try:
                os.chmod(link_path, 0o755)
            except OSError:
                pass

        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        _FFMPEG_BIN_DIR = bin_dir
        return bin_dir

    except Exception as e:
        print(f"[ffmpeg] Could not prepare ffmpeg/ffprobe dir: {e}")
        return None

def format_file_size(size):
    if size is None:
        return "Unknown"

    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

    return f"{size:.2f} PB"

# ==================================================
# Format labelling (works for YouTube *and* Instagram)
# ==================================================
_GENERIC_NOTES = ("dash", "unknown", "default", "medium", "low", "high")

def friendly_codec(codec):
    # vp09.00.31.08...' -> 'VP9', 'avc1.64001f' -> 'H.264', 'mp4a.40.2' -> 'AAC
    if not codec or codec == "none":
        return None
    c = codec.lower()
    table = (
        (("avc1", "avc3", "h264"), "H.264"),
        (("hev1", "hvc1", "h265"), "H.265"),
        (("vp09", "vp9"), "VP9"),
        (("vp08", "vp8"), "VP8"),
        (("av01", "av1"), "AV1"),
        (("mp4a", "aac"), "AAC"),
        (("opus",), "Opus"),
        (("vorbis",), "Vorbis"),
        (("ec-3", "eac3"), "E-AC3"),
        (("mp3",), "MP3"),
    )
    for prefixes, name in table:
        if c.startswith(prefixes):
            return name
    return c.split(".")[0].upper()

def describe_format(fmt, duration=None):
    vcodec, acodec = fmt.get("vcodec"), fmt.get("acodec")
    height, width = fmt.get("height"), fmt.get("width")
    fps, tbr, abr = fmt.get("fps"), fmt.get("tbr"), fmt.get("abr")
    note = (fmt.get("format_note") or "").strip()

    audio_only = vcodec == "none"
    video_only = acodec == "none" and vcodec not in (None, "none")
    has_video = not audio_only
    has_audio = not video_only

    # ---- quality label ----
    if audio_only:
        rate = abr or tbr
        quality = f"{int(rate)} kbps" if rate else "Audio"
    elif height:
        # Reels are portrait (720x1280) -> use the shorter side so it reads 720p
        side = min(height, width) if width else height
        quality = f"{int(side)}p"
        if fps and fps > 30:
            quality += f"{int(fps)}"
    elif note and not note.lower().startswith(_GENERIC_NOTES):
        quality = note
    elif tbr:
        quality = f"{int(tbr)} kbps"
    else:
        quality = "Video"

    # ---- detail line ----
    vc, ac = friendly_codec(vcodec), friendly_codec(acodec)
    if audio_only:
        detail = ac or "Audio only"
    elif video_only:
        detail = f"{vc or 'Video'} \u2022 no audio"
    elif vc and ac:
        detail = f"{vc} + {ac}"
    else:
        detail = f"{vc} \u2022 video+audio" if vc else "Video + audio"
    if width and height and not audio_only:
        detail += f" \u2022 {int(width)}x{int(height)}"

    # ---- size (exact -> approx -> estimated from bitrate) ----
    size = fmt.get("filesize") or fmt.get("filesize_approx")
    size_text = format_file_size(size) if size else None
    if not size_text and tbr and duration:
        size_text = "~" + format_file_size(tbr * 125 * duration)
    if not size_text:
        size_text = "Size unknown"

    return {
        "quality": quality,
        "codec": detail,
        "size": size_text,
        "has_video": has_video,
        "has_audio": has_audio,
        "audio_known": acodec not in (None,),   # False -> unsure whether audio is included
        "sort_key": (height or 0, tbr or abr or 0),
    }

# ==================================================
# Background workers (plain threads, not QThread)
# ==================================================
class FetchWorker(threading.Thread):
    def __init__(self, url, on_done, on_error):
        super().__init__(daemon=True)
        self.url = url
        self.on_done = on_done
        self.on_error = on_error

    def run(self):
        try:
            print("=" * 60)
            print("FetchWorker started")
            print("Platform :", platform)
            print("Python   :", sys.version)
            print("yt-dlp   :", yt_dlp.version.__version__)
            print("URL      :", self.url)
            print("=" * 60)

            print("sys.stdout :", type(sys.stdout), sys.stdout)
            print("sys.stderr :", type(sys.stderr), sys.stderr)
            print("stdout.write :", hasattr(sys.stdout, "write"))
            print("stderr.write :", hasattr(sys.stderr, "write"))

            print("STEP 1 : Building YoutubeDL options")
            class Logger:
                def debug(self, msg):
                    print("[DEBUG]", msg)

                def warning(self, msg):
                    print("[WARNING]", msg)

                def error(self, msg):
                    print("[ERROR]", msg)

            ffmpeg_loc = prepare_ffmpeg_location()
            print("STEP 1b: ffmpeg_location resolved to", ffmpeg_loc)

            opts = {
                "quiet": False,
                "skip_download": True,
                "logger": Logger(),
                "progress_hooks": [
                    lambda d: print("HOOK:", d.get("status"))
                ],
                # YouTube has been DRM-protecting the 'tv' client's streams
                # since early 2025 (yt-dlp issue #12563), and yt-dlp tries
                # 'tv' first by default, so a lot of videos were failing as
                # "DRM protected" even though non-DRM formats exist via other
                # clients. Skip 'tv' and let yt-dlp fall back through its
                # other default clients instead. Revisit this if YouTube
                # changes tactics again - it's a moving target.
                "extractor_args": {
                    "youtube": {"player_client": ["default", "-tv"]}
                },
            }
            if ffmpeg_loc:
                opts["ffmpeg_location"] = ffmpeg_loc

            print("STEP 2 : Creating YoutubeDL")
            ydl = yt_dlp.YoutubeDL(opts)

            print("STEP 3 : Calling extract_info()")
            info = ydl.extract_info(self.url, download=False)

            print("STEP 4 : extract_info() returned")
            formats = info.get("formats", [])
            print(f"Formats found : {len(formats)}")

            duration = info.get("duration")
            processed = []

            for fmt in formats:
                d = describe_format(fmt, duration)
                d.update({
                    "format_id": fmt.get("format_id"),
                    "extension": fmt.get("ext") or "?",
                })
                processed.append(d)

            # Best quality first
            processed.sort(key=lambda f: f["sort_key"], reverse=True)

            print("STEP 5 : Scheduling UI update")
            Clock.schedule_once(
                lambda dt: self.on_done(info, processed)
            )
            print("FetchWorker completed successfully")

        except BaseException as e:

            print("=" * 60)
            print("FetchWorker FAILED")
            print("Exception Type :", type(e).__name__)
            print("Exception      :", repr(e))
            print("=" * 60)

            traceback.print_exc()
            error_message = str(e)
            def notify(dt):
                self.on_error(error_message)

            Clock.schedule_once(notify)

class Logger:
    def debug(self, msg):
        print("[DEBUG]", msg)

    def warning(self, msg):
        print("[WARNING]", msg)

    def error(self, msg):
        print("[ERROR]", msg)

class DownloadWorker(threading.Thread):
    def __init__(self, url, format_id, download_dir, on_progress, on_done, on_error):
        super().__init__(daemon=True)
        self.url = url
        self.format_id = format_id
        self.download_dir = download_dir
        self.on_progress = on_progress
        self.on_done = on_done
        self.on_error = on_error

    def progress_hook(self, d):
        if d["status"] != "downloading":
            return

        ansi = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
        percent_text = ansi.sub("", d.get("_percent_str", "0%"))
        match = re.search(r"(\d+(?:\.\d+)?)", percent_text)
        value = float(match.group(1)) if match else 0.0

        speed = ansi.sub("", d.get("_speed_str", ""))
        eta = ansi.sub("", d.get("_eta_str", ""))

        status = f"{value:.1f}%"
        if speed:
            status += f" - {speed}"
        if eta:
            status += f" - ETA {eta}"

        Clock.schedule_once(
            lambda dt: self.on_progress(value, status)
        )

    def run(self):
        try:
            print("=" * 80)
            print("DOWNLOAD STARTED")
            print("Platform     :", platform)
            print("Python       :", sys.version)
            print("yt-dlp       :", yt_dlp.version.__version__)
            print("URL          :", self.url)
            print("Format       :", self.format_id)
            print("Output Dir   :", self.download_dir)
            ffmpeg_path = get_ffmpeg_path()
            ffmpeg_loc = prepare_ffmpeg_location()
            print("ffmpeg path     :", ffmpeg_path)
            print("ffmpeg_location :", ffmpeg_loc)

            try:
                result = subprocess.run(
                    [ffmpeg_path, "-version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                print("RETURN CODE :", result.returncode)
                print(result.stdout)

            except Exception:
                traceback.print_exc()

            print("=" * 80)

            work_dir = get_temp_download_dir() if platform == "android" else self.download_dir
            print("Working Dir  :", work_dir)

            opts = {
                "format": self.format_id,
                "outtmpl": os.path.join(
                    work_dir,
                    "%(title)s.%(ext)s"
                ),

                "progress_hooks": [self.progress_hook],

                "windowsfilenames": platform == "win",
                "concurrent_fragment_downloads": 2,

                "retries": 20,
                "fragment_retries": 20,
                "socket_timeout": 30,

                # Same 'tv' client DRM workaround as FetchWorker - see the
                # comment there for details.
                "extractor_args": {
                    "youtube": {"player_client": ["default", "-tv"]}
                },

                # Android debugging
                "quiet": True,
                "no_warnings": True,
                "logger": Logger(),
            }
            if ffmpeg_loc:
                opts["ffmpeg_location"] = ffmpeg_loc

            print("Creating YoutubeDL...")
            ydl = yt_dlp.YoutubeDL(opts)

            print("ffmpeg_location =", ydl.params.get("ffmpeg_location"))

            print("Starting download...")
            before_files = set(os.listdir(work_dir))
            result = ydl.download([self.url])
            after_files = set(os.listdir(work_dir))
            new_files = sorted(after_files - before_files)

            print("Download finished.")
            print("Result:", result)
            print("New files:", new_files)

            if platform == "android":
                if not new_files:
                    raise RuntimeError("Download finished but no output file was found.")

                print("Publishing to public Downloads/Tubit...")
                published_any = False
                for fname in new_files:
                    local_path = os.path.join(work_dir, fname)
                    final_path = publish_to_public_downloads(local_path)
                    if final_path:
                        print(f"Published : {final_path}")
                        published_any = True
                    else:
                        print(f"Publish FAILED for {fname} (left in app-private storage)")

                if not published_any:
                    raise RuntimeError(
                        "Download finished but could not be saved to the public "
                        "Downloads folder."
                    )

            Clock.schedule_once(
                lambda dt: self.on_done()
            )

        except BaseException as e:
            print("=" * 80)
            print("DOWNLOAD FAILED")
            print("Exception:", repr(e))
            traceback.print_exc()
            print("=" * 80)

            error_message = str(e)
            def notify(dt):
                self.on_error(error_message)

            Clock.schedule_once(notify)