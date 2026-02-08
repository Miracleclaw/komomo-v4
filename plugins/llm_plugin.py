"""
Komomo System Plugin - LLM Language Engine
Version: v4.2.0

[役割]
こももの「知能」を司るプラグイン。
GeminiやGroqなどの外部APIと連携し、キャラクター設定に基づいた
自然な応答テキストを生成します。

[主な機能]
- 複数モデル（Gemini/Groq）の切り替えとエラーハンドリング
- キャラクター設定（character.txt）を反映したプロンプト構築
- クォータ制限時の自動フォールバック処理
"""
import requests
import json
import re
import google.generativeai as genai

class LLMPlugin:
    def __init__(self, config, gui):
        self.config = config
        self.gui = gui
        print("[LLMPlugin] Initialized (Gemini/Groq)")

    def generate_response(self, text, instruction):
        print(f"[LLM] 思考プロセス開始: '{text}'")
        conf = self.config
        response_text = None

        # --- 1. Gemini (メイン) ---
        google_key = conf.get("google_api_key")
        if google_key:
            try:
                self.gui.update_status("思考中...(Gemini)")
                genai.configure(api_key=google_key)
                model_name = conf.get("gemini_model", "gemini-2.0-flash").replace("models/", "")
                model = genai.GenerativeModel(model_name)
                
                res = model.generate_content(f"System: {instruction}\nUser: {text}")
                if res and res.text:
                    response_text = res.text
                    print("[LLM] Geminiから応答を受信")
                    self.gui.update_status("オンライン (Gemini)")
            except Exception as e:
                print(f"[LLM] Gemini接続エラー: {e}")

        # --- 2. Groq (フォールバック) ---
        groq_key = conf.get("groq_api_key")
        if not response_text and groq_key:
            try:
                self.gui.update_status("Gemini制限中... Groqへ切替")
                res = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json={
                        "model": conf.get("groq_model", "llama-3.3-70b-versatile"),
                        "messages": [
                            {"role": "system", "content": instruction},
                            {"role": "user", "content": text}
                        ]
                    }, timeout=15
                )
                if res.status_code == 200:
                    response_text = res.json()["choices"][0]["message"]["content"]
                    print("[LLM] Groqから応答を受信")
                    self.gui.update_status("オンライン (Groq)")
            except Exception as e:
                print(f"[LLM] Groq接続エラー: {e}")
                self.gui.update_status("全API接続失敗")

        return self._clean_response(response_text) if response_text else None

    def _clean_response(self, text):
        """発声に不要なタグ [ID:xx] などを除去"""
        cleaned = re.sub(r'\[.*?\]', '', text)
        return cleaned.strip()