"""
Komomo System Plugin - Song & Concert Controller
Version: v4.2.0

[役割]
歌唱機能およびコンサートモードを司るプラグイン。
会話ロジックから歌唱処理を分離し、独立したスレッドで演出を制御します。

[主な機能]
- 「歌って」「コンサート」等のキーワードに対する割り込み処理
- 指定曲数（3〜5曲）のランダム選曲と連続再生
- 歌唱中の表情(Unity)および歌詞(GUI)の同期制御
- コンサート終了後の自動挨拶および表情リセット
"""
import re
import pluggy
import os
import threading
import random
import time
import wave
import contextlib

hookimpl = pluggy.HookimplMarker("komomo")
SONGS_DIR = os.path.join(os.getcwd(), "songs")

class Plugin:
    def __init__(self, config):
        self.config = config
        self.pm = None
        self.is_singing = False

    def on_plugin_loaded(self, pm):
        """PluginManagerを受け取り、保持する"""
        self.pm = pm
        print("[SongPlugin] PluginManager Loaded.")

    @hookimpl(tryfirst=True)
    def on_query_received(self, text: str):
        """歌唱・コンサート判定の司令塔"""
        # --- 歌唱中はすべての入力を遮断し、LLMに渡さない ---
        if self.is_singing: 
            print(f"[SongPlugin] 歌唱中のため入力をブロックしました: {text[:10]}...")
            return True 

        normalized_text = re.sub(r'[。\?？!！、\s]', '', text)

        # 判定キーワード
        is_concert = any(k in normalized_text for k in ["コンサート", "ライブ"])
        is_singing = any(k in normalized_text for k in ["歌って", "うたって", "歌唱"])

        if is_concert or is_singing:
            if not os.path.exists(SONGS_DIR):
                print(f"[SongPlugin] Error: {SONGS_DIR} が見つかりません。")
                return False

            all_wavs = [f for f in os.listdir(SONGS_DIR) if f.endswith(".wav")]
            if not all_wavs:
                print("[SongPlugin] 再生可能な曲(wav)がありません。")
                return False

            if is_concert:
                # コンサートモード：3～5曲をランダム抽出
                count = min(len(all_wavs), random.randint(3, 5))
                selected = random.sample(all_wavs, count)
                print(f"[SongPlugin] コンサート開始: 全{len(selected)}曲")
            else:
                # 通常歌唱：1曲をランダム抽出
                selected = [random.choice(all_wavs)]
                print(f"[SongPlugin] 通常歌唱開始: {selected[0]}")
            
            # 非同期で歌唱シーケンスを開始（メインスレッドをブロックしない）
            threading.Thread(target=self._singing_sequence, args=(selected, is_concert), daemon=True).start()
            return True # 以降のプラグイン(LLM等)の処理をスキップさせる

    def _singing_sequence(self, files, is_concert):
        """歌唱・演出・クリーンアップの連鎖処理"""
        if not self.pm:
            print("[SongPlugin] Error: PluginManager not set.")
            return

        self.is_singing = True
        
        # メインシステム側の歌唱中フラグも更新（会話の割り込みを防止）
        for p in self.pm.get_plugins():
            if p.__class__.__name__ == "KomomoSystem":
                p.is_singing_now = True

        # 各プラグインへの直接参照を取得（読み上げ回避のため）
        voice_p = None
        ego_p = None
        gui_p = None
        for p in self.pm.get_plugins():
            p_name = p.__class__.__name__
            if p_name == "VoicePlugin": voice_p = p
            if p_name == "EgoPlugin": ego_p = p
            if p_name == "GUIPlugin": gui_p = p

        # 1. イントロのセリフ（これは喋らせる）
        intro_text = "コンサート、始めちゃうよ！" if is_concert else "私の歌、聴いてほしいな。"
        self.pm.hook.on_llm_response_generated(response_text=intro_text)
        time.sleep(2.5)

        for fname in files:
            # 表情制御：ID:20（歌唱用）を直接送信
            if ego_p and hasattr(ego_p, "send_to_unity"):
                ego_p.send_to_unity(20)
            
            # 2. 歌詞データの送信
            raw_key = os.path.splitext(fname)[0]
            l_path = os.path.join(SONGS_DIR, f"{raw_key}.txt")
            if os.path.exists(l_path):
                try:
                    with open(l_path, "r", encoding="utf-8") as f:
                        lyrics = f.read()
                        # GUIウィンドウに表示
                        if gui_p and hasattr(gui_p, "_show_lyric_window"):
                            gui_p._show_lyric_window(lyrics)
                except Exception as e:
                    print(f"[SongPlugin] 歌詞読み込みエラー: {e}")

            # 3. 曲データの送信
            wav_path = os.path.join(SONGS_DIR, fname)
            if voice_p and hasattr(voice_p, "sing"):
                voice_p.sing(wav_path)

            # 曲が終わるまで待機（この間もブロックフラグを維持）
            duration = self._get_wav_duration(wav_path)
            time.sleep(duration + 1.5)

            # 歌詞カードを閉じる
            if gui_p and hasattr(gui_p, "_close_lyric_window"):
                gui_p._close_lyric_window()
            if voice_p and hasattr(voice_p, "clear_lyrics"):
                voice_p.clear_lyrics()

        # コンサート終了：表情を通常(12)に戻す
        if ego_p and hasattr(ego_p, "send_to_unity"):
            ego_p.send_to_unity(12)
        
        if is_concert:
            time.sleep(1.0)
            # 感謝の言葉
            self.pm.hook.on_llm_response_generated(response_text="聴いてくれてありがとう。")
            time.sleep(2.5) # 最後のセリフが終わるまでブロックを維持
        
        # フラグを解除して通常会話を許可
        self.is_singing = False
        for p in self.pm.get_plugins():
            if p.__class__.__name__ == "KomomoSystem":
                p.is_singing_now = False

        print("[SongPlugin] 歌唱シーケンス終了。通常モードに戻ります。")

    def _get_wav_duration(self, file_path):
        """wavファイルの長さを秒で取得"""
        try:
            with contextlib.closing(wave.open(file_path, 'r')) as f:
                frames = f.getnframes()
                rate = f.getframerate()
                return frames / float(rate)
        except Exception as e:
            print(f"[SongPlugin] duration取得失敗: {e}")
            return 180.0