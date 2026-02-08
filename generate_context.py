
"""
Komomo System Tool - Project Context Generator
Version: v4.2.0

[役割]
プロジェクト内のソースコードを1つのテキストファイルに統合し、
AI(Gemini等)に最新のコンテキストを伝えるためのファイルを生成します。

[主な機能]
- 指定された拡張子(.py, .json等)の全ファイルをスキャン
- 除外設定(venv, .git等)を適用し、不必要なデータの混入を防止
- 日時付きの統合ファイル(full_source_*)および、全ファイルリスト(file-list-*)を出力
"""

import os
from datetime import datetime

# --- 設定：今後のバージョン変更やプロジェクト名に対応 ---
VERSION = "4"  # komomo_system_v◯ の ◯ 部分を指定
PROJECT_NAME = f"komomo_system_v{VERSION}"

# 【full_source（AIコンテキスト）出力時にのみ】除外するフォルダ・ファイル
IGNORE_DIRS = {".git", "__pycache__", "venv", ".idea", ".vscode", "songs", "build", "dist"}
IGNORE_FILES = {".DS_Store", "temp_input.wav"}
# 読み込む拡張子（AIコンテキスト用）
TARGET_EXTS = {".py", ".json", ".txt", ".md"}

def main():
    # スクリプトの実行場所を起点とする
    base_dir = os.getcwd()
    
    # タイムスタンプ生成 (Windows対応: コロンをハイフンに置換)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    
    # 出力ファイル名の定義
    source_filename = f"full_source_{timestamp}.txt"
    list_filename = f"file-list-{timestamp}.txt"
    
    source_path = os.path.join(base_dir, source_filename)
    list_path = os.path.join(base_dir, list_filename)
    
    full_file_list = [] # 全ファイル一覧用（フィルタなし）
    added_to_source_count = 0 # ソースに統合したファイル数

    print(f"Target Project: {PROJECT_NAME}")
    print(f"Scanning Root : {base_dir}")
    print("-" * 40)

    try:
        # 1. ソースコード統合ファイルの作成開始
        with open(source_path, "w", encoding="utf-8") as outfile:
            outfile.write(f"Project Context: {PROJECT_NAME}\n")
            outfile.write(f"Generated at: {base_dir}\n")
            outfile.write(f"Timestamp: {timestamp}\n")
            outfile.write("="*50 + "\n\n")

            # 全ディレクトリをスキャン
            for root, dirs, files in os.walk(base_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, base_dir)
                    
                    # --- A. ファイル一覧用：一切の除外をせず、全ファイルを追加 ---
                    # 過去の full_source_ や file-list- もすべてリストに載ります
                    full_file_list.append(rel_path)

                    # --- B. AIコンテキスト(full_source)用：フィルタを適用 ---
                    # 除外フォルダ内のファイルはスキップ
                    path_parts = set(rel_path.split(os.sep))
                    if any(d in path_parts for d in IGNORE_DIRS):
                        continue
                    
                    if file in IGNORE_FILES:
                        continue
                    
                    # 拡張子チェック
                    _, ext = os.path.splitext(file)
                    if ext.lower() not in TARGET_EXTS:
                        continue
                    
                    # 無限ループ防止：今作っているファイルとスクリプト自身は中身を書き込まない
                    if file == os.path.basename(__file__) or file == source_filename:
                        continue
                    
                    # 過去のログファイルもAIが混乱するため、中身の統合はスキップ
                    if file.startswith("full_source_") or file.startswith("file-list-"):
                        continue

                    try:
                        with open(file_path, "r", encoding="utf-8") as infile:
                            content = infile.read()
                            
                        # 統合ファイルへの書き込み
                        outfile.write(f"\n\n{'='*20} FILE START: {rel_path} {'='*20}\n")
                        outfile.write(content)
                        outfile.write(f"\n{'='*20} FILE END: {rel_path} {'='*20}\n")
                        added_to_source_count += 1
                    except:
                        # バイナリ等の読み込みエラーはコンテキスト用のみ無視
                        pass

        # 2. ファイル一覧（インデックス）の作成
        # こちらには一切のフィルタをかけず、sortedで出力
        with open(list_path, "w", encoding="utf-8") as listfile:
            listfile.write(f"COMPLETE FILE LIST (Unfiltered) for {PROJECT_NAME}\n")
            listfile.write(f"Total Files Found: {len(full_file_list)}\n")
            listfile.write(f"Generated at: {timestamp}\n")
            listfile.write("※この一覧には.gitやキャッシュ等、すべてのファイルが含まれています。\n")
            listfile.write("-" * 50 + "\n")
            
            for item in sorted(full_file_list):
                listfile.write(f"{item}\n")

        print("-" * 40)
        print(f"1. AI Context Merged : {source_filename} ({added_to_source_count} files)")
        print(f"2. Complete Index   : {list_filename} ({len(full_file_list)} files)")
        print("-" * 40)
        print("成功！ 一覧ファイルを確認して、不要なファイルの掃除に役立ててください。")

    except Exception as e:
        print(f"\n[Fatal Error] {e}")

if __name__ == "__main__":
    main()