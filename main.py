import sys
import time
import os  # 追加
from core.host import get_plugin_manager
import re

def main():
    print("==========================================")
    print("   Komomo AI Assistant System v4.0 (Pluggy)")
    print("==========================================")

    pm = get_plugin_manager()

    print("\n[System] システムを起動しました。")
    print("[System] 声で話しかけるか、文字を入力してください。")
    print("[System] 'exit' で終了します。\n")

    try:
        while True:
            try:
                # 入力待ち
                user_text = input("あなた: ").strip()
            except EOFError:
                break

            if not user_text:
                time.sleep(0.1)
                continue
            
            if user_text.lower() in ["exit", "quit"]:
                break

            pm.hook.on_query_received(text=user_text)

    except KeyboardInterrupt:
        print("\n[System] 強制終了シグナルを受信しました。")
    finally:
        print("=== 終了処理を実行中... ===")
        # ここがポイント！
        # デーモンスレッド（GUIやSTT）が残っていても、OSレベルで強制的にプロセスを殺します
        os._exit(0)

if __name__ == "__main__":
    main()