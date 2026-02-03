import re
import pluggy
import os
import threading
import pygame
import random
import time

hookimpl = pluggy.HookimplMarker("komomo")
SONGS_DIR = os.path.join(os.getcwd(), "songs")

class Plugin:
    def __init__(self, config):
        self.config = config
        self.pm = None
        self.is_singing = False
        try:
            pygame.mixer.init()
        except:
            pass

    def on_plugin_loaded(self, pm):
        self.pm = pm

    @hookimpl(tryfirst=True)
    def on_query_received(self, text: str):
        if self.is_singing: return True 

        if any(k in text for k in ["歌って", "コンサート", "ライブ"]):
            all_wavs = [f for f in os.listdir(SONGS_DIR) if f.endswith(".wav")]
            if not all_wavs: return True

            is_concert = any(k in text for k in ["コンサート", "ライブ"])
            if is_concert:
                count = min(len(all_wavs), random.randint(3, 5))
                selected = random.sample(all_wavs, count)
            else:
                selected = [random.choice(all_wavs)]
            
            print(f"[Song] 歌唱開始。曲数: {len(selected)}")
            threading.Thread(target=self._performance_thread, args=(selected,), daemon=True).start()
            return True

    def _performance_thread(self, files):
        self.is_singing = True

        for fname in files:
            # 1. イントロセリフ
            self.pm.hook.on_llm_response_generated(response_text="歌うね！")
            
            # --- 【重要】ここを追加！ ---
            # 「歌うね！」と言い終わるのを待つ（これがないと曲に上書きされて消える）
            time.sleep(2.0)

            # 2. 歌詞データの送信 (ログを汚さないよう静かに送る)
            raw_key = os.path.splitext(fname)[0]
            l_path = os.path.join(SONGS_DIR, f"{raw_key}.txt")
            if os.path.exists(l_path):
                try:
                    with open(l_path, "r", encoding="utf-8") as f:
                        lyrics = f.read()
                        self.pm.hook.on_llm_response_generated(response_text=f"Lyric:{lyrics}")
                except: pass

            # 3. 曲データの送信
            try:
                wav_path = os.path.join(SONGS_DIR, fname)
                with open(wav_path, "rb") as f:
                    wav_data = f.read()
                
                if self.pm:
                    self.pm.hook.on_audio_generated(audio_data=wav_data)
                    temp_sound = pygame.mixer.Sound(wav_path)
                    duration = temp_sound.get_length()
                    time.sleep(duration + 0.5) 
            except Exception as e:
                print(f"[Song] 再生エラー: {e}")
            
            self.pm.hook.on_llm_response_generated(response_text="Lyric:CLOSE")
            time.sleep(1.0)

        self.pm.hook.on_llm_response_generated(response_text="聴いてくれてありがとう！")
        self.is_singing = False