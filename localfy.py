import os
import io
from tkinter import *
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import pygame
from mutagen import File

APP_TITLE = "Localfy"
WINDOW_SIZE = "780x460"
COVER_SIZE = (220, 220)
SPOTIFY_GREEN = "#1DB954"
BG_DARK = "#191414"
BG_LIGHT = "#282828"
FG_TEXT = "#FFFFFF"
FG_SUB = "#B3B3B3"

def format_time(seconds):
    if seconds is None:
        return "0:00"
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"

class Song:
    def __init__(self, path):
        self.path = path
        self.title = os.path.basename(path)
        self.artist = "Unknown"
        self.album = "Unknown"
        self.length = 0
        self.cover_image_pil = None
        self._read_metadata()

    def _read_metadata(self):
        try:
            audio = File(self.path)
            if hasattr(audio.info, "length"):
                self.length = float(audio.info.length)
            tags = audio.tags
            if tags:
                if tags.get("TIT2"): self.title = tags["TIT2"].text[0]
                if tags.get("TPE1"): self.artist = tags["TPE1"].text[0]
                if tags.get("TALB"): self.album = tags["TALB"].text[0]
                apic = tags.get("APIC:") or tags.get("APIC")
                if not apic:
                    for k, v in tags.items():
                        if k.startswith("APIC"):
                            apic = v
                            break
                if apic:
                    img = Image.open(io.BytesIO(apic.data)).convert("RGBA")
                    self.cover_image_pil = img
        except:
            pass

class LocalfyPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.root.configure(bg=BG_DARK)

        pygame.mixer.init()

        self.songs = []
        self.filtered_songs = []
        self.current_index = None
        self.playing = False
        self.seek_dragging = False
        self.seek_offset = 0.0

        self._style_widgets()
        self._build_ui()
        self._start_update_loop()

    def _style_widgets(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TScale",
                        background=BG_DARK,
                        troughcolor=BG_LIGHT,
                        sliderlength=12,
                        sliderthickness=12)
        style.configure("Seek.Horizontal.TScale",
                        troughcolor=BG_LIGHT,
                        sliderlength=16,
                        sliderthickness=14,
                        background=BG_DARK)
        style.map("Seek.Horizontal.TScale",
                  background=[("active", BG_DARK)],
                  troughcolor=[("active", BG_LIGHT)])
        style.configure("Volume.Horizontal.TScale",
                        troughcolor=BG_LIGHT,
                        sliderlength=12,
                        sliderthickness=10,
                        background=BG_DARK)
        style.map("Volume.Horizontal.TScale",
                  background=[("active", BG_DARK)],
                  troughcolor=[("active", BG_LIGHT)])

    def _build_ui(self):
        main_frame = Frame(self.root, bg=BG_DARK)
        main_frame.pack(fill=BOTH, expand=True, padx=12, pady=12)

        left_frame = Frame(main_frame, bg=BG_DARK)
        left_frame.pack(side=LEFT, fill=BOTH, expand=False)

        self.cover_label = Label(left_frame, bg=BG_DARK)
        self.cover_label.pack(pady=(0, 8))
        self._set_cover_image(None)

        self.title_var = StringVar(value="—")
        self.artist_var = StringVar(value="—")
        Label(left_frame, textvariable=self.title_var,
              fg=FG_TEXT, bg=BG_DARK, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        Label(left_frame, textvariable=self.artist_var,
              fg=FG_SUB, bg=BG_DARK, font=("Segoe UI", 11)).pack(anchor="w")

        self.seek_var = ttk.Scale(left_frame, from_=0, to=100,
                                  orient=HORIZONTAL, style="Seek.Horizontal.TScale")
        self.seek_var.pack(fill="x", pady=(12, 4))
        self.seek_var.bind("<Button-1>", self._start_seek)
        self.seek_var.bind("<B1-Motion>", self._seek_drag)
        self.seek_var.bind("<ButtonRelease-1>", self._commit_seek)

        time_frame = Frame(left_frame, bg=BG_DARK)
        time_frame.pack(fill="x")
        self.time_cur_var = StringVar(value="0:00")
        self.time_tot_var = StringVar(value="0:00")
        Label(time_frame, textvariable=self.time_cur_var,
              fg=FG_SUB, bg=BG_DARK).pack(side=LEFT)
        Label(time_frame, textvariable=self.time_tot_var,
              fg=FG_SUB, bg=BG_DARK).pack(side=RIGHT)

        controls = Frame(left_frame, bg=BG_DARK)
        controls.pack(pady=8)
        Button(controls, text="⏮", command=self.prev_song,
               font=("Segoe UI", 12), bg=SPOTIFY_GREEN, fg="black",
               width=4).pack(side=LEFT, padx=4)
        self.btn_play = Button(controls, text="▶", command=self.play_pause,
                               font=("Segoe UI", 12), bg=SPOTIFY_GREEN, fg="black",
                               width=4)
        self.btn_play.pack(side=LEFT, padx=4)
        Button(controls, text="⏭", command=self.next_song,
               font=("Segoe UI", 12), bg=SPOTIFY_GREEN, fg="black",
               width=4).pack(side=LEFT, padx=4)

        self.volume_slider = ttk.Scale(left_frame, from_=0, to=100,
                                       orient=HORIZONTAL, style="Volume.Horizontal.TScale",
                                       command=self._on_volume_change)
        self.volume_slider.set(80)
        self.volume_slider.pack(fill="x", pady=(8, 0))

        right_frame = Frame(main_frame, bg=BG_DARK)
        right_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(12, 0))

        search_frame = Frame(right_frame, bg=BG_DARK)
        search_frame.pack(fill="x", pady=(0, 6))
        Label(search_frame, text="Search:", fg=FG_TEXT, bg=BG_DARK).pack(side=LEFT, padx=(0, 4))
        self.search_var = StringVar()
        search_entry = Entry(search_frame, textvariable=self.search_var, bg=BG_LIGHT, fg=FG_TEXT, insertbackground=FG_TEXT)
        search_entry.pack(fill="x", expand=True)
        search_entry.bind("<KeyRelease>", self._filter_songs)

        self.playlist_box = Listbox(right_frame, bg=BG_LIGHT, fg=FG_TEXT,
                                    selectbackground=SPOTIFY_GREEN, activestyle="none")
        self.playlist_box.pack(fill=BOTH, expand=True)
        self.playlist_box.bind("<Double-Button-1>", self._on_playlist_double)

        btn_frame = Frame(right_frame, bg=BG_DARK)
        btn_frame.pack(fill="x", pady=(8, 0))
        Button(btn_frame, text="Open Files", command=self.add_files,
               bg=SPOTIFY_GREEN, fg="black").pack(side=LEFT, padx=4)
        Button(btn_frame, text="Add Folder", command=self.add_folder,
               bg=SPOTIFY_GREEN, fg="black").pack(side=LEFT, padx=4)

    def _filter_songs(self, _=None):
        query = self.search_var.get().lower()
        self.playlist_box.delete(0, END)
        self.filtered_songs = []
        for idx, s in enumerate(self.songs):
            if query in s.title.lower() or query in s.artist.lower():
                self.playlist_box.insert(END, f"{s.title} — {s.artist}")
                self.filtered_songs.append(idx)

    def _set_cover_image(self, pil_img):
        if pil_img is None:
            pil_img = Image.new("RGBA", COVER_SIZE, BG_LIGHT)
        else:
            pil_img = pil_img.copy()
            pil_img.thumbnail(COVER_SIZE, Image.LANCZOS)
        tkimg = ImageTk.PhotoImage(pil_img)
        self.cover_label.config(image=tkimg)
        self.cover_label.image = tkimg

    def add_files(self):
        files = filedialog.askopenfilenames(filetypes=[("MP3 files", "*.mp3")])
        for f in files:
            self._add_song(f)
        self._filter_songs()

    def add_folder(self):
        folder = filedialog.askdirectory()
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(".mp3"):
                    self._add_song(os.path.join(root, f))
        self._filter_songs()

    def _add_song(self, path):
        s = Song(path)
        self.songs.append(s)
        self.playlist_box.insert(END, f"{s.title} — {s.artist}")
        if self.current_index is None:
            self.current_index = 0
            self._display_song(0)

    def _display_song(self, idx):
        s = self.songs[idx]
        self.title_var.set(s.title)
        self.artist_var.set(s.artist)
        self.time_tot_var.set(format_time(s.length))
        try:
            self.seek_var.config(to=max(1, s.length))
        except Exception:
            self.seek_var.config(to=100)
        self._set_cover_image(s.cover_image_pil)

    def _on_playlist_double(self, _):
        sel = self.playlist_box.curselection()
        if sel:
            actual_idx = self.filtered_songs[sel[0]] if self.search_var.get() else sel[0]
            self.play_song_at_index(actual_idx)

    def _start_seek(self, event):
        self.seek_dragging = True

    def _seek_drag(self, event):
        try:
            self.time_cur_var.set(format_time(self.seek_var.get()))
        except Exception:
            pass

    def _commit_seek(self, event):
        if self.current_index is not None:
            pos = float(self.seek_var.get())
            self.seek_offset = pos
            try:
                pygame.mixer.music.play(start=pos)
            except TypeError:
                pygame.mixer.music.play()
                try:
                    pygame.mixer.music.set_pos(pos)
                except Exception:
                    pass
            self.playing = True
            self.btn_play.config(text="⏸")
        self.seek_dragging = False

    def play_song_at_index(self, idx, start=0):
        self.current_index = idx
        self.seek_offset = float(start or 0)
        s = self.songs[idx]
        pygame.mixer.music.load(s.path)
        try:
            pygame.mixer.music.play(start=start)
        except TypeError:
            pygame.mixer.music.play()
            try:
                pygame.mixer.music.set_pos(start)
            except Exception:
                pass
        self.playing = True
        self.btn_play.config(text="⏸")
        self._display_song(idx)

    def play_pause(self):
        if not self.songs:
            return
        if not pygame.mixer.music.get_busy() and not self.playing:
            self.play_song_at_index(self.current_index or 0, start=self.seek_offset)
        elif self.playing:
            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms != -1:
                self.seek_offset += pos_ms / 1000.0
            pygame.mixer.music.pause()
            self.playing = False
            self.btn_play.config(text="▶")
        else:
            self.play_song_at_index(self.current_index or 0, start=self.seek_offset)

    def next_song(self):
        if not self.songs:
            return
        self.play_song_at_index((self.current_index + 1) % len(self.songs))

    def prev_song(self):
        if not self.songs:
            return
        self.play_song_at_index((self.current_index - 1) % len(self.songs))

    def _on_volume_change(self, _):
        pygame.mixer.music.set_volume(self.volume_slider.get() / 100)

    def _start_update_loop(self):
        def loop():
            if self.current_index is not None:
                pos_ms = pygame.mixer.music.get_pos()
                if pos_ms < 0:
                    if self.playing:
                        self.next_song()
                else:
                    pos = pos_ms / 1000.0
                    current_time = self.seek_offset + pos
                    try:
                        song_len = self.songs[self.current_index].length
                        if song_len and current_time > song_len:
                            current_time = song_len
                    except Exception:
                        pass
                    if not self.seek_dragging and self.playing:
                        try:
                            self.seek_var.set(current_time)
                        except Exception:
                            pass
                        try:
                            self.time_cur_var.set(format_time(current_time))
                        except Exception:
                            pass
            self.root.after(250, loop)
        loop()

if __name__ == "__main__":
    root = Tk()
    app = LocalfyPlayer(root)
    root.mainloop()
