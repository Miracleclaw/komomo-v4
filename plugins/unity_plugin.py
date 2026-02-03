import pluggy
import requests
import json
import re

hookimpl = pluggy.HookimplMarker("komomo")

class Plugin:
    def __init__(self, config):
        self.config = config
        self.unity_url = config.get("unity_url", "http://127.0.0.1:58080/play/") 
        self.emotion_url = config.get("emotion_url", "http://127.0.0.1:58080/emotion")

    @hookimpl
    def on_llm_response_generated(self, response_text: str):
        # --- 【修正】真っ先にチェック ---
        # これにより、Lyricデータの時はログ出力も表情送信もスキップします
        if response_text.startswith("Lyric:") or response_text.startswith("ID:"):
            return

        print(f"[Unity] 表情解析中: {response_text[:10]}...")
        expression_index = self._analyze_emotion(response_text)
        self._send_expression(expression_index)

    @hookimpl
    def on_audio_generated(self, audio_data: bytes):
        # 歌のデータは大きいので、送信中であることがわかるように表示
        size_mb = len(audio_data) / (1024 * 1024)
        print(f"[Unity] 音声データを送信中... ({size_mb:.1f} MB)")
        self._send_audio(audio_data)

    def _send_audio(self, wav_data):
        try:
            res = requests.post(
                self.unity_url,
                data=wav_data,
                headers={"Content-Type": "audio/wav"},
                timeout=20 # 歌のデータは大きいので少し長めに
            )
            if res.status_code == 200:
                print("[Unity] 送信成功")
        except Exception as e:
            print(f"[Unity] Connection Error: {e}")

    def _send_expression(self, index):
        try:
            requests.post(self.emotion_url, json={"action": "expression", "index": index}, timeout=0.5)
        except: pass

    def _analyze_emotion(self, text):
        if any(w in text for w in ["悲", "泣", "残念", "辛", "ごめん"]): return 1
        if any(w in text for w in ["怒", "許", "プンプン", "😡", "💢"]): return 2
        if any(w in text for w in ["喜", "楽", "笑", "♪", "！", "✨", "わーい"]): return 3
        return 0