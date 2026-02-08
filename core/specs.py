"""
Komomo System Core - Plugin Hook Specifications
Version: v4.2.0

[役割]
このシステムにおける「プラグインが実装すべきメソッド（Hook）」を定義するインターフェース。
ここでの定義に基づいて、各プラグインが連携動作します。

[主な機能]
- 会話、音声合成、描画、Unity送信等のイベント定義
- 各Hookの引数と戻り値の形式指定
- システム全体の拡張ポイントの定義
"""
import pluggy

hookspec = pluggy.HookspecMarker("komomo")

class KomomoSpecs:
    @hookspec
    def on_plugin_loaded(self, pm):
        """プラグインロード完了時の通知"""

    @hookspec
    def on_query_received(self, text: str):
        """ユーザー入力時"""

    @hookspec
    def on_llm_response_generated(self, response_text: str):
        """LLM回答時"""

    @hookspec
    def on_audio_generated(self, audio_data: bytes):
        """音声生成時"""

    @hookspec
    def on_open_settings_requested(self, root_window):
        """設定画面リクエスト"""

    # --- ↓ 追加: 録音制御用 ↓ ---
    @hookspec
    def on_start_recording_requested(self):
        """録音開始をリクエスト"""

    @hookspec
    def on_stop_recording_requested(self):
        """録音停止をリクエスト"""