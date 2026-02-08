"""
Komomo AI Assistant System - Core Launcher
Version: v4.3.0.12

[役割]
システムのメインエントリーポイント。
回答生成時に「事実」「履歴」「関連思い出」を参考資料として注入しつつ、
DBに直接的な答えがない場合にLLMが自律的に知識を活用できるよう、プロンプト構成を最適化。
"""
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
        print("   Komomo AI Assistant System v4.3.0.12")
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
        # --- 歌唱中はすべての入力を無視するガード ---
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
        """ハイブリッド記憶を活用した回答生成（自律知識活用版）"""
        model_name = getattr(self.llm, 'current_model', getattr(self.llm, 'model_type', 'LLM'))
        
        if hasattr(self.gui, "update_status"):
             self.gui.update_status(f"思考中...({model_name})")

        try:
            # --- 🚀 ハイブリッド記憶の抽出 ---
            user_profile = self.ego.get_user_profile_summary()
            recent_memories = self.ego.get_recent_memories(limit=5)
            semantic_memories = ""
            if hasattr(self.ego, "search_semantic_memories"):
                semantic_memories = self.ego.search_semantic_memories(text, n_results=2)
            
            # --- 🚀 修正：記憶と自律知識のバランス調整用プロンプト ---
            context_instruction = (
                "\n[記憶と知識の取り扱い方針]\n"
                "1. 下記の提供されたコンテキスト（あっきーの知識、過去の思い出）は、事実確認のための参考資料です。\n"
                "2. もし提供されたコンテキストに直接的な答えやエピソードが含まれていない場合（例：昔話をして、面白い話をして等の依頼）は、"
                "あなた自身が持つ広範な知識や創造力を駆使して、こももらしく楽しく自由に回答してください。\n"
                "3. 記憶に縛られすぎて、単なる「思い出の確認」に終始しないよう注意してください。\n"
            )
            
            # 4. すべてを合体させてプロンプトを構築
            full_instruction = (
                f"{self.instruction}\n"
                f"{context_instruction}\n"
                f"{user_profile}\n"
                f"{recent_memories}\n"
                f"{semantic_memories}"
            )
            
            # 回答生成の実行
            response = self.llm.generate_response(text, full_instruction)
            
            if response:
                user_name = self.config.get("user_name", "あなた")
                final_res = response.replace("{{user}}", user_name)
                
                # フック通知：各プラグインへの配送
                self.pm.hook.on_llm_response_generated(response_text=final_res)
                # 感情分析、事実抽出、および履歴保存（SQLite & ChromaDB）
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
        print("[System] システム稼働中. 終了するには Ctrl+C を押してください.")
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