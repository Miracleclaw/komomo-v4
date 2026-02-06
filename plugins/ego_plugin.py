import json
import requests
import os

class EgoPlugin:
    def __init__(self, config, gui):
        self.config = config
        self.gui = gui
        self.memory_path = "memory.json"
        self.memory = self._load_memory()
        print("[EgoPlugin] Initialized (OpenRouter)")

    def _load_memory(self):
        if os.path.exists(self.memory_path):
            with open(self.memory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"user_data": {}, "last_emotion": {"joy": 50, "trust": 50, "tension": 20}}

    def extract_info_from_dialogue(self, user_text, ai_response):
        """OpenRouterを使って感情とユーザー情報を抽出"""
        print("[Ego] 感情分析リクエスト送信中...")
        key = self.config.get("openrouter_api_key")
        if not key:
            print("[Ego] APIキーがないためスキップします")
            return

        prompt = f"""
        以下の会話からJSON形式でデータを抽出してください。
        会話: ユーザー「{user_text}」 こもも「{ai_response}」
        出力形式: {{"emotion_stats": {{"joy": 0, "trust": 0, "tension": 0}}, "emotion_id": "12", "inner_monologue": "..."}}
        """
        try:
            res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "google/gemini-2.0-flash-lite-preview-02-05:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"}
                }, timeout=15
            )
            if res.status_code == 200:
                data = json.loads(res.json()["choices"][0]["message"]["content"])
                print(f"[Ego] 分析結果受信: ID={data.get('emotion_id')}")
                self._save_memory(data)
                self.send_to_unity(data.get("emotion_id", "12"))
        except Exception as e:
            print(f"[Ego] 感情分析エラー (無視): {e}")

    def _save_memory(self, data):
        self.memory["last_emotion"] = data.get("emotion_stats", self.memory["last_emotion"])
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, indent=4, ensure_ascii=False)

    def send_to_unity(self, emotion_id):
        """UnityへJSON形式で表情IDを送信（歌唱用など外部からの呼び出し用）"""
        try:
            unity_url = "http://127.0.0.1:58080/play/"
            payload = {
                "action": "expression",
                "index": int(emotion_id)
            }
            requests.post(unity_url, json=payload, timeout=5)
            print(f"[Ego] Unityへ表情ID {emotion_id} を送信しました")
        except Exception as e:
            print(f"[Ego] Unity表情送信エラー: {e}")

    def _send_to_unity(self, emotion_id):
        """内部互換性用の別名"""
        self.send_to_unity(emotion_id)