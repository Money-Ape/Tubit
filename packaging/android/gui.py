import os
from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.uix.behaviors import ToggleButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import AsyncImage, Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex, platform
from theme import THEMES
from backend import resource_path, get_download_dir, FetchWorker, DownloadWorker

THEME = THEMES["blue_gray"]
SELECTED_CARD_BG = "#25344A"

STATUS_COLORS = {
    "info": THEME["accent"],
    "success": THEME["success"],
    "warning": THEME["warning"],
    "error": THEME["danger"],
}

FORMAT_MODE_COLORS = {
    "video": THEME["accent"],
    "video_only": THEME["warning"],
    "audio_only": THEME["success"],
}

# ==================================================
# Small helpers
# ==================================================
def section_title(text, size=15):
    return Label(
        text=f"[b]{text}[/b]", markup=True, font_size=dp(size),
        halign="left", valign="middle", size_hint_y=None, height=dp(24),
        color=get_color_from_hex(THEME["text"]),
    )

def empty_state(text, height=180):
    """Centered placeholder shown while a list has nothing to display yet,
    instead of leaving a large blank gap."""
    box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(height),
                     padding=(dp(20), 0))
    lbl = Label(
        text=text, font_size=dp(12.5), halign="center", valign="middle",
        color=get_color_from_hex(THEME["subtext"]),
    )
    lbl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
    box.add_widget(lbl)
    return box

def subtext_label(text, size=11, height=20, markup=False):
    lbl = Label(
        text=text, font_size=dp(size), halign="left", valign="middle",
        size_hint_y=None, height=dp(height), markup=markup,
        color=get_color_from_hex(THEME["subtext"]),
    )
    lbl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
    return lbl

# ==================================================
# Themed UI primitives
# ==================================================
class Card(BoxLayout):
    """A BoxLayout with a rounded, themed background + border, plus an
    optional soft drop-shadow for a bit of depth.

    Pass no_border=True for a flat card with no outline (pills, dividers,
    badges) - explicit flag instead of overloading border=None, since
    None already means "use the default theme border"."""

    def __init__(self, bg=None, border=None, radius=16, border_width=1.2,
                 shadow=True, no_border=False, **kwargs):
        super().__init__(**kwargs)
        self._radius = radius
        bg = bg or THEME["workspace"]
        border = None if no_border else (border or THEME["border"])

        with self.canvas.before:
            if shadow:
                Color(0, 0, 0, 0.30)
                self._shadow_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            else:
                self._shadow_rect = None

            self._bg_color = Color(*get_color_from_hex(bg))
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            self._border_color = Color(*get_color_from_hex(border)) if border else Color(0, 0, 0, 0)
            self._border_line = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, radius),
                width=border_width,
            )
        self.bind(pos=self._update, size=self._update)

    def _update(self, *_):
        if self._shadow_rect:
            self._shadow_rect.pos = (self.x - dp(1), self.y - dp(3))
            self._shadow_rect.size = self.size
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._border_line.rounded_rectangle = (self.x, self.y, self.width, self.height, self._radius)

    def set_bg(self, hex_color):
        self._bg_color.rgba = get_color_from_hex(hex_color)

    def set_border(self, hex_color):
        self._border_color.rgba = get_color_from_hex(hex_color)

    def animate_bg(self, hex_color, duration=0.15):
        Animation.cancel_all(self._bg_color, "rgba")
        Animation(rgba=get_color_from_hex(hex_color), duration=duration, t="out_quad").start(self._bg_color)

    def animate_border(self, hex_color, duration=0.15):
        Animation.cancel_all(self._border_color, "rgba")
        Animation(rgba=get_color_from_hex(hex_color), duration=duration, t="out_quad").start(self._border_color)

class AnimatedButton(Button):
    """Flat button with a soft press-darken animation and a helper to
    smoothly re-theme it (color + label) in one call. Only animates the
    button's own background_color property - a plain Kivy ListProperty,
    no canvas/texture tricks involved."""

    def __init__(self, **kwargs):
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        super().__init__(**kwargs)
        self._base_color = list(self.background_color)
        self.bind(on_press=self._on_press, on_release=self._on_release)

    def _on_press(self, *_):
        Animation.cancel_all(self, "background_color")
        darker = [c * 0.85 for c in self._base_color[:3]] + [self._base_color[3] if len(self._base_color) > 3 else 1]
        Animation(background_color=darker, duration=0.08).start(self)

    def _on_release(self, *_):
        Animation.cancel_all(self, "background_color")
        Animation(background_color=self._base_color, duration=0.18, t="out_quad").start(self)

    def set_style(self, bg_hex, color_hex, disabled=None):
        self._base_color = get_color_from_hex(bg_hex)
        Animation.cancel_all(self, "background_color")
        Animation(background_color=self._base_color, duration=0.2, t="out_quad").start(self)
        self.color = get_color_from_hex(color_hex)
        if disabled is not None:
            self.disabled = disabled

class RoundedProgressBar(Widget):
    """Rounded progress bar that eases smoothly toward each new value
    instead of snapping. Uses a plain NumericProperty so Animation and
    redraw-on-change both work through the standard property system."""

    value = NumericProperty(0)

    def __init__(self, maximum=100, **kwargs):
        super().__init__(**kwargs)
        self.maximum = maximum
        with self.canvas:
            self._bg_color = Color(*get_color_from_hex(THEME["interactive"]))
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[8])
            self._chunk_color = Color(*get_color_from_hex(THEME["accent"]))
            self._chunk_rect = RoundedRectangle(pos=self.pos, size=(0, self.height), radius=[8])
        self.bind(pos=self._redraw, size=self._redraw, value=self._redraw)

    def _redraw(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        ratio = (self.value / self.maximum) if self.maximum else 0
        w = max(0, min(self.width, self.width * ratio))
        self._chunk_rect.pos = self.pos
        self._chunk_rect.size = (w, self.height)

    def set_value(self, value, animate=True):
        value = max(0, min(value, self.maximum))
        Animation.cancel_all(self, "value")
        if animate:
            Animation(value=value, duration=0.25, t="out_quad").start(self)
        else:
            self.value = value

# ==================================================
# Format card
# ==================================================
class FormatCard(ToggleButtonBehavior, Card):
    def __init__(self, fmt, mode, on_select, **kwargs):
        super().__init__(
            group="formats", orientation="vertical",
            padding=(dp(12), dp(10)), spacing=dp(2),
            size_hint=(1, None), height=dp(96),
            bg=THEME["workspace"], border=THEME["border"], radius=14, shadow=False,
            **kwargs,
        )
        self.fmt = fmt
        self.on_select_cb = on_select

        dot_color = FORMAT_MODE_COLORS.get(mode, THEME["accent"])
        top_row = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(6))
        dot = Label(
            text="\u25CF", font_size=dp(11), size_hint_x=None, width=dp(12),
            halign="left", valign="middle", color=get_color_from_hex(dot_color),
        )
        quality = Label(
            text=f"[b]{fmt['quality']} \u2022 {fmt['extension']}[/b]", markup=True,
            font_size=dp(14), halign="left", valign="middle",
            shorten=True, shorten_from="right",
            color=get_color_from_hex(THEME["text"]),
        )
        quality.bind(size=lambda w, *_: setattr(w, "text_size", w.size))

        self.check_label = Label(
            text="", markup=True, font_size=dp(14), bold=True,
            size_hint_x=None, width=dp(18), halign="right", valign="middle",
            color=get_color_from_hex(THEME["accent"]),
        )
        top_row.add_widget(dot)
        top_row.add_widget(quality)
        top_row.add_widget(self.check_label)

        codec = Label(
            text=fmt.get("codec") or "Unknown", font_size=dp(11),
            halign="left", valign="middle", size_hint_y=None, height=dp(16),
            color=get_color_from_hex(THEME["subtext"]),
        )
        codec.bind(size=lambda w, *_: setattr(w, "text_size", w.size))

        size_lbl = Label(
            text=fmt["size"], font_size=dp(12), halign="left", valign="middle",
            size_hint_y=None, height=dp(18),
            color=get_color_from_hex(THEME["accent"]), bold=True,
        )
        size_lbl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))

        self.add_widget(top_row)
        self.add_widget(codec)
        self.add_widget(Widget())  # stretch
        self.add_widget(size_lbl)

    def on_state(self, widget, value):
        if not hasattr(self, "_bg_color"):
            # Guard against Kivy dispatching on_state from inside super().__init__()
            # (happens if state is ever passed as a constructor kwarg) before the
            # canvas instructions created in Card.__init__ exist yet.
            return
        if value == "down":
            self.animate_bg(SELECTED_CARD_BG)
            self.animate_border(THEME["accent"])
            self.check_label.text = "[color=#58A6FF]\u2713[/color]"
            self.on_select_cb(self.fmt)
        else:
            self.animate_bg(THEME["workspace"])
            self.animate_border(THEME["border"])
            self.check_label.text = ""

class FilterButton(ToggleButtonBehavior, Card):
    """Pill segment inside the format-type switcher."""

    def __init__(self, text="", **kwargs):
        super().__init__(
            orientation="horizontal", padding=(dp(8), dp(4)), spacing=dp(6),
            bg=THEME["interactive"], no_border=True, radius=9, shadow=False,
            **kwargs,
        )
        self.label = Label(
            text=text, font_size=dp(12), bold=True,
            halign="center", valign="middle",
            color=get_color_from_hex(THEME["subtext"]),
        )
        self.label.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        self.add_widget(self.label)

    def on_state(self, widget, value):
        if not hasattr(self, "_bg_color"):
            # Same guard as FormatCard.on_state - see comment there.
            return
        if value == "down":
            self.animate_bg(THEME["accent"])
            Animation.cancel_all(self.label, "color")
            Animation(color=get_color_from_hex("#FFFFFF"), duration=0.15).start(self.label)
        else:
            self.animate_bg(THEME["interactive"])
            Animation.cancel_all(self.label, "color")
            Animation(color=get_color_from_hex(THEME["subtext"]), duration=0.15).start(self.label)

# ==================================================
# Root layout
# ==================================================
class TubitRoot(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(16), spacing=dp(14), **kwargs)
        Window.clearcolor = get_color_from_hex(THEME["window"])

        self.download_dir = get_download_dir()
        self.all_formats = []
        self.selected_format = None
        self.video_info = None
        self.format_mode = "video"

        scroll = ScrollView(size_hint=(1, 1), bar_width=0,
                             bar_color=(0, 0, 0, 0), bar_inactive_color=(0, 0, 0, 0))
        self.content = BoxLayout(orientation="vertical", spacing=dp(14), size_hint_y=None, padding=(0, 0, 0, dp(8)))
        self.content.bind(minimum_height=self.content.setter("height"))
        scroll.add_widget(self.content)
        self.add_widget(scroll)

        self._build_header()
        self._build_url_card()
        self._build_formats_card()
        self._build_info_card()
        self._build_download_card()
        self._build_footer()

    # ---------- header ----------
    def _build_header(self):
        header = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(78), spacing=dp(10))
        top = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(12))

        icon_path = resource_path(os.path.join("assets", "Tubit.png"))
        if os.path.exists(icon_path):
            logo = Image(source=icon_path, size_hint=(None, None), size=(dp(56), dp(56)))
        else:
            logo = Card(bg=THEME["accent"], no_border=True, radius=16, shadow=False,
                        size_hint=(None, None), size=(dp(56), dp(56)))
            logo.add_widget(Label(text="[b]T[/b]", markup=True, font_size=dp(26),
                                   color=get_color_from_hex("#FFFFFF")))
        top.add_widget(logo)

        title_box = BoxLayout(orientation="vertical", spacing=dp(2))
        title_row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(8))
        title = Label(
            text="[b]TUBIT: Video Downloader[/b]", markup=True, font_size=dp(20),
            halign="left", valign="bottom", size_hint_x=1,
            color=get_color_from_hex(THEME["text"]),
        )
        title.bind(size=lambda w, *_: setattr(w, "text_size", w.size))

        version_badge = Card(bg=THEME["interactive"], no_border=True, radius=8, shadow=False,
                              size_hint=(None, None), size=(dp(46), dp(22)))
        version_badge.add_widget(Label(text="v1.6", font_size=dp(10), bold=True,
                                        color=get_color_from_hex(THEME["subtext"])))

        title_row.add_widget(title)
        title_row.add_widget(version_badge)

        subtitle = subtext_label("YouTube | Instagram \u2022 Fast \u2022 Simple \u2022 Reliable",
                                  size=11, height=22)

        title_box.add_widget(title_row)
        title_box.add_widget(subtitle)
        top.add_widget(title_box)
        header.add_widget(top)

        divider = Card(bg=THEME["accent"], no_border=True, radius=2, shadow=False,
                        size_hint_y=None, height=dp(2))
        header.add_widget(divider)

        self.content.add_widget(header)

    # ---------- URL card ----------
    def _build_url_card(self):
        card = Card(orientation="vertical", padding=dp(16), spacing=dp(10), size_hint_y=None)
        card.bind(minimum_height=card.setter("height"))
        self.url_card = card

        card.add_widget(section_title("URL (YouTube | Instagram)", size=13))

        input_wrap = Card(bg=THEME["interactive"], border=THEME["border"], radius=12,
                           shadow=False, size_hint_y=None, height=dp(48), padding=(dp(2), dp(2)))
        self.url_entry = TextInput(
            hint_text="Paste a video URL here...", multiline=False,
            background_normal="", background_active="", background_color=(0, 0, 0, 0),
            foreground_color=get_color_from_hex(THEME["text"]),
            hint_text_color=get_color_from_hex(THEME["subtext"]),
            cursor_color=get_color_from_hex(THEME["accent"]),
            padding=[dp(12), dp(14), dp(12), 0],
            font_size=dp(13),
        )
        self.url_entry.bind(text=lambda *_: self._on_url_text_changed())
        input_wrap.add_widget(self.url_entry)

        self.fetch_btn = AnimatedButton(
            text="Fetch Available Formats", size_hint_y=None, height=0, opacity=0,
            background_color=get_color_from_hex(THEME["interactive"]),
            color=get_color_from_hex(THEME["subtext"]), bold=True,
            disabled=True,
        )
        self.fetch_btn.bind(on_release=lambda *_: self.fetch_formats())

        card.add_widget(input_wrap)
        card.add_widget(self.fetch_btn)
        self.content.add_widget(card)

    def _on_url_text_changed(self):
        has_text = bool(self.url_entry.text.strip())
        self._set_collapsed(self.fetch_btn, not has_text, dp(46))
        if has_text:
            self.fetch_btn.set_style(THEME["accent"], "#FFFFFF", disabled=False)
        else:
            self.fetch_btn.set_style(THEME["interactive"], THEME["subtext"], disabled=True)
            if hasattr(self, "video_title"):
                self.video_title.text = "No video loaded"
                self.video_channel.text = "Channel : ---"
                self.video_duration.text = "Duration : --:--"
                self.thumbnail.source = ""

    # ---------- formats card ----------
    def _build_formats_card(self):
        card = Card(orientation="vertical", padding=dp(16), spacing=dp(10),
                    size_hint_y=None, height=dp(436))

        header_row = BoxLayout(size_hint_y=None, height=dp(24))
        header_row.add_widget(section_title("Available Formats", size=13))
        self.format_count = Label(
            text="0", size_hint_x=None, width=dp(30), font_size=dp(12), bold=True,
            color=get_color_from_hex(THEME["accent"]),
        )
        header_row.add_widget(self.format_count)
        card.add_widget(header_row)

        filter_track = Card(bg=THEME["window"], border=THEME["border"], radius=12, shadow=False,
                             size_hint_y=None, height=dp(42), padding=dp(4), spacing=dp(6))
        self.video_btn = FilterButton(text="Video", group="mode")
        self.video_only_btn = FilterButton(text="Video Only", group="mode")
        self.audio_only_btn = FilterButton(text="Audio Only", group="mode")
        for btn in (self.video_btn, self.video_only_btn, self.audio_only_btn):
            btn.bind(on_release=lambda *_: self.filter_formats())
            filter_track.add_widget(btn)
        card.add_widget(filter_track)

        # Set the default-active pill only after every FilterButton is fully
        # constructed (canvas instructions included) - see the on_state guard
        # comment on FilterButton for why this can't be a constructor kwarg.
        self.video_btn.state = "down"

        scroll = ScrollView(size_hint=(1, 1), bar_width=0,
                            bar_color=(0, 0, 0, 0), bar_inactive_color=(0, 0, 0, 0))
        self.grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, padding=(0, dp(4)))
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll.add_widget(self.grid)
        card.add_widget(scroll)

        self.content.add_widget(card)

        # Nice centered placeholder instead of a blank card until a video
        # is actually fetched.
        self._show_formats_placeholder("Paste a URL above and fetch\nto see available formats.")

    def _show_formats_placeholder(self, text):
        self.grid.clear_widgets()
        self.grid.cols = 1
        self.grid.add_widget(empty_state(text))

    # ---------- video info card ----------
    def _build_info_card(self):
        card = Card(orientation="vertical", padding=dp(16), spacing=dp(8),
                    size_hint_y=None, height=dp(154))

        card.add_widget(section_title("Video insights", size=13))

        info_row = BoxLayout(spacing=dp(12))
        thumb_wrap = Card(bg=THEME["interactive"], border=THEME["border"], radius=10, shadow=False,
                           size_hint_x=None, width=dp(124), padding=dp(2))
        thumb_inner = FloatLayout()
        self.thumbnail_placeholder = Label(
            text="No\nPreview", font_size=dp(11), halign="center", valign="middle",
            size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            color=get_color_from_hex(THEME["subtext"]),
        )
        self.thumbnail_placeholder.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        self.thumbnail = AsyncImage(
            allow_stretch=True, keep_ratio=True, opacity=0,
            size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
        )
        self.thumbnail.bind(source=self._on_thumbnail_source_changed)
        thumb_inner.add_widget(self.thumbnail_placeholder)
        thumb_inner.add_widget(self.thumbnail)
        thumb_wrap.add_widget(thumb_inner)

        details = BoxLayout(orientation="vertical", spacing=dp(5))
        self.video_title = Label(
            text="No video loaded", font_size=dp(14), bold=True,
            halign="left", valign="top",
            color=get_color_from_hex(THEME["text"]),
        )
        self.video_title.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        self.video_channel = subtext_label("Channel : ---", size=11, height=18)
        self.video_duration = subtext_label("Duration : --:--", size=11, height=18)

        details.add_widget(self.video_title)
        details.add_widget(self.video_channel)
        details.add_widget(self.video_duration)

        info_row.add_widget(thumb_wrap)
        info_row.add_widget(details)
        card.add_widget(info_row)

        self.content.add_widget(card)

    # ---------- download card ----------
    def _build_download_card(self):
        card = Card(orientation="vertical", padding=dp(16), spacing=dp(8), size_hint_y=None)
        card.bind(minimum_height=card.setter("height"))

        card.add_widget(section_title("Download", size=13))

        card.add_widget(subtext_label("Selected Format", size=10, height=16))
        self.selected_format_label = Label(
            text="No Format Selected", font_size=dp(14), bold=True,
            halign="left", valign="middle", size_hint_y=None, height=dp(22),
            color=get_color_from_hex(THEME["text"]),
        )
        self.selected_format_label.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        card.add_widget(self.selected_format_label)

        self.download_btn = AnimatedButton(
            text="Download", size_hint_y=None, height=0, opacity=0, disabled=True,
            background_color=get_color_from_hex(THEME["interactive"]),
            color=get_color_from_hex(THEME["subtext"]), bold=True,
        )
        self.download_btn.bind(on_release=lambda *_: self.download_video())
        card.add_widget(self.download_btn)

        card.add_widget(subtext_label("Save", size=10, height=16))
        self.loc_label = Label(
            text=self.download_dir, font_size=dp(11), halign="left", valign="middle",
            size_hint_y=None, height=dp(20),
            color=get_color_from_hex(THEME["subtext"]),
        )
        self.loc_label.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        card.add_widget(self.loc_label)

        self.progress = RoundedProgressBar(maximum=100, size_hint_y=None, height=dp(14))
        card.add_widget(self.progress)

        self.status_label = subtext_label("", size=11, height=18, markup=True)
        card.add_widget(self.status_label)
        self._set_status("Select a format to continue.", "info")

        self.content.add_widget(card)

    # ---------- footer ----------
    def _build_footer(self):
        footer = subtext_label(
            "Powered by [color=58A6FF]yt-dlp[/color] & [color=58A6FF]ffmpeg[/color]",
            size=10, height=24, markup=True,
        )
        footer.halign = "center"
        footer.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        self.content.add_widget(footer)

    # ==================================================
    # Status helper
    # ==================================================
    def _set_status(self, text, kind="info"):
        color = STATUS_COLORS.get(kind, THEME["accent"])
        self.status_label.text = f"[color={color}]\u25CF[/color]  {text}"

    @staticmethod
    def _set_collapsed(widget, collapsed, expanded_height):
        """Show/hide a widget by animating its height to 0 (rather than just
        disabling it) so the surrounding card shrinks/grows around it instead
        of leaving a dead, disabled-looking button in place."""
        widget.size_hint_y = None
        target = 0 if collapsed else expanded_height
        Animation.cancel_all(widget, "height", "opacity")
        Animation(height=target, opacity=0 if collapsed else 1,
                  duration=0.15, t="out_quad").start(widget)

    def _on_thumbnail_source_changed(self, widget, value):
        has_source = bool(value)
        widget.opacity = 1 if has_source else 0
        self.thumbnail_placeholder.opacity = 0 if has_source else 1

    # ==================================================
    # Behaviour
    # ==================================================
    def fetch_formats(self):
        url = self.url_entry.text.strip()
        if not url:
            return

        self.fetch_btn.set_style(THEME["interactive"], THEME["subtext"], disabled=True)
        self.fetch_btn.text = "Fetching..."
        FetchWorker(url, self.populate_formats, self.on_error).start()

    def populate_formats(self, info, formats):
        self.all_formats = formats
        self.video_info = info

        self.fetch_btn.text = "Fetch Available Formats"
        self._on_url_text_changed()

        self.video_title.text = info.get("title", "Unknown")
        self.video_channel.text = f"Channel : {info.get('uploader', 'Unknown')}"
        self.video_duration.text = f"Duration : {info.get('duration_string', '--:--')}"
        self.thumbnail.source = info.get("thumbnail", "")

        self.selected_format = None
        self.selected_format_label.text = "No Format Selected"
        self.download_btn.set_style(THEME["interactive"], THEME["subtext"], disabled=True)
        self._set_collapsed(self.download_btn, True, dp(46))
        self._set_status("Select a format to continue.", "info")

        self.filter_formats()

    def filter_formats(self):
        self.grid.clear_widgets()
        self.selected_format = None
        self.selected_format_label.text = "No Format Selected"
        self.download_btn.set_style(THEME["interactive"], THEME["subtext"], disabled=True)
        self._set_collapsed(self.download_btn, True, dp(46))

        if self.video_btn.state == "down":
            self.format_mode = "video"
            visible = [f for f in self.all_formats if f["has_video"]]
        elif self.video_only_btn.state == "down":
            self.format_mode = "video_only"
            visible = [f for f in self.all_formats if f["has_video"] and not f["has_audio"]]
        else:
            self.format_mode = "audio_only"
            visible = [f for f in self.all_formats if f["has_audio"] and not f["has_video"]]

        self.format_count.text = str(len(visible))

        if not visible:
            self.grid.cols = 1
            self.grid.add_widget(empty_state("No formats available for this filter."))
            return

        self.grid.cols = 2
        for fmt in visible:
            card = FormatCard(fmt, self.format_mode, self.select_format, size_hint_x=0.5)
            self.grid.add_widget(card)

    def select_format(self, fmt):
        self.selected_format = fmt
        self.selected_format_label.text = f"\u2713 {fmt['quality']} \u2022 {fmt['extension']} \u2022 {fmt['size']}"
        self.download_btn.set_style(THEME["accent"], "#FFFFFF", disabled=False)
        self._set_collapsed(self.download_btn, False, dp(46))

    def download_video(self):
        if not self.selected_format:
            return

        self.download_btn.set_style(THEME["interactive"], THEME["subtext"], disabled=True)
        self.fetch_btn.disabled = True
        self.progress.set_value(0, animate=False)
        self._set_status("Starting download...", "info")
        url = self.url_entry.text.strip()

        # --------------------------------------------
        # Build the format string
        # --------------------------------------------
        if self.format_mode == "video":
            if self.selected_format.get("has_audio") and self.selected_format.get("audio_known", True):
                # Already contains audio - don't merge a second track
                format_id = self.selected_format["format_id"]
            else:
                format_id = f"{self.selected_format['format_id']}+bestaudio/best"

        elif self.format_mode == "video_only":
            format_id = self.selected_format["format_id"]

        else:   # Audio Only
            format_id = self.selected_format["format_id"]

        DownloadWorker(
            url,
            format_id,
            self.download_dir,
            self.update_progress,
            self.download_complete,
            self.on_error,
        ).start()

    def update_progress(self, value, status):
        self.progress.set_value(value)
        self._set_status(status, "info")

    def download_complete(self):
        self.progress.set_value(100)
        self.download_btn.set_style(THEME["accent"], "#FFFFFF", disabled=False)
        self.fetch_btn.disabled = False
        self._on_url_text_changed()
        self._set_status(f"Saved to {self.download_dir}", "success")
        Clock.schedule_once(lambda dt: self.progress.set_value(0), 1.5)

    def on_error(self, message):
        self.fetch_btn.disabled = False
        self._on_url_text_changed()
        self.fetch_btn.text = "Fetch Available Formats"
        self.download_btn.disabled = False
        self._set_status(f"Error: {message}", "error")

class TubitApp(App):
    def build(self):
        self.title = "Tubit"
        return TubitRoot()