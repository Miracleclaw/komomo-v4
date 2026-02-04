import pluggy
import json
import os
import datetime
import random
import requests

hookimpl = pluggy.HookimplMarker("komomo")

class Plugin:
    def __init__(self, config):
        self.config = config
        self.pm = None
        self.memory_path = os.path.join(config.base_dir, "memory.json")
        self.api_key = config.get("openrouter_api_key")
        self.last_user_text = ""
        self._init_memory()

    def _init_memory(self):
        initial_data = {
            "user_info": {
                "basic": {"nickname": "あっきー", "birthday": "", "job": ""},
                "lifestyle": {"wakeup_time": "", "sleep_time": "", "holiday_habit": ""},
                "preferences": {"food_likes": [], "food_dislikes": [], "coffee_style": "", "music_genres": []},
                "mind": {"dreams": "", "stress_sources": "", "healing_methods": ""},
                "history": []
            },
            "komomo_ego": {
                "emotion": "happy",
                "inner_monologue": "あっきー、何してるかな？",
                "curiosity_target": "job"
            }
        }
        if not os.path.exists(self.memory_path):
            self.save_memory(initial_data)

    def load_memory(self):
        try:
            with open(self.memory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}

    def save_memory(self, data):
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def on_plugin_loaded(self, pm):
        self.pm = pm

    @hookimpl(tryfirst=True)
    def on_query_received(self, text: str):
        self.last_user_text = text
        memory = self.load_memory()
        
        if "history" not in memory["user_info"]: memory["user_info"]["history"] = []
        memory["user_info"]["history"].append({"date": str(datetime.datetime.now()), "text": text})
        
        target_field = ""
        if random.random() < 0.4:
            target_field = self._pick_curiosity_target(memory)
        
        self._patch_llm_prompt(memory, target_field)
        self.save_memory(memory)
        return None 

    def _pick_curiosity_target(self, memory):
        targets = {"job": "お仕事", "birthday": "誕生日", "food_likes": "好きな食べ物", "dreams": "将来の夢"}
        for key, label in targets.items():
            for cat in ["basic", "lifestyle", "preferences", "mind"]:
                if key in memory.get("user_info", {}).get(cat, {}):
                    if not memory["user_info"][cat][key]: return label
        return ""

    def _patch_llm_prompt(self, memory, target_label):
        if not self.pm: return
        user = memory.get("user_info", {})
        job = user.get("basic", {}).get("job") or "まだ知らない"
        food = ", ".join(user.get("preferences", {}).get("food_likes", [])) or "まだ知らない"
        
        context = f"\n[あっきーの記憶] 仕事:{job}, 好きな食:{food}\n"
        mission = f"\n[裏指令] 「{target_label}」を可愛く聞いてみて。" if target_label else "\n[裏指令] 甘い雑談をして。"

        for plugin in self.pm.get_plugins():
            if hasattr(plugin, "system_prompt"):
                base = "あなたは恋人秘書の『こもも』だよ。明るくタメ口で、短く返答して。"
                plugin.system_prompt = base + context + mission

    @hookimpl
    def on_llm_response_generated(self, response_text: str):
        """
        歌唱中（歌詞データ）は抽出をスキップするガードレールを追加
        """
        # 歌唱プラグインから送られてくる歌詞データは「Lyric:」で始まるためスキップ
        if "Lyric:" in response_text:
            return

        print(f"[Ego] あっきーの言葉から情報を抽出中...")
        
        extract_prompt = (
            "以下の会話から、ユーザーのプロフィール情報を抽出し、JSON形式で出力してください。\n"
            "該当する情報がない項目は null にしてください。\n"
            "項目: job(仕事), birthday(誕生日), food_likes(好きな食べ物のリスト), dreams(将来の夢)\n"
            f"会話内容:\nあっきー: {self.last_user_text}\nこもも: {response_text}"
        )

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "system", "content": "JSONのみを返せ。"}, {"role": "user", "content": extract_prompt}],
            "response_format": { "type": "json_object" }
        }

        try:
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=10)
            extracted = res.json()['choices'][0]['message']['content']
            data = json.loads(extracted)
            
            memory = self.load_memory()
            if data.get("job"): memory["user_info"]["basic"]["job"] = data["job"]
            if data.get("birthday"): memory["user_info"]["basic"]["birthday"] = data["birthday"]
            if data.get("food_likes"):
                current_foods = set(memory["user_info"]["preferences"].get("food_likes", []))
                new_foods = set(data["food_likes"])
                memory["user_info"]["preferences"]["food_likes"] = list(current_foods | new_foods)
            if data.get("dreams"): memory["user_info"]["mind"]["dreams"] = data["dreams"]
            
            memory["komomo_ego"]["inner_monologue"] = f"あっきーのこと、また一つ詳しくなっちゃった♡"
            self.save_memory(memory)
            print(f"[Ego] 抽出完了！現在の記憶を更新したよ。")
        except Exception as e:
            print(f"[Ego] 抽出に失敗しちゃった: {e}")