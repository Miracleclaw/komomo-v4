import pluggy
import tkinter as tk
from tkinter import scrolledtext, font
import threading
import queue
import time
import os
import sys
import re

hookimpl = pluggy.HookimplMarker("komomo")

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.getcwd()
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

class GUIPlugin:
    def __init__(self, config, system):
        self.config = config
        self.pm = None
        self.root = None
        self.msg_queue = queue.Queue()
        self.is_running = True
        self.assets = {} 
        self.is_log_visible = False
        self.is_recording_ui = False
        self.lyric_win = None
        
        self.WIN_W = 480
        self.WIN_H_STARTUP = 640   
        self.WIN_H_EXPANDED = 920

        self.colors = {
            "bg": "#FFF0F5",
            "fg_text": "#555555",
            "status_fg": "#4169E1",
            "input_bg": "#FFFFFF",
            "log_bg": "#FFFFFF",
            "user_text": "#4169E1",
            "bot_text": "#D2691E",
        }

    def on_plugin_loaded(self, pm):
        self.pm = pm
        self.gui_thread = threading.Thread(target=self._run_gui, daemon=True)
        self.gui_thread.start()

    @hookimpl(tryfirst=True)
    def on_query_received(self, text: str):
        self.msg_queue.put(("rec_state", False))
        self.msg_queue.put(("user", text))
        self.msg_queue.put(("status", "思考中... 🤔"))

    @hookimpl
    def on_llm_response_generated(self, response_text: str):
        if response_text.startswith("Lyric:"):
            lyrics = response_text.replace("Lyric:", "").strip()
            self.msg_queue.put(("lyrics", lyrics))
        elif response_text.startswith("ID:"):
            pass
        else:
            self.msg_queue.put(("bot", response_text))
            self.msg_queue.put(("status", "おしゃべり中 🗣️"))

    def _run_gui(self):
        self.root = tk.Tk()
        self.VERSION = "v4.1.9"
        self._update_title()
        self.root.geometry(f"{self.WIN_W}x{self.WIN_H_STARTUP}")
        self.root.configure(bg=self.colors["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.main_font = font.Font(family="Meiryo", size=9)
        self.status_font = font.Font(family="Meiryo", size=11, weight="bold")
        self.header_font = font.Font(family="Meiryo", size=11, weight="bold")
        self.small_font = font.Font(family="Meiryo", size=8)

        self._load_assets()
        if "icon" in self.assets: self.root.iconphoto(False, self.assets["icon"])

        # フッター・設定ボタン
        self.footer_frame = tk.Frame(self.root, bg=self.colors["bg"])
        self.footer_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        btn_conf = tk.Button(self.footer_frame, command=self._request_settings, bg=self.colors["bg"], 
                               relief="flat", bd=0, activebackground=self.colors["bg"])
        if "gear" in self.assets: btn_conf.config(image=self.assets["gear"])
        else: btn_conf.config(text="⚙ 設定", font=self.small_font)
        btn_conf.pack(side=tk.RIGHT)

        # ヘッダー
        header_frame = tk.Frame(self.root, bg=self.colors["bg"])
        header_frame.pack(fill=tk.X, padx=10, pady=10, anchor="w")
        if "icon" in self.assets: tk.Label(header_frame, image=self.assets["icon"], bg=self.colors["bg"]).pack(side=tk.LEFT, padx=(0, 5))
        if "name" in self.assets: tk.Label(header_frame, image=self.assets["name"], bg=self.colors["bg"]).pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(header_frame, text=f"{self.VERSION} - {self.config.get('user_name', 'User')}", 
                   bg=self.colors["bg"], fg=self.colors["fg_text"], font=self.header_font).pack(side=tk.LEFT)

        # ステータス表示
        self.status_var = tk.StringVar(value="スタンバイ OK ✨")
        self.lbl_status = tk.Label(self.root, textvariable=self.status_var, font=self.status_font, 
                                    fg=self.colors["status_fg"], bg=self.colors["bg"], compound="center")
        if "status_bg" in self.assets: self.lbl_status.config(image=self.assets["status_bg"])
        self.lbl_status.pack(pady=20)

        # 録音ボタン (長押し対応)
        self.btn_rec = tk.Button(self.root, bg=self.colors["bg"], relief="flat", bd=0)
        if "mic" in self.assets: self.btn_rec.config(image=self.assets["mic"])
        self.btn_rec.pack(pady=5)
        
        # --- 可愛い説明ラベル ---
        self.lbl_guide = tk.Label(self.root, text="ぎゅっと押している間、きかせてね ♡", 
                                  font=self.small_font, fg="#FF69B4", bg=self.colors["bg"])
        self.lbl_guide.pack(pady=(0, 10))

        # --- 長押しイベントのバインド ---
        self.btn_rec.bind("<ButtonPress-1>", self._on_mic_pressed)
        self.btn_rec.bind("<ButtonRelease-1>", self._on_mic_released)

        # テキスト入力エリア
        input_frame = tk.Frame(self.root, bg=self.colors["bg"])
        input_frame.pack(fill=tk.X, padx=40, pady=5)
        self.entry_var = tk.StringVar()
        self.entry_box = tk.Entry(input_frame, textvariable=self.entry_var, font=self.main_font, bd=2, relief="flat")
        self.entry_box.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        self.entry_box.bind("<Return>", self._on_submit)
        tk.Button(input_frame, text="送信", command=self._on_submit, bg="#FFB6C1", fg="white", font=self.main_font, relief="flat", padx=10).pack(side=tk.LEFT, padx=(5, 0))

        # ログボタン
        self.btn_log = tk.Button(self.root, command=self._toggle_log_panel, bg=self.colors["bg"], relief="flat", bd=0)
        if "log_btn" in self.assets: self.btn_log.config(image=self.assets["log_btn"])
        self.btn_log.pack(pady=5)

        # ログエリア
        self.log_frame = tk.Frame(self.root, bg=self.colors["bg"])
        self.chat_area = scrolledtext.ScrolledText(self.log_frame, state='disabled', bg=self.colors["log_bg"], 
                                                    fg="#333333", font=self.main_font, bd=0, padx=10, pady=5, height=10)
        self.chat_area.pack(fill=tk.X, expand=True, padx=20, pady=5)
        self.chat_area.tag_config("user", foreground=self.colors["user_text"], justify="right")
        self.chat_area.tag_config("bot", foreground=self.colors["bot_text"], justify="left")

        self.root.after(100, self._check_queue)
        self.root.mainloop()

    # --- 録音制御ロジック (Push-to-Talk) ---
    def _on_mic_pressed(self, event):
        if not self.is_recording_ui:
            self.is_recording_ui = True
            self.status_var.set("🔴 録音中...")
            self.btn_rec.config(relief="sunken", bg="#FFC0CB")
            if self.pm:
                self.pm.hook.start_recording()

    def _on_mic_released(self, event):
        if self.is_recording_ui:
            self.is_recording_ui = False
            self.status_var.set("解析中... 🔍")
            self.btn_rec.config(relief="flat", bg=self.colors["bg"])
            if self.pm:
                self.pm.hook.stop_recording()

    def _update_title(self):
        user_name = self.config.get("user_name", "ユーザー")
        if self.root: self.root.title(f"こもも - {user_name}")

    def _toggle_log_panel(self):
        if self.is_log_visible:
            self.log_frame.pack_forget()
            self.root.geometry(f"{self.WIN_W}x{self.WIN_H_STARTUP}")
            self.is_log_visible = False
        else:
            self.log_frame.pack(side=tk.TOP, fill=tk.X, after=self.btn_log)
            self.root.geometry(f"{self.WIN_W}x{self.WIN_H_EXPANDED}")
            self.is_log_visible = True

    def _show_lyric_window(self, lyrics):
        if lyrics == "CLOSE":
            if self.lyric_win: self.lyric_win.withdraw()
            return
        if self.lyric_win is None or not self.lyric_win.winfo_exists():
            self.lyric_win = tk.Toplevel(self.root)
            self.lyric_win.overrideredirect(True)
            self.lyric_win.attributes("-topmost", True)
            self.lyric_win.geometry("400x240+100+100")
            self.lyric_win.configure(bg="#FFF0F5")
            def start_move(e): self.lyric_win._x = e.x; self.lyric_win._y = e.y
            def do_move(e):
                x = self.lyric_win.winfo_x() + (e.x - self.lyric_win._x)
                y = self.lyric_win.winfo_y() + (e.y - self.lyric_win._y)
                self.lyric_win.geometry(f"+{x}+{y}")
            self.lyric_win.bind("<Button-1>", start_move); self.lyric_win.bind("<B1-Motion>", do_move)
            self.lyric_win.bind("<Button-3>", lambda e: self.lyric_win.withdraw()) 
            self.lyric_txt = tk.Text(self.lyric_win, font=("Meiryo", 10), bg="#FFF0F5", fg="#FF1493", bd=0, padx=20, pady=10, height=8)
            self.lyric_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb = tk.Scrollbar(self.lyric_win, command=self.lyric_txt.yview)
            self.lyric_txt.config(yscrollcommand=sb.set); sb.pack(side=tk.RIGHT, fill=tk.Y)
            self.lyric_txt.bind("<Button-1>", start_move); self.lyric_txt.bind("<B1-Motion>", do_move)
        self.lyric_win.deiconify(); self.lyric_txt.config(state='normal'); self.lyric_txt.delete("1.0", tk.END)
        self.lyric_txt.insert(tk.END, lyrics); self.lyric_txt.config(state='disabled')

    def _check_queue(self):
        try:
            while not self.msg_queue.empty():
                m_type, content = self.msg_queue.get_nowait()
                if m_type == "status": self.status_var.set(content)
                elif m_type == "lyrics": self._show_lyric_window(content)
                elif m_type == "rec_state":
                    self.is_recording_ui = content
                    if not content: 
                        self.status_var.set("スタンバイ OK ✨")
                        self.btn_rec.config(relief="flat", bg=self.colors["bg"])
                elif m_type == "bot": self._append_log("bot", content); self.status_var.set("スタンバイ OK ✨")
                elif m_type == "user": self._append_log("user", content)
        except: pass
        finally:
            if self.is_running and self.root: self.root.after(100, self._check_queue)

    def _append_log(self, tag, text):
        self.chat_area.config(state='normal')
        ts = time.strftime("%H:%M")
        if tag == "user": display = f"{text.replace('[User]','').strip()} ({ts})\n"
        elif tag == "bot": display = f"[こもも]: {text} ({ts})\n"
        else: display = f"{text}\n"
        self.chat_area.insert(tk.END, display, tag); self.chat_area.see(tk.END); self.chat_area.config(state='disabled')

    def _load_assets(self):
        file_map = {"icon": "icon.png", "name": "name.png", "status_bg": "image_f1e9c3.png", 
                    "mic": "image_f24aa4.png", "log_btn": "image_f48d96.png", "gear": "gear.png"}
        for k, v in file_map.items():
            path = os.path.join(ASSETS_DIR, v)
            if os.path.exists(path): self.assets[k] = tk.PhotoImage(file=path)

    def _on_submit(self, e=None):
        t = self.entry_var.get().strip()
        if t and self.pm:
            self.entry_var.set(""); self.entry_box.focus_set()
            threading.Thread(target=lambda: self.pm.hook.on_query_received(text=t), daemon=True).start()
        return "break"

    def _request_settings(self):
        if self.pm:
            self.msg_queue.put(("bot", "設定画面を開くね。何か変えるのかな？"))
            self.pm.hook.on_open_settings_requested(root_window=self.root)

    def _on_close(self):
        self.is_running = False; self.root.destroy(); os._exit(0)