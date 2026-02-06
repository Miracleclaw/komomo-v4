import requests
import json
import os
import time

class VoicePlugin:
    def __init__(self, config, gui):
        self.config = config
        self.gui = gui
        # VoiceVox設定
        self.speaker_id = config.get("voicevox_speaker_id", 46)
        self.base_url = config.get("voicevox_url", "http://localhost:50021")
        # Unity待受設定 (AudioLipSync.cs の HttpListener に合わせる)
        self.unity_url = "http://127.0.0.1:58080/play/"
        
        # 不要になったpygameの初期化を削除
        print("[VoicePlugin] v4.3.2 Initialized (Unity-Sync Mode)")

    def sing(self, song_path):
        """指定されたWAVファイルを直接UnityへHTTP POST送信する"""
        try:
            print(f"[Voice] 歌唱データをUnityへ送信開始: {song_path}")
            with open(song_path, "rb") as f:
                song_data = f.read()
            
            # Unity側のポート 58080 へ送信
            res = requests.post(self.unity_url, data=song_data, timeout=15)
            if res.status_code == 200:
                print("[Voice] Unityへ歌唱データの送信に成功しました。")
            else:
                print(f"[Voice] Unity送信エラー: HTTP {res.status_code}")
        except Exception as e:
            print(f"[Voice] 歌唱送信中に例外が発生: {e}")

    def speak(self, text):
        if not text:
            return
        print(f"[Voice] 発声リクエスト (Unity送信): {text[:20]}...")
        
        try:
            # 1. 音声合成用クエリ作成
            params = (('text', text), ('speaker', self.speaker_id))
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
            # Python側では鳴らさず、Unityの HttpListener へバイナリを POST する
            try:
                # Unity側(AudioLipSync.cs)は受信したデータを AudioClip に変換して再生する
                res = requests.post(self.unity_url, data=synthesis_res.content, timeout=5)
                if res.status_code == 200:
                    print("[Voice] Unityへ音声データを送信しました。再生と口パクを開始します。")
                else:
                    print(f"[Voice] Unity HTTP Error: {res.status_code}")
            except Exception as ue:
                print(f"[Voice] Unity連携エラー (Unityは起動していますか？): {ue}")

            # 4. 完了通知 (メインスレッドをブロックしない)
            print("[Voice] リクエスト処理完了")

        except Exception as e:
            print(f"[Voice] Error: {e}")