import argparse
import sys
import os

# Ensure backend root is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from plugins.txt_to_epub import TxtToEpubPlugin
from plugins.epub_tool.plugin import EpubToolPlugin

def main():
    # 1. Initialize Plugins Registry
    plugins = {
        "txt2epub": TxtToEpubPlugin(),
        "epub_tool": EpubToolPlugin()
    }
    
    # 2. Determine which plugin to use
    active_plugin_name = "txt2epub"
    
    # Simple manual check for --plugin arg before full parsing
    if "--plugin" in sys.argv:
        try:
            idx = sys.argv.index("--plugin")
            if idx + 1 < len(sys.argv):
                active_plugin_name = sys.argv[idx + 1]
        except ValueError:
            pass

    active_plugin = plugins.get(active_plugin_name)
    
    if not active_plugin:
        print(f"ERROR: Plugin {active_plugin_name} not found. Available: {list(plugins.keys())}", file=sys.stderr)
        sys.exit(1)
    
    # 3. Setup Argument Parser
    parser = argparse.ArgumentParser(description="TXT to EPUB Converter Backend")
    parser.add_argument("--plugin", default="txt2epub", help="Select plugin to use")
    
    # 4. Register arguments from the active plugin
    active_plugin.register_arguments(parser)
    
    # 5. Parse arguments
    args = parser.parse_args()
    
    # 6. Run Plugin
    active_plugin.run(args)

if __name__ == "__main__":
    main()
