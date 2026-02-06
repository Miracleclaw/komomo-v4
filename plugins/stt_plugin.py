import pluggy
import threading
import time
import speech_recognition as sr
import whisper
import os
import torch
import traceback

hookimpl = pluggy.HookimplMarker("komomo")

class STTPlugin:
    def __init__(self, config, gui):
        self.config = config
        self.gui = gui
        self.pm = None
        self.recognizer = sr.Recognizer()
        
        # 感度設定
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.2  # 少し長めに待つ
        
        self.model_size = config.get("whisper_model", "small")
        self.model = None
        self.is_recording = False
        self.source = sr.Microphone()
        print(f"[STT] インスタンス生成完了")
        # ★ on_plugin_loadedを待たずにロードを開始する
        threading.Thread(target=self._load_model, daemon=True).start()

    def on_plugin_loaded(self, pm):
        self.pm = pm
        print(f"[STT] PluginManagerをセットしました")

    def _load_model(self):
        print(f"[STT] Whisperモデル({self.model_size})ロード開始...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = whisper.load_model(self.model_size, device=device)
        print(f"[STT] モデルロード完了。マイク入力準備OK。")

    @hookimpl
    def on_start_recording_requested(self):
        if self.is_recording:
            return
        print("[STT] 録音開始リクエストを受信 -> 録音スレッド起動")
        self.is_recording = True
        # ボタンが押されたら、その都度録音処理をスレッドで走らせる
        threading.Thread(target=self._record_process, daemon=True).start()

    @hookimpl
    def on_stop_recording_requested(self):
        # 今回は「無音検知」または「30秒」で自動停止するため、
        # ここではフラグ管理のみ（必要なら強制停止ロジックを組む）
        print("[STT] 録音停止リクエストを受信 (自動停止を待ちます)")
        self.is_recording = False

    def _record_process(self):
        """録音から解析までの一連のフロー"""
        print("[STT] >>> 録音フェーズ開始")
        if hasattr(self.gui, "update_status"):
            self.gui.update_status("きいてるよ... 🎤")

        try:
            with self.source as source:
                # 最初の0.5秒で環境音に慣らす
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                print("[STT] 聴取中... (話し終わると自動で解析します)")
                
                # phrase_time_limit: 最大30秒
                # timeout: 何も聞こえないまま5秒経ったら終了
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=30)
                
            print(f"[STT] 録音終了 (データ受信: {len(audio.get_wav_data())} bytes)")
            self._transcribe_and_send(audio)

        except sr.WaitTimeoutError:
            print("[STT] タイムアウト: 音声が検知されませんでした")
        except Exception as e:
            print(f"[STT] 録音エラー: {e}")
            traceback.print_exc()
        finally:
            self.is_recording = False
            if hasattr(self.gui, "update_status"):
                self.gui.update_status("スタンバイ OK ✨")

    def _transcribe_and_send(self, audio):
        """Whisper解析とメインへの送信"""
        # --- ↓ モデルがまだロード中の場合の待機を追加 ↓ ---
        if self.model is None:
            print("[STT] Whisperモデルのロードを待機しています...")
            if hasattr(self.gui, "update_status"):
                self.gui.update_status("準備中... ⏳")
            while self.model is None:
                time.sleep(0.5)
        
        print("[STT] Whisper解析開始...")
        if hasattr(self.gui, "update_status"):
            self.gui.update_status("考え中... ⏳")

        path = "temp_stt.wav"
        try:
            with open(path, "wb") as f:
                f.write(audio.get_wav_data())
            
            result = self.model.transcribe(path, language="ja")
            text = result["text"].strip()
            if text:
                print(f"[STT] 認識結果: 「{text}」")
                if self.pm:
                    print(f"[STT] -> PluginManager経由でメインに送信します")
                    self.pm.hook.on_query_received(text=text)
                else:
                    # ここが原因の可能性大！
                    print(f"[STT] !! 警告 !! self.pm が None です。送信に失敗しました。")
            else:
                print("[STT] 認識結果が空です") 

        except Exception as e:
            print(f"[STT] 解析エラー: {e}")
        finally:
            if os.path.exists(path):
                os.remove(path)