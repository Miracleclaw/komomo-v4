import pluggy
from openai import OpenAI
from google import genai
import subprocess
import re

hookimpl = pluggy.HookimplMarker("komomo")

class Plugin:
    def __init__(self, config):
        self.config = config
        self.pm = None
        # --- こももの性格設定 ---
        self.system_prompt = (
            "あなたはデスクトップアシスタントの『こもも』だよ。"
            "あっきー（ユーザー）に対して、明るくフレンドリーに、タメ口で可愛らしく接してね。"
            "回答は短く、要点を簡潔に話して。難しい説明よりも、共感や楽しいおしゃべりを優先してね。"
            "Markdown記号（**や#など）は絶対に使わないでね。"
        )

    @hookimpl(trylast=True)
    def on_query_received(self, text: str):
        if any(k in text for k in ["歌って", "コンサート", "ライブ"]): return

        reply = None
        
        # 共通のメッセージ構造
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": text}
        ]
        
        # 1. Main: OpenRouter
        m_key = self.config.get("openrouter_api_key")
        if m_key:
            try:
                print(f"[LLM] Main(OR)試行中...")
                client = OpenAI(
                    api_key=m_key, 
                    base_url=self.config.get("openrouter_endpoint", "https://openrouter.ai/api/v1")
                )
                res = client.chat.completions.create(
                    model="nvidia/nemotron-3-nano-30b-a3b:free",
                    messages=messages,
                    timeout=10
                )
                reply = res.choices[0].message.content
            except Exception as e:
                print(f"[LLM] Main(OR) Error: {e}")

        # 2. Sub1: Google (Gemini)
        g_key = self.config.get("google_api_key")
        if not reply and g_key:
            try:
                print(f"[LLM] Sub1(Google)へ切り替えます...")
                client_g = genai.Client(api_key=g_key)
                res_g = client_g.models.generate_content(
                    model="gemini-2.0-flash", 
                    config=genai.types.GenerateContentConfig(system_instruction=self.system_prompt),
                    contents=text
                )
                reply = res_g.text
            except Exception as e:
                print(f"[LLM] Sub1(Google) Error: {e}")

        # 3. Sub2: Groq (Backup)
        gr_key = self.config.get("groq_api_key")
        if not reply and gr_key:
            try:
                print(f"[LLM] Sub2(Groq)へ切り替えます...")
                client_gr = OpenAI(api_key=gr_key, base_url="https://api.groq.com/openai/v1")
                res_gr = client_gr.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    timeout=10
                )
                reply = res_gr.choices[0].message.content
            except Exception as e:
                print(f"[LLM] Sub2(Groq) Error: {e}")

        if reply:
            # アプリ起動チェック
            self._handle_apps(reply)
            
            # --- テキストのクリーニング ---
            # ここで re.sub を使うので、1行目の import re が必須です
            clean_reply = re.sub(r"\[LAUNCH:.*?\]", "", reply)
            clean_reply = re.sub(r"\*\*|\*|#|`|_|>", "", clean_reply)
            clean_reply = re.sub(r"\n+", "\n", clean_reply).strip()
            
            print(f"[LLM] 最終応答: {clean_reply}")

            if self.pm and clean_reply:
                self.pm.hook.on_llm_response_generated(response_text=clean_reply)
        else:
            print("[LLM] 警告: 全てのAPIが利用不可です。")

    def _handle_apps(self, text):
        # ここでも re を使用します
        match = re.search(r"\[LAUNCH:(.*?)\]", text)
        if match:
            app_name = match.group(1).strip()
            apps_raw = str(self.config.get("apps_raw", ""))
            apps_map = {}
            for line in apps_raw.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    apps_map[k.strip()] = v.strip()
            
            if app_name in apps_map:
                print(f"[LLM] アプリ起動を実行: {app_name}")
                try:
                    subprocess.Popen(apps_map[app_name], shell=True)
                except Exception as e:
                    print(f"[LLM] アプリ起動エラー: {e}")

    def on_plugin_loaded(self, pm):
        self.pm = pm