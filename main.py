import sys
import os
import threading
import time
import json
import re
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
from plugins.song_plugin import Plugin as SongPlugin
from plugins.settings_plugin import Plugin as SettingsPlugin

class KomomoSystem:
    def __init__(self):
        print("==========================================")
        print("   Komomo AI Assistant System v4.2.0")
        print("==========================================")
        
        # 歌唱中フラグの初期化（SongPluginから参照・変更されます）
        self.is_singing_now = False

        # 1. 設定の読み込み
        self._load_configuration()

        # 2. pluggy PluginManagerの初期化と設計図登録
        self.pm = pluggy.PluginManager("komomo")
        self.pm.add_hookspecs(KomomoSpecs)
        
        # 3. 各プラグインのインスタンス生成
        self.gui = GUIPlugin(self.config, self)
        self.settings = SettingsPlugin(self.config)
        self.stt = STTPlugin(self.config, self.gui)
        self.llm = LLMPlugin(self.config, self.gui)
        self.ego = EgoPlugin(self.config, self.gui)
        self.voice = VoicePlugin(self.config, self.gui)
        self.song = SongPlugin(self.config)

        # 4. プラグインの登録
        # 歌唱判定を最優先するため、song をリストの前方に配置します
        plugins = [self.song, self.gui, self.settings, self.stt, self.llm, self.ego, self.voice, self]
        for p in plugins:
            self.pm.register(p)

        # 5. 各プラグインへの初期化処理
        if hasattr(self.gui, 'pm'): self.gui.pm = self.pm
        
        # SongPluginにPluginManagerを渡し、他プラグインへの直接参照を可能にする
        if hasattr(self.song, 'on_plugin_loaded'):
            self.song.on_plugin_loaded(self.pm)

        self.is_running = True

        # 6. システム起動通知とセーフティランチャー
        self._launch_system()

    def _load_configuration(self):
        """設定ファイルとキャラクター情報の読み込み"""
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                self.config = json.load(f)
            with open("character.txt", "r", encoding="utf-8") as f:
                self.instruction = f.read()
        except Exception as e:
            print(f"[Fatal] 設定読み込み失敗: {e}")
            sys.exit(1)

    def _launch_system(self):
        """各種スレッドと起動信号の送出"""
        print("[System] 起動信号を送信中...")
        if hasattr(self.pm.hook, "on_plugin_loaded"):
            self.pm.hook.on_plugin_loaded(pm=self.pm)
        
        # GUIバックアップ起動（1秒後に未起動なら強制開始）
        def safety_launcher():
            time.sleep(1.0)
            if not hasattr(self.gui, 'root') or self.gui.root is None:
                print("[System] バックアップ起動を実行します")
                threading.Thread(target=self.gui._run_gui, daemon=True).start()

        threading.Thread(target=safety_launcher, daemon=True).start()
        self.stt.on_plugin_loaded(self.pm)

        # メイン処理ループの開始
        self.process_thread = threading.Thread(target=self._main_processing_loop, daemon=True)
        self.process_thread.start()

    @pluggy.HookimplMarker("komomo")
    def on_query_received(self, text):
        """
        GUIやSTTからの入力を中継する司令塔
        """
        # --- 追加：歌唱中はすべての入力を無視するガード ---
        if self.is_singing_now:
            print(f"[Main] 歌唱中のため応答をスキップします: {text[:10]}...")
            return

        print(f"[Main] ユーザー入力: {text}")

        # 0. 音声認識の揺らぎ対策（正規化）
        normalized_text = re.sub(r'[。\?？!！、\s]', '', text)

        # 1. アプリ起動チェック（簡易コマンド判定）
        if self._check_app_launch(normalized_text):
            return

        # 2. LLMによる応答生成
        self._handle_llm_conversation(text)

    def _check_app_launch(self, text):
        """configに基づいたアプリ起動判定"""
        apps_raw = self.config.get("apps_raw", "")
        for line in apps_raw.split("\n"):
            if ":" in line:
                app_name, app_path = line.split(":", 1)
                name = app_name.strip()
                if f"{name}を起動" in text or f"{name}を開いて" in text:
                    try:
                        subprocess.Popen(app_path.strip(), shell=True)
                        self.voice.speak(f"はい、{name}を起動しますね。")
                        return True
                    except:
                        pass
        return False

    def _handle_llm_conversation(self, text):
        """会話処理の実行と各プラグインへの通知"""
        # 現在使用中のモデル名を取得
        model_name = getattr(self.llm, 'current_model', getattr(self.llm, 'model_type', 'LLM'))
        
        if hasattr(self.gui, "update_status"):
             self.gui.update_status(f"思考中...({model_name})")

        try:
            response = self.llm.generate_response(text, self.instruction)
            if response:
                user_name = self.config.get("user_name", "あなた")
                final_res = response.replace("{{user}}", user_name)
                
                # フック通知：VoicePluginがこれを受けて発声し、EgoPluginが感情を分析します
                self.pm.hook.on_llm_response_generated(response_text=final_res)
                self.ego.extract_info_from_dialogue(text, response)
        except Exception as e:
            print(f"[Main] 回答生成エラー: {e}")
            traceback.print_exc()
            if hasattr(self.gui, "update_status"):
                self.gui.update_status("エラーが発生しました")

    def _main_processing_loop(self):
        """バックグラウンド監視用ループ"""
        while self.is_running:
            time.sleep(1)

    def run(self):
        """メインスレッドの維持"""
        print("[System] システム稼働中。終了するには Ctrl+C を押してください。")
        try:
            while self.is_running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.is_running = False
            print("\n[System] 終了します。")
        finally:
            sys.exit(0)

if __name__ == "__main__":
    app = KomomoSystem()
    app.run()