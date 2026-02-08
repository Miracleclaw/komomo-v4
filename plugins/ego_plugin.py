"""
Komomo System Plugin - Ego & Emotion Controller
Version: v4.3.0.13

[役割]
感情分析とハイブリッド記憶管理。
ユーザーの好みや事実を敏感に抽出する強化プロンプトを搭載。
不正な感情ID（1, 102等）を排除し、厳格に 12, 13, 17, 20 に制限。
旧来のJSONメモリ管理を廃止し、SQLite + ChromaDB に完全移行。
"""
import json
import requests
import os
import sqlite3
import traceback
from datetime import datetime
import chromadb

class EgoPlugin:
    def __init__(self, config, gui):
        self.config = config
        self.gui = gui
        self.pm = None 
        self.db_path = "komomo_v4_memory.db"
        
        # 使用するOpenAIモデル（無料枠リスト内のモデルを指定）
        self.openai_model = "gpt-4o-mini-2024-07-18"
        
        # 1. SQLite初期化
        self._init_db()
        
        # 2. ChromaDB (ベクトルDB) 初期化
        try:
            # プロジェクトフォルダ内に chroma_db ディレクトリを作成しデータを永続化
            self.chroma_client = chromadb.PersistentClient(path="./chroma_db")
            # キーワード検索モードでコレクションを取得/作成
            self.collection = self.chroma_client.get_or_create_collection(name="komomo_memories")
        except Exception as e:
            print(f"[Ego] ChromaDB初期化失敗: {e}")
        
        print(f"[EgoPlugin] v4.3.0.13 Initialized (Clean Hybrid DB Mode)")

    def _init_db(self):
        """SQLiteテーブルの初期化"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''CREATE TABLE IF NOT EXISTS user_profile 
                                (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP)''')
                cursor.execute('''CREATE TABLE IF NOT EXISTS system_status 
                                (key TEXT PRIMARY KEY, value TEXT)''')
                cursor.execute('''CREATE TABLE IF NOT EXISTS conversation_history 
                                (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                                 user_text TEXT, ai_response TEXT, 
                                 inner_monologue TEXT, emotion_id TEXT, 
                                 created_at TIMESTAMP)''')
                conn.commit()
        except Exception as e:
            print(f"[EgoPlugin] DB初期化エラー: {e}")

    def _get_search_keywords(self, text):
        """OpenAIモデルを使って検索用のキーワード（意味タグ）を抽出する"""
        key = self.config.get("openai_api_key")
        if not key:
            return text
            
        try:
            res = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.openai_model,
                    "messages": [
                        {"role": "system", "content": "Extract 3-5 search keywords from the user input as a comma-separated list. Focus on entities, events, and topics."},
                        {"role": "user", "content": text}
                    ],
                    "temperature": 0
                }, timeout=10
            )
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
            else:
                return text
        except:
            return text

    def search_semantic_memories(self, query_text, n_results=2):
        """今の話題に関連する過去の思い出を検索する"""
        try:
            # 検索キーワードを生成
            search_tags = self._get_search_keywords(query_text)
            
            # ChromaDBから検索（テキストベースのマッチング）
            results = self.collection.query(
                query_texts=[search_tags],
                n_results=n_results
            )
            
            if not results or not results['documents'][0]:
                return ""
                
            memory_context = "\n### 関連する過去の思い出 ###\n"
            for doc in results['documents'][0]:
                memory_context += f"・{doc}\n"
            memory_context += "###########################\n"
            return memory_context
        except Exception as e:
            print(f"[Ego] 記憶検索エラー: {e}")
            return ""

    def get_user_profile_summary(self):
        """DBからプロフィールを取得"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT key, value FROM user_profile")
                rows = cursor.fetchall()
                if not rows: return ""
                summary = "\n### あなたが覚えているあっきーの情報 ###\n"
                for key, value in rows:
                    summary += f"・{key}: {value}\n"
                summary += "########################################\n"
                return summary
        except: return ""

    def get_recent_memories(self, limit=5):
        """DBから最新の会話履歴を取得"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_text, ai_response FROM conversation_history ORDER BY id DESC LIMIT ?', (limit,))
                rows = cursor.fetchall()
                if not rows: return ""
                rows.reverse()
                memory_text = "\n### 最近の二人の会話の思い出 ###\n"
                for user, ai in rows:
                    memory_text += f"あっきー: {user}\nこもも: {ai}\n"
                memory_text += "##################################\n"
                return memory_text
        except: return ""

    def extract_info_from_dialogue(self, user_text, ai_response):
        """分析と保存の実行"""
        key = self.config.get("openrouter_api_key")
        if not key: return

        model_id = "meta-llama/llama-3.3-70b-instruct"
        
        # 好み抽出を強化したプロンプト
        prompt = f"""Extract data into JSON for "Komomo".
        User says: "{user_text}"
        Komomo responds: "{ai_response}"

        ### 1. NEW INFO EXTRACTION (CRITICAL):
        Identify any personal facts about the user (e.g., likes, dislikes, habits, occupation, preference).
        Even small details like "likes baths" or "drinks coffee" must be extracted.
        Format: "new_facts": {{"key": "value"}}
        Example: "new_facts": {{"favorite_bath": "true", "coffee_style": "no sugar"}}
        If no new info, return "new_facts": null.

        ### 2. EMOTION:
        ID: 13(Music/Excited), 17(Happy), 12(Normal).
        
        ### Required JSON Format:
        {{
            "emotion_stats": {{"joy": 50, "trust": 50, "tension": 20}},
            "emotion_id": "12",
            "inner_monologue": "text",
            "new_facts": {{ "key": "value" }}
        }}
        """
        try:
            res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "HTTP-Referer": "http://localhost"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}},
                timeout=15
            )
            if res.status_code == 200:
                data = json.loads(res.json()["choices"][0]["message"]["content"])
                raw_val = str(data.get("emotion_id", "12")).lower()
                final_id = self._robust_parse_id(raw_val)
                print(f"[Ego] Llama 3.3 受信: '{raw_val}' -> 最終決定={final_id}")
                self.send_to_unity(final_id)
                self._save_to_db(user_text, ai_response, data, final_id)
        except Exception as e:
            print(f"[Ego] 分析失敗: {e}")

    def _save_to_db(self, user_text, ai_response, data, final_id):
        """SQLite + ChromaDB への永続化"""
        try:
            now = datetime.now().isoformat()
            
            # SQLite保存
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                new_stats = data.get("emotion_stats")
                if new_stats:
                    cursor.execute("INSERT OR REPLACE INTO system_status (key, value) VALUES (?, ?)", ("last_emotion", json.dumps(new_stats)))
                cursor.execute('INSERT INTO conversation_history (user_text, ai_response, inner_monologue, emotion_id, created_at) VALUES (?, ?, ?, ?, ?)',
                             (user_text, ai_response, data.get("inner_monologue"), str(final_id), now))
                
                # 事実の保存とログ出力
                new_facts = data.get("new_facts")
                if isinstance(new_facts, dict) and new_facts:
                    for k, v in new_facts.items():
                        print(f"[Ego] ★新しい記憶を保存: {k} = {v}")
                        cursor.execute("INSERT OR REPLACE INTO user_profile (key, value, updated_at) VALUES (?, ?, ?)", (k, str(v), now))
                conn.commit()

            # ChromaDB保存
            mem_text = f"あっきー: {user_text}\nこもも: {ai_response}"
            self.collection.add(
                documents=[mem_text],
                metadatas=[{"timestamp": now}],
                ids=[f"mem_{datetime.now().timestamp()}"]
            )
            print("[Ego] ChromaDBに思い出を保存しました。")

        except Exception as e:
            print(f"[Ego] 保存エラー: {e}")

    def _robust_parse_id(self, raw_val):
        """不正なID（1, 102等）を排除し、許可された値のみを返す"""
        raw_val = raw_val.lower()
        is_singing = False
        if self.pm:
            for p in self.pm.get_plugins():
                if p.__class__.__name__ in ["KomomoSystem", "SongPlugin"]:
                    is_singing = is_singing or getattr(p, "is_singing_now", False) or getattr(p, "is_singing", False)

        # 1. 歌唱中キーワード判定
        if any(k in raw_val for k in ["song", "sing", "20"]):
            return 20 if is_singing else 13
        
        # 2. ポジティブキーワード判定
        if any(k in raw_val for k in ["happy", "excite", "joy", "楽"]):
            return 17

        # 3. 数値チェックとガード
        try:
            t_id = int(raw_val)
            if t_id in [12, 13, 17, 20]:
                if t_id == 20 and not is_singing: return 13
                return t_id
            return 12
        except:
            return 12

    def send_to_unity(self, emotion_id):
        try:
            requests.post("http://127.0.0.1:58080/play/", json={"action": "expression", "index": int(emotion_id)}, timeout=5)
            print(f"[Ego] Unityへ表情ID {emotion_id} を送信しました")
        except: pass

    def on_plugin_loaded(self, pm):
        self.pm = pm