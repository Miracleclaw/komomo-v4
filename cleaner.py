"""
Komomo System Tool - Garbage Cleaner
Version: v1.0.0

[役割]
開発中に発生した不要な一時ファイルやキャッシュ、
古い生成ログ(full_source等)を一括スキャンして削除します。

[主な機能]
- __pycache__ や .DS_Store などのキャッシュフォルダの特定
- 過去の full_source_ および file-list- ファイルの抽出
- 削除前の確認プロセス(y/n)による安全なクリーンアップ
"""
import os
import shutil

# --- 掃除対象の定義 ---
# 1. 完全に不要な特定ファイル名
TARGET_FILES = {
    ".DS_Store", 
    "temp_input.wav", 
    "full_source_context.txt" # 古い固定名のファイル
}

# 2. パターンで指定する不要ファイル（過去のログなど）
TARGET_PATTERNS = [
    "full_source_", 
    "file-list-"
]

# 3. 削除しても動作に支障がないキャッシュディレクトリ
TARGET_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache"
}

def main():
    base_dir = os.getcwd()
    to_delete_files = []
    to_delete_dirs = []

    print("=== Komomo Project Garbage Cleaner ===")
    print(f"Scanning in: {base_dir}\n")

    for root, dirs, files in os.walk(base_dir):
        # ディレクトリのチェック
        for d in dirs:
            if d in TARGET_DIRS:
                path = os.path.join(root, d)
                to_delete_dirs.append(path)

        # ファイルのチェック
        for f in files:
            path = os.path.join(root, f)
            
            # 自分のスクリプト自身は絶対に消さない
            if f == os.path.basename(__file__):
                continue

            # A. 特定ファイル名に一致
            if f in TARGET_FILES:
                to_delete_files.append(path)
                continue

            # B. 過去の生成ログパターンに一致（最新のものは残したい場合は手動除外が必要）
            if any(f.startswith(p) for p in TARGET_PATTERNS):
                # 実行中のリストファイルなどは除外したければここで判定
                to_delete_files.append(path)

    # リストの表示
    total_items = len(to_delete_files) + len(to_delete_dirs)
    if total_items == 0:
        print("掃除が必要なゴミは見つかりませんでした！✨")
        return

    print(f"以下の {total_items} 件のアイテムを削除候補として抽出しました:")
    print("-" * 60)
    for d in to_delete_dirs:
        print(f"[DIR]  {os.path.relpath(d, base_dir)}")
    for f in to_delete_files:
        print(f"[FILE] {os.path.relpath(f, base_dir)}")
    print("-" * 60)

    # 最終確認
    confirm = input(f"\nこれらのファイルを実際に削除しますか？ (y/n): ")
    
    if confirm.lower() == 'y':
        print("\n削除を実行中...")
        # ディレクトリ削除
        for d in to_delete_dirs:
            try:
                shutil.rmtree(d)
                print(f"Deleted DIR : {os.path.relpath(d, base_dir)}")
            except Exception as e:
                print(f"Error (DIR) : {d} - {e}")

        # ファイル削除
        for f in to_delete_files:
            try:
                os.remove(f)
                print(f"Deleted FILE: {os.path.relpath(f, base_dir)}")
            except Exception as e:
                print(f"Error (FILE): {f} - {e}")
        
        print("\n掃除が完了しました！すっきりしましたね ♡")
    else:
        print("\n削除をキャンセルしました。")

if __name__ == "__main__":
    main()