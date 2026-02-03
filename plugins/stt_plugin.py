import pluggy
import speech_recognition as sr
import whisper
import tempfile
import os
import threading
import re

hookimpl = pluggy.HookimplMarker("komomo")

class Plugin:
    def __init__(self, config):
        self.config = config
        self.pm = None
        self.is_recording = False
        self.model = None
        self.recognizer = sr.Recognizer()

    def on_plugin_loaded(self, pm):
        self.pm = pm
        # モデルロードは重いので別スレッドまたは初回のみにするが、
        # ここでは起動時に読み込んでおく
        print("[STT] Whisperモデル(small)を読み込んでいます...")
        self.model = whisper.load_model("small")
        print("[STT] 準備完了。")

    @hookimpl
    def on_start_recording_requested(self):
        """録音開始リクエストを受信"""
        if not self.is_recording:
            self.is_recording = True
            # 別スレッドで録音処理を開始（GUIを固めないため）
            threading.Thread(target=self._record_and_transcribe).start()

    @hookimpl
    def on_stop_recording_requested(self):
        """録音停止リクエストを受信"""
        # speech_recognition の listen は途中で止めにくいが、
        # フラグを下ろすことでループ制御などに使う（今回は listen(timeout) 頼り）
        self.is_recording = False

    def _record_and_transcribe(self):
        """マイクから音声を録音して文字起こし"""
        print("[STT] 録音開始...")
        
        # マイク設定
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                self.recognizer.energy_threshold = 400
                
                # 録音実行 (ユーザーが話し終わるか、制限時間が来るまで)
                # v3.0 audio_service.py のパラメータ準拠
                audio_data = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
                print("[STT] 録音完了。解析中...")
                
                # 一時ファイルに保存
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                    f.write(audio_data.get_wav_data())
                    wav_path = f.name

                # Whisperで文字起こし
                result = self.model.transcribe(
                    wav_path,
                    language="ja",
                    beam_size=5,
                    no_speech_threshold=0.6,
                    condition_on_previous_text=False
                )
                text = result["text"].strip()
                
                # 一時ファイル削除
                if os.path.exists(wav_path):
                    os.remove(wav_path)

                if text:
                    print(f"[STT] 認識結果: {text}")
                    # 認識できたらシステムに入力として投げる
                    if self.pm:
                        self.pm.hook.on_query_received(text=text)
                else:
                    print("[STT] 音声を認識できませんでした。")

        except Exception as e:
            print(f"[STT] Error: {e}")
        finally:
            self.is_recording = False
            # GUI側へ「録音終わったよ（停止状態に戻して）」と通知する仕組みが必要だが、
            # 現状はGUI側で自動的に戻るか、status更新で対応する