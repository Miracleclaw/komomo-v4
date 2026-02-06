import sys
import threading
import time
import json
import re
import requests
import subprocess
import pluggy
import traceback

# 設計図(specs)のインポート
try:
    from core.specs import KomomoSpecs
except ModuleNotFoundError:
    from specs import KomomoSpecs

# 各プラグインのインポート
from plugins.llm_plugin import LLMPlugin
from plugins.ego_plugin import EgoPlugin
from plugins.gui_plugin import GUIPlugin
from plugins.stt_plugin import STTPlugin
from plugins.voice_plugin import VoicePlugin
# settings_plugin.py内のクラス名はPlugin
from plugins.settings_plugin import Plugin as SettingsPlugin

class KomomoSystem:
    def __init__(self):
        print("==========================================")
        print("   Komomo AI Assistant System v4.3.0")
        print("==========================================")
        
        # 1. 設定の読み込み
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                self.config = json.load(f)
            with open("character.txt", "r", encoding="utf-8") as f:
                self.instruction = f.read()
        except Exception as e:
            print(f"[Fatal] 設定読み込み失敗: {e}")
            sys.exit(1)

        # 2. pluggy PluginManagerの初期化と設計図登録
        self.pm = pluggy.PluginManager("komomo")
        self.pm.add_hookspecs(KomomoSpecs)
        
        # 3. インスタンス生成
        self.gui = GUIPlugin(self.config, self)
        self.settings = SettingsPlugin(self.config)
        self.stt = STTPlugin(self.config, self.gui)
        self.llm = LLMPlugin(self.config, self.gui)
        self.ego = EgoPlugin(self.config, self.gui)
        self.voice = VoicePlugin(self.config, self.gui)

        # 4. プラグインの登録
        self.pm.register(self.gui)
        self.pm.register(self.settings)
        self.pm.register(self.stt)
        self.pm.register(self.llm)
        self.pm.register(self.ego)
        self.pm.register(self.voice)
        # 自分自身を登録してフック(on_query_received)を待ち受ける
        self.pm.register(self)

        # 5. 【重要】GUIPluginへの初期化処理
        # pmをセットし、起動メソッドを別スレッドで安全に実行する
        if hasattr(self.gui, 'pm'):
            self.gui.pm = self.pm

        self.is_running = True

        print("[System] 起動信号を送信中...")
        # 信号送信を試行
        if hasattr(self.pm.hook, "on_plugin_loaded"):
            self.pm.hook.on_plugin_loaded(pm=self.pm)
        
        # specs.pyに定義がない場合や信号が届かない場合に備え、
        # 1秒後にGUIが未起動なら直接 _run_gui を別スレッドで叩く
        def safety_launcher():
            time.sleep(1.0)
            if not hasattr(self.gui, 'root') or self.gui.root is None:
                print("[System] バックアップ起動を実行: _run_gui を開始します")
                threading.Thread(target=self.gui._run_gui, daemon=True).start()

        threading.Thread(target=safety_launcher, daemon=True).start()

        self.stt.on_plugin_loaded(self.pm)

        # 6. 処理ループスレッド
        self.process_thread = threading.Thread(target=self._main_processing_loop, daemon=True)
        self.process_thread.start()
   
    @pluggy.HookimplMarker("komomo")
    def on_query_received(self, text):
        """GUIやSTTからの入力を中継する司令塔"""
        print(f"[Main] ユーザー入力: {text}")
        
        # --- A. アプリ起動チェック ---
        apps_raw = self.config.get("apps_raw", "")
        for line in apps_raw.split("\n"):
            if ":" in line:
                app_name, app_path = line.split(":", 1)
                if f"{app_name.strip()}を起動" in text or f"{app_name.strip()}を開いて" in text:
                    try:
                        subprocess.Popen(app_path.strip(), shell=True)
                        self.voice.speak(f"はい、{app_name.strip()}を起動しますね。")
                        return 
                    except: pass

        # --- B. LLMで返答を生成 ---
        response = self.llm.generate_response(text, self.instruction)
        
        if response:
            user_name = self.config.get("user_name", "あなた")
            final_res = response.replace("{{user}}", user_name)
            
            # 各種プラグインへの通知 (GUI表示・感情分析・発声)
            self.pm.hook.on_llm_response_generated(response_text=final_res)
            self.ego.extract_info_from_dialogue(text, response)
            self.voice.speak(final_res)

    def _main_processing_loop(self):
        while self.is_running:
            time.sleep(1)

    def run(self):
        """メインスレッドを維持し、終了を待機する"""
        print("[System] システム稼働中。終了するには Ctrl+C を押してください。")
        try:
            while self.is_running:
                # GUIが閉じられた場合に備え、微小な待機を入れる
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.is_running = False
            print("\n[System] ユーザーにより終了リクエストを受け取りました。")
        finally:
            print("[System] 終了します。")
            sys.exit(0)

if __name__ == "__main__":
    app = KomomoSystem()
    app.run()