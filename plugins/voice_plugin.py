"""
Komomo System Plugin - Voice Synthesis & Unity Sync
Version: v4.2.0

[役割]
こももの「声」と「Unity通信」を制御するプラグイン。
VoiceVoxでの音声合成、および生成した音声・指示バイナリの
Unity側へのソケット送信を担当します。

[主な機能]
- VoiceVox APIを利用したテキストからの音声合成
- 音声バイナリデータのUnityへのリアルタイム送信
- 歌唱データ（WAV）の転送および再生指示
"""
import requests
import json
import os
import time
import re
import pluggy  # NameErrorを解消するために追加

class VoicePlugin:
    def __init__(self, config, gui):
        self.config = config
        self.gui = gui
        # VoiceVox設定
        self.speaker_id = config.get("voicevox_speaker_id", 46)
        self.base_url = config.get("voicevox_url", "http://localhost:50021")
        
        # Unity待受設定
        # 音声・歌唱バイナリ送信先
        self.unity_url = "http://127.0.0.1:58080/play/"
        # 歌詞テキスト送信先
        self.unity_lyrics_url = "http://127.0.0.1:58080/lyrics/"
        
        print("[VoicePlugin] v4.1.9.4 Initialized (Unity-Sync Mode)")

    def sing(self, song_path):
        """指定されたWAVファイルを直接UnityへHTTP POST送信する"""
        try:
            print(f"[Voice] 歌唱データをUnityへ送信開始: {song_path}")
            if not os.path.exists(song_path):
                print(f"[Voice] Error: ファイルが見つかりません {song_path}")
                return

            with open(song_path, "rb") as f:
                song_data = f.read()
            
            # Unity側のポート 58080 へバイナリ送信
            res = requests.post(self.unity_url, data=song_data, timeout=15)
            if res.status_code == 200:
                print("[Voice] Unityへ歌唱データの送信に成功しました。")
            else:
                print(f"[Voice] Unity送信エラー: HTTP {res.status_code}")
        except Exception as e:
            print(f"[Voice] 歌唱送信中に例外が発生: {e}")

    def speak(self, text):
        """テキストを音声合成し、Unityへ送信して再生・口パクさせる"""
        if not text:
            return
        
        # 発声前に不要なタグ（(笑)など）をクリーニング
        clean_text = self._clean_text(text)

        print(f"[Voice] 発声リクエスト (Unity送信): {clean_text[:20]}...")
        
        try:
            # 1. 音声合成用クエリ作成
            params = (('text', clean_text), ('speaker', self.speaker_id))
            query_res = requests.post(f'{self.base_url}/audio_query', params=params, timeout=10)
            if query_res.status_code != 200:
                print(f"[Voice] Query Error: {query_res.status_code}")
                return
            query_data = query_res.json()

            # 2. 音声合成 (Synthesis)
            synthesis_res = requests.post(
                f'{self.base_url}/synthesis',
                headers={'Content-Type': 'application/json'},
                params={'speaker': self.speaker_id},
                data=json.dumps(query_data),
                timeout=30
            )
            if synthesis_res.status_code != 200:
                print(f"[Voice] Synthesis Error: {synthesis_res.status_code}")
                return

            # 3. Unityへの送信 (口パク・再生用)
            try:
                res = requests.post(self.unity_url, data=synthesis_res.content, timeout=5)
                if res.status_code == 200:
                    print("[Voice] Unityへ音声データを送信しました。")
                else:
                    print(f"[Voice] Unity HTTP Error: {res.status_code}")
            except Exception as ue:
                print(f"[Voice] Unity連携エラー (Unityは起動していますか？): {ue}")

            print("[Voice] リクエスト処理完了")

        except Exception as e:
            print(f"[Voice] Error: {e}")

    def clear_lyrics(self):
        """Unity側の歌詞表示を消去する"""
        try:
            # 空の文字列を送信して、表示を消す
            payload = {"text": ""}
            res = requests.post(self.unity_lyrics_url, json=payload, timeout=5)
            if res.status_code == 200:
                print("[Voice] Unityの歌詞表示をクリアしました。")
        except Exception as e:
            print(f"[Voice] 歌詞クリア送信エラー: {e}")

    def _clean_text(self, text):
        """発声時のゴミ（カッコやタグ）をクリーニング"""
        text = text.replace("（", "(").replace("）", ")")
        text = re.sub(r'\(.*?\)', '', text)
        text = re.sub(r'\[.*?\]', '', text)
        return text.strip()

    @pluggy.HookimplMarker("komomo")
    def on_llm_response_generated(self, response_text):
        """
        PluginManager経由で呼ばれるフック
        LLMの回答が生成されたら自動的に発声を開始する
        """
        self.speak(response_text)