"""
Jodis Build Wizard - Main entry point.
Kodi 21.3 Omega compatible build installation wizard.
"""

import sys
import os

# Add resources/lib to path for module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'lib'))

from resources.lib import router


if __name__ == '__main__':
    router.run()
