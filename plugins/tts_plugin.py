"""
Komomo System Plugin - Text To Speech (TTS) Interface
Version: v4.2.0

[役割]
テキストを音声に変換する外部エンジン（VoiceVox等）との仲介プラグイン。
生成された音声データのバッファ管理を行います。

[主な機能]
- 音声合成エンジンへのリクエスト送信
- 話速、ピッチ、イントネーションのパラメータ制御
- 合成完了後の音声データ受け渡し
"""
import re
import pluggy
import requests
import json

hookimpl = pluggy.HookimplMarker("komomo")

class Plugin:
    def __init__(self, config):
        self.config = config
        self.pm = None
        self.url = config.get("voicevox_url", "http://127.0.0.1:50021")
        self.speaker_id = config.get("voicevox_speaker_id", 46)

    def on_plugin_loaded(self, pm):
        self.pm = pm

    @hookimpl
    def on_llm_response_generated(self, response_text: str):
        # --- 【修正ポイント】ここを厳格にチェックします ---
        # 「Lyric:」で始まる歌詞データ、または「ID:」で始まる制御命令は、
        # 1文字も喋らせずにここで処理を終了（return）させます。
        if response_text.startswith("Lyric:") or response_text.startswith("ID:"):
            print(f"[TTS] フィルタリング: 命令データをスキップします ({response_text[:10]}...)")
            return

        # クリーニング処理（タグやMarkdown除去）
        clean_text = self._cleanup_text(response_text)
        if not clean_text:
            return

        print(f"[TTS] 音声合成中 (長さ: {len(clean_text)}文字)...")
        
        try:
            # 1. 音声合成用のクエリ作成
            res1 = requests.post(
                f"{self.url}/audio_query",
                params={"text": clean_text, "speaker": self.speaker_id},
                timeout=60
            )
            if res1.status_code != 200:
                return
            
            query_data = res1.json()

            # 2. 音声合成（WAV生成）実行
            res2 = requests.post(
                f"{self.url}/synthesis",
                params={"speaker": self.speaker_id},
                data=json.dumps(query_data),
                timeout=60
            )

            if res2.status_code == 200:
                # 生成された音声データをUnityプラグインへ渡す
                if self.pm:
                    self.pm.hook.on_audio_generated(audio_data=res2.content)
            else:
                print(f"[TTS] 合成失敗: {res2.status_code}")

        except Exception as e:
            print(f"[TTS] Error: {e}")

    def _cleanup_text(self, text):
        """読み上げに不要なタグやMarkdown記号を除去"""
        # [LAUNCH:xxx] 形式の除去
        t = re.sub(r"\[LAUNCH:.*?\]", "", text)
        # Markdown記号 (**太字** など) の除去
        t = re.sub(r"\*\*|\*|#|`|_|>", "", t)
        return t.strip()