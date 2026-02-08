"""
Komomo System Plugin - LLM Language Engine
Version: v4.3.0.0

[役割]
こももの「知能」を司るプラグイン。
OpenAI, Gemini, Groq の3段階フォールバックシステムを搭載し、
API制限による会話停止を極力防ぎます。

[優先順位]
1. OpenAI (gpt-4o-mini) : 安定・高速・無料枠活用
2. Gemini (Flash 2.0)   : 高性能だがQuota制限がきつい
3. Groq (Llama 3)       : 最終防衛ライン
"""
import requests
import json
import re
import traceback
import google.generativeai as genai

class LLMPlugin:
    def __init__(self, config, gui):
        self.config = config
        self.gui = gui
        print("[LLMPlugin] Initialized (OpenAI -> Gemini -> Groq)")

    def generate_response(self, text, instruction):
        print(f"[LLM] 思考プロセス開始: '{text}'")
        conf = self.config
        response_text = None

        # --- 1. OpenAI (最優先: 安定版) ---
        openai_key = conf.get("openai_api_key")
        if openai_key:
            try:
                self.gui.update_status("思考中...(OpenAI)")
                res = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {openai_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": conf.get("openai_model", "gpt-4o-mini-2024-07-18"),
                        "messages": [
                            {"role": "system", "content": instruction},
                            {"role": "user", "content": text}
                        ],
                        "temperature": 0.7
                    }, timeout=20
                )
                if res.status_code == 200:
                    response_text = res.json()["choices"][0]["message"]["content"]
                    self.current_model = "OpenAI"
                    print("[LLM] OpenAIから応答を受信")
                    self.gui.update_status("オンライン (OpenAI)")
                else:
                    print(f"[LLM] OpenAI Error: {res.status_code}")
            except Exception as e:
                print(f"[LLM] OpenAI接続エラー: {e}")

        # --- 2. Gemini (フォールバック 1) ---
        google_key = conf.get("google_api_key")
        if not response_text and google_key:
            try:
                self.gui.update_status("OpenAI不可... Geminiへ切替")
                genai.configure(api_key=google_key)
                # モデル名の 'models/' 接頭辞を除去して正規化
                model_name = conf.get("gemini_model", "gemini-2.0-flash").replace("models/", "")
                model = genai.GenerativeModel(model_name)
                
                # Geminiは systemプロンプトを generate_content の引数に入れるか、
                # SystemInstructionとして渡す必要があるが、簡易的に結合する
                full_prompt = f"System: {instruction}\nUser: {text}"
                
                res = model.generate_content(full_prompt)
                if res and res.text:
                    response_text = res.text
                    self.current_model = "Gemini"
                    print("[LLM] Geminiから応答を受信")
                    self.gui.update_status("オンライン (Gemini)")
            except Exception as e:
                print(f"[LLM] Gemini接続エラー: {e}")

        # --- 3. Groq (フォールバック 2: 最終手段) ---
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
                    self.current_model = "Groq"
                    print("[LLM] Groqから応答を受信")
                    self.gui.update_status("オンライン (Groq)")
            except Exception as e:
                print(f"[LLM] Groq接続エラー: {e}")
                self.gui.update_status("全API接続失敗")

        return self._clean_response(response_text) if response_text else None

    def _clean_response(self, text):
        """発声に不要なタグ [ID:xx] などを除去"""
        # [ID:12] のようなタグを除去
        cleaned = re.sub(r'\[.*?\]', '', text)
        # 思考プロセス <think>...</think> が混じる場合を除去 (DeepSeek等対策)
        cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL)
        return cleaned.strip()