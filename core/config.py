import os
import sys
import json

class ConfigManager:
    def __init__(self):
        # v3.0のパス解決を完全移植
        if getattr(sys, "frozen", False):
            self.base_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            # core/ の親ディレクトリ（プロジェクトルート）を基準とする
            self.base_dir = os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))

        self.config_path = os.path.join(self.base_dir, "config.json")
        self.char_path = os.path.join(self.base_dir, "character.txt")
        self.settings = self._load_json(self.config_path)

    def _load_json(self, path):
        """config.json を読み込み、辞書として返す"""
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Config Load Error ({path}): {e}")
        return {}

    def get_enabled_models(self):
        """config.json の models リストから enabled: true の名前を抽出"""
        models = self.settings.get("models", [])
        # enabled が True のもの、またはフラグがないものを抽出
        enabled_names = [m["name"] for m in models if m.get("enabled", True)]
        
        # もしリストが空なら、単体の model_name キーをフォールバックとして使う
        if not enabled_names and "model_name" in self.settings:
            enabled_names = [self.settings["model_name"]]
        return enabled_names

    def get_character_prompt(self, user_name="あっきー"):
        """character.txt を読み込み、変数を置換して返す"""
        content = "明るい秘書、こもも。"
        if os.path.exists(self.char_path):
            with open(self.char_path, "r", encoding="utf-8") as f:
                content = f.read()
        # {{user}} などのプレースホルダーを置換
        return content.replace("{{user}}", user_name).replace("{{char}}", "こもも")

    def get(self, key, default=None):
        """特定のキー設定を取得"""
        return self.settings.get(key, default)