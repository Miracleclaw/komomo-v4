import pluggy
import re

hookimpl = pluggy.HookimplMarker("komomo")

class Plugin:
    # config を受け取るように変更（使わなくても引数には入れておく）
    def __init__(self, config):
        self.config = config

    @hookimpl
    def on_user_input(self, text: str):
        return f"【AutoLoad】{text} を受信しました"