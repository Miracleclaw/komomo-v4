import pluggy
import threading
import time
import speech_recognition as sr
import whisper
import os
import torch

hookimpl = pluggy.HookimplMarker("komomo")

class STTPlugin:
    def __init__(self, config, gui):
        self.config = config
        self.pm = None
        self.recognizer = sr.Recognizer()
        self.model_size = config.get("whisper_model", "small")
        self.model = None
        self.is_running = True
        self.is_recording = False
        self.stop_requested = False
        # マイクをインスタンス変数として保持し、何度も生成されないようにする
        self.source = sr.Microphone()

    def on_plugin_loaded(self, pm):
        self.pm = pm
        threading.Thread(target=self._load_model_and_loop, daemon=True).start()

    def _load_model_and_loop(self):
        print(f"[STT] Whisperモデル({self.model_size})を読み込んでいます...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = whisper.load_model(self.model_size, device=device)
        print(f"[STT] 準備完了。")

        while self.is_running:
            if self.is_recording:
                self._record_and_transcribe()
            else:
                time.sleep(0.1)

    @hookimpl
    def start_recording(self):
        self.stop_requested = False
        self.is_recording = True

    @hookimpl
    def stop_recording(self):
        self.stop_requested = True

    def _record_and_transcribe(self):
        print("[STT] 録音開始 (最大30秒)...")
        audio_data_list = []
        
        # 修正：listen_in_background に直接 self.source を渡す
        # これにより内部で適切にコンテキスト管理が行われ、二重オープンを防げるよ
        stop_listening = self.recognizer.listen_in_background(
            self.source, 
            lambda r, a: audio_data_list.append(a)
        )
        
        start_time = time.time()
        while not self.stop_requested:
            if time.time() - start_time > 30:
                print("[STT] 30秒制限により自動停止します。")
                break
            time.sleep(0.05)
        
        # 録音停止
        stop_listening(wait_for_stop=False)
        self.is_recording = False
        
        if not audio_data_list:
            print("[STT] 音声データが検出されませんでした。")
            return
        
        print("[STT] 録音完了。解析中...")
        combined_raw = b"".join([a.get_raw_data() for a in audio_data_list])
        combined_audio = sr.AudioData(
            combined_raw,
            audio_data_list[0].sample_rate,
            audio_data_list[0].sample_width
        )
        
        path = "temp_stt.wav"
        with open(path, "wb") as f:
            f.write(combined_audio.get_wav_data())
        
        try:
            result = self.model.transcribe(path, language="ja")
            text = result["text"].strip()
        except Exception as e:
            print(f"[STT] 解析エラー: {e}")
            text = ""
        finally:
            if os.path.exists(path):
                os.remove(path)

        if text and self.pm:
            print(f"[STT] 認識結果: {text}")
            self.pm.hook.on_query_received(text=text)