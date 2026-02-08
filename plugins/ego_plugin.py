"""
Komomo System Plugin - Ego & Emotion Controller
Version: v4.2.1.0

[役割]
Llama 3.3 (OpenRouter) による感情分析と記憶管理。
AIに対して使用可能な表情IDを厳格に制限し、勝手な数値(15等)の生成を抑制します。
また、文字列で返答された場合もキーワードから適切にID:13やID:20へ導きます。
"""
import json
import requests
import os
import traceback

class EgoPlugin:
    def __init__(self, config, gui):
        self.config = config
        self.gui = gui
        self.pm = None # PluginManager保持用
        self.memory_path = "memory.json"
        self.memory = self._load_memory()
        print("[EgoPlugin] Initialized (OpenRouter / Llama 3.3 / Strict-ID Mode)")

    def on_plugin_loaded(self, pm):
        """システムの状態を参照するためにPMを保持"""
        self.pm = pm
        print("[EgoPlugin] PluginManager connected.")

    def _load_memory(self):
        """メモリの読み込み（構造を保証する）"""
        default_memory = {"user_data": {}, "last_emotion": {"joy": 50, "trust": 50, "tension": 20}}
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "last_emotion" not in data:
                        data["last_emotion"] = default_memory["last_emotion"]
                    if "user_data" not in data:
                        data["user_data"] = {}
                    return data
            except:
                return default_memory
        return default_memory

    def extract_info_from_dialogue(self, user_text, ai_response):
        """OpenRouter (Llama 3.3) を使って感情分析"""
        key = self.config.get("openrouter_api_key")
        if not key: return

        model_id = "meta-llama/llama-3.3-70b-instruct"

        # AIに勝手な数字を作らせないための厳格なプロンプト
        prompt = f"""
        Extract dialogue data into JSON format for the character "Komomo".
        User "{user_text}", Komomo "{ai_response}"

        ### EMOTION_ID RULES (STRICT):
        Choose ONLY ONE ID from this list. DO NOT create new numbers or intermediate values:
        - "13": Use for MUSIC, SINGING, or feeling very excited.
        - "17": Use for general HAPPY or JOYFUL feelings.
        - "12": Use for NORMAL or calm conversation.

        Required JSON Format:
        {{
            "emotion_stats": {{"joy": 50, "trust": 50, "tension": 20}},
            "emotion_id": "12",
            "inner_monologue": "text"
        }}
        """
        
        try:
            res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "HTTP-Referer": "http://localhost",
                },
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"}
                }, timeout=15
            )
            
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]
                data = json.loads(content)
                
                # raw_id を取得 (小文字の文字列として処理)
                raw_val = str(data.get("emotion_id", "12")).lower()
                
                # --- 強力なパースロジックの呼び出し ---
                final_id = self._robust_parse_id(raw_val)
                
                print(f"[Ego] Llama 3.3 受信: '{raw_val}' -> 最終決定={final_id}")
                
                # 表情送信を優先的に実行
                self.send_to_unity(final_id)
                
                try:
                    self._save_memory(data)
                except Exception as e:
                    print(f"[Ego] メモリ保存エラー (無視): {e}")
            else:
                print(f"[Ego] OpenRouter Error: {res.status_code} {res.text}")

        except Exception as e:
            print(f"[Ego] 感情分析中に例外が発生しました: {e}")
            traceback.print_exc()

    def _robust_parse_id(self, raw_val):
        """Llama 3.3 が返す 'happy_excitement' 等の単語を ID:13 へ翻訳する"""
        
        # 1. 歌唱中フラグを確認
        is_singing = False
        if self.pm:
            for p in self.pm.get_plugins():
                p_name = p.__class__.__name__
                if p_name == "KomomoSystem":
                    is_singing = getattr(p, "is_singing_now", False)
                elif p_name == "SongPlugin":
                    is_singing = is_singing or getattr(p, "is_singing", False)

        # 2. キーワード救済 (Llamaの表現の揺らぎを吸収)
        # 「歌」に関連するか、もしくは「幸せ・ワクワク」系の言葉が含まれていれば 13 にする
        happy_keywords = ["song", "sing", "20", "happy", "excite", "joy", "楽"]
        if any(keyword in raw_val for keyword in happy_keywords):
            if is_singing:
                return 20 # 歌唱中なら本番ポーズ
            else:
                print(f"[Ego] ★救済発動: '{raw_val}' からポジティブな感情を検知 -> 音符(13)に変更")
                return 13 # 雑談なら音符

        # 3. 通常の数値変換
        try:
            target_id = int(raw_val)
            # 歌唱中でないのに 20 が選ばれた場合は 13 に振替
            if target_id == 20 and not is_singing:
                return 13
            return target_id
        except:
            # 数値変換できない場合はデフォルトの12
            return 12

    def _save_memory(self, data):
        """分析データの保存"""
        new_stats = data.get("emotion_stats")
        if new_stats:
            self.memory["last_emotion"] = new_stats
            
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, indent=4, ensure_ascii=False)

    def send_to_unity(self, emotion_id):
        """Unityへ表情IDを送信"""
        try:
            unity_url = "http://127.0.0.1:58080/play/"
            payload = {"action": "expression", "index": int(emotion_id)}
            requests.post(unity_url, json=payload, timeout=5)
            print(f"[Ego] Unityへ表情ID {emotion_id} を送信しました")
        except Exception as e:
            print(f"[Ego] Unity表情送信エラー: {e}")

    def _send_to_unity(self, emotion_id):
        self.send_to_unity(emotion_id)