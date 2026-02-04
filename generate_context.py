import os

# 除外するフォルダ・ファイル
IGNORE_DIRS = {".git", "__pycache__", "venv", ".idea", ".vscode", "songs", "build", "dist"}
IGNORE_FILES = {".DS_Store", "temp_input.wav"}
# 読み込む拡張子
TARGET_EXTS = {".py", ".json", ".txt", ".md"}

OUTPUT_FILE = "full_source_context.txt"

def main():
    base_dir = os.getcwd()
    output_path = os.path.join(base_dir, OUTPUT_FILE)
    
    with open(output_path, "w", encoding="utf-8") as outfile:
        outfile.write(f"Project Context Generated at: {os.getcwd()}\n")
        outfile.write("="*50 + "\n\n")

        for root, dirs, files in os.walk(base_dir):
            # 除外フォルダをスキップ
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in files:
                if file in IGNORE_FILES:
                    continue
                
                _, ext = os.path.splitext(file)
                if ext.lower() not in TARGET_EXTS:
                    continue
                
                # 自分自身（このスクリプトと出力ファイル）は除外
                if file == os.path.basename(__file__) or file == OUTPUT_FILE:
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, base_dir)

                try:
                    with open(file_path, "r", encoding="utf-8") as infile:
                        content = infile.read()
                        
                    # AIが読みやすい形式で書き込み
                    outfile.write(f"\n\n{'='*20} FILE START: {rel_path} {'='*20}\n")
                    outfile.write(content)
                    outfile.write(f"\n{'='*20} FILE END: {rel_path} {'='*20}\n")
                    
                    print(f"Added: {rel_path}")
                except Exception as e:
                    print(f"Skipped (Error): {rel_path} - {e}")

    print(f"\nDone! All code is merged into: {OUTPUT_FILE}")
    print("このファイルをGeminiにアップロードしてください。")

if __name__ == "__main__":
    main()