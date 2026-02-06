import requests
import json
import pygame
import tempfile
import os
import time

class VoicePlugin:
    def __init__(self, config, gui):
        self.config = config
        self.gui = gui
        self.speaker_id = config.get("voicevox_speaker_id", 46)
        self.base_url = config.get("voicevox_url", "http://localhost:50021")
        # pygameのミキサーを初期化
        pygame.mixer.init()
        print("[VoicePlugin] v4.1.9 Initialized (using pygame)")

    def speak(self, text):
        if not text: return
        print(f"[Voice] 発声リクエスト: {text[:20]}...")
        
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

            # 3. 再生 (pygame)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(synthesis_res.content)
                temp_path = f.name
            
            try:
                pygame.mixer.music.load(temp_path)
                pygame.mixer.music.play()
                # 再生が終わるまで待機
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                pygame.mixer.music.unload() # ファイルを解放
            except Exception as e:
                print(f"[Voice] Playback Error: {e}")
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass # 使用中の場合はスキップ
            
            print("[Voice] 再生完了")

        except Exception as e:
            print(f"[Voice] Error: VoiceVoxの起動確認をしてください。({e})")