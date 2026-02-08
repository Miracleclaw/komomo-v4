"""
Komomo System Plugin - Runtime Settings UI
Version: v4.2.0

[役割]
動作中のシステム設定を変更するためのUIを提供するプラグイン。
音量や感度などをリアルタイムで調整可能にします。

[主な機能]
- 設定変更用スライダーやチェックボックスの提供
- 変更されたパラメータの `core/config.py` への反映
"""
import pluggy
import tkinter as tk
from tkinter import ttk
import json
import os
import re

hookimpl = pluggy.HookimplMarker("komomo")

class Plugin:
    def __init__(self, config):
        self.config = config
        self.pm = None
        self.win = None

    @hookimpl
    def on_open_settings_requested(self, root_window):
        if self.win is not None and self.win.winfo_exists():
            self.win.lift()
            return

        self.win = tk.Toplevel(root_window)
        self.win.title("こもも設定")
        self.win.geometry("500x650")
        self.win.configure(bg="#FFF0F5")
        self.win.attributes("-topmost", True)

        nb = ttk.Notebook(self.win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- 【接続設定】タブ ---
        tab1 = tk.Frame(nb, bg="#FFF0F5")
        nb.add(tab1, text=" 【接続設定】 ")

        self.entries = {}
        self._add_field(tab1, "user_name", "ユーザー名")
        
        self._add_label(tab1, "■ OpenRouter (Main)", bold=True, pady=(15, 0))
        self._add_field(tab1, "openrouter_api_key", "API Key")
        self._add_field(tab1, "openrouter_endpoint", "Endpoint")

        self._add_label(tab1, "■ Google API Key (Sub1)", bold=True, pady=(15, 0))
        self._add_field(tab1, "google_api_key", "API Key")

        self._add_label(tab1, "■ Groq API Key (Sub2)", bold=True, pady=(15, 0))
        self._add_field(tab1, "groq_api_key", "API Key")

        # --- 【登録アプリ】タブ ---
        tab2 = tk.Frame(nb, bg="#FFF0F5")
        nb.add(tab2, text=" 【登録アプリ】 ")
        tk.Label(tab2, text="[アプリ名]:[PATH] (1行ずつ)", bg="#FFF0F5", font=("Meiryo", 9)).pack(pady=10, anchor="w", padx=20)
        self.ent_apps = tk.Text(tab2, height=15, width=50, font=("Meiryo", 9))
        
        # 読み込み: self.configから直接、またはdata辞書から取得
        apps_val = self._get_config_val("apps_raw")
        self.ent_apps.insert("1.0", str(apps_val))
        self.ent_apps.pack(padx=20, pady=5, fill=tk.BOTH, expand=True)

        tk.Button(self.win, text="保存して閉じる", command=self.save_proc, bg="#FFB6C1", font=("", 10, "bold")).pack(pady=20)

    def _add_label(self, parent, text, bold=False, pady=(10, 0)):
        f = ("Meiryo", 9, "bold" if bold else "normal")
        tk.Label(parent, text=text, bg="#FFF0F5", font=f).pack(pady=pady, anchor="w", padx=20)

    def _add_field(self, parent, key, label):
        tk.Label(parent, text=label, bg="#FFF0F5", font=("Meiryo", 9)).pack(anchor="w", padx=20)
        ent = tk.Entry(parent, width=50)
        val = self._get_config_val(key)
        ent.insert(0, str(val))
        ent.pack(padx=20, pady=2, fill=tk.X)
        self.entries[key] = ent

    def _get_config_val(self, key):
        """あらゆる手段でconfigから値を取得する"""
        if hasattr(self.config, 'data') and key in self.config.data:
            return self.config.data[key]
        if hasattr(self.config, key):
            return getattr(self.config, key)
        # config.get()がある場合
        try: return self.config.get(key, "")
        except: return ""

    def save_proc(self):
        print("[Settings] 保存シーケンス開始...")
        
        # 1. データの収集
        save_data = {}
        for key, ent in self.entries.items():
            save_data[key] = ent.get()
        save_data["apps_raw"] = self.ent_apps.get("1.0", tk.END).strip()

        # 2. ConfigManagerオブジェクトの更新
        for key, val in save_data.items():
            # data辞書を優先更新
            if hasattr(self.config, 'data'):
                self.config.data[key] = val
            # 属性としてもセット
            setattr(self.config, key, val)

        # 3. ファイルへの書き出し（ローラー作戦）
        success = False

        # A. 既存のsaveメソッドがあれば実行
        if hasattr(self.config, 'save'):
            try:
                self.config.save()
                print("[Settings] config.save() を実行しました。")
                success = True
            except Exception as e:
                print(f"[Settings] save実行失敗: {e}")

        # B. 保存されなかった場合、直接config.jsonを書き換える（最終手段）
        try:
            target_path = "config.json"
            # ConfigManagerが保持している全てのデータを書き出す
            full_data = {}
            if hasattr(self.config, 'data'):
                full_data = self.config.data
            else:
                # 属性からデータを抽出
                full_data = {k: v for k, v in self.config.__dict__.items() if not k.startswith('_')}
            
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(full_data, f, indent=4, ensure_ascii=False)
            print(f"[Settings] {target_path} を直接上書き保存しました。")
            success = True
        except Exception as e:
            print(f"[Settings] ファイル直接保存に失敗: {e}")

        if success:
            print("[Settings] すべての変更が確定しました。")
            self.win.destroy()
            self.win = None

    def on_plugin_loaded(self, pm):
        self.pm = pm