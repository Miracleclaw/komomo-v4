import pluggy

hookspec = pluggy.HookspecMarker("komomo")

class KomomoSpecs:
    # ... (既存のフック) ...

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