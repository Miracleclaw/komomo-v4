import pluggy
import importlib
import pkgutil
import plugins  # pluginsパッケージを参照
from . import specs
from .config import ConfigManager

def get_plugin_manager():
    """
    プラグインシステムの初期化、設定の読み込み、および自動ロードを行う司令塔。
    """
    # 1. Pluggyのマネージャー初期化
    # "komomo" プロジェクト名で管理
    pm = pluggy.PluginManager("komomo")
    pm.add_hookspecs(specs.KomomoSpecs)
    
    # 2. 設定マネージャーの初期化 (core/config.py)
    # これにより全プラグインが共通の設定値にアクセスできる
    config = ConfigManager()
    
    # 3. plugins フォルダ内のモジュールを自動探索して登録
    print("--- Loading Plugins ---")
    
    # pkgutilを使って plugins ディレクトリ配下の全ファイルをリストアップ
    for loader, name, ispkg in pkgutil.iter_modules(plugins.__path__):
        # plugins.xxx としてモジュールを動的にインポート
        module = importlib.import_module(f"plugins.{name}")
        
        # モジュール内に 'Plugin' クラスが定義されているかチェック
        if hasattr(module, "Plugin"):
            # プラグインのインスタンス化時に config を渡す（依存性の注入）
            plugin_instance = module.Plugin(config)
            
            # Pluggyに登録
            pm.register(plugin_instance)
            
            # --- 重要：プラグイン起動後の初期化処理 ---
            # STTプラグインなどの「常に動く」機能のために、
            # ロード直後に on_plugin_loaded メソッドがあれば呼び出す
            if hasattr(plugin_instance, "on_plugin_loaded"):
                # 自分（pm）を渡すことで、プラグイン側からもフックを呼べるようにする
                plugin_instance.on_plugin_loaded(pm)
            
            print(f"Successfully loaded: {name}")
        else:
            print(f"Warning: 'Plugin' class not found in {name}")
            
    print("-----------------------\n")
    return pm