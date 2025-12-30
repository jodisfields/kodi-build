"""
Build wizard configuration.
Centralised settings for build URLs, addon IDs, and service configuration.
"""

# Build identification
BUILD_NAME = "JodisBuild"
BUILD_VERSION = "1.0.0"

# Build download URLs (GitHub Pages hosted)
BUILD_URL = "https://jodisfields.github.io/kodi-build/builds/jodisbuild-latest.zip"
CHECKSUM_URL = "https://jodisfields.github.io/kodi-build/builds/jodisbuild-latest.zip.md5"

# Repository URL for reference
REPO_URL = "https://jodisfields.github.io/kodi-build/"

# External repository for Fentastic/FenLight source
IVARBRANDT_REPO = "https://ivarbrandt.github.io/repository.ivarbrandt/"

# Core addon IDs included in build
FENLIGHT_ID = "plugin.video.fenlight"
FENTASTIC_ID = "skin.fentastic"
COCOSCRAPERS_ID = "script.module.cocoscrapers"
MYACCOUNTS_ID = "script.module.myaccounts"

# Required addons for build validation
REQUIRED_ADDONS = [
    FENTASTIC_ID,
    FENLIGHT_ID,
    COCOSCRAPERS_ID,
]

# Debrid service definitions
# Tuple format: (Display Name, settings key prefix, auth method)
DEBRID_SERVICES = [
    ("Real-Debrid", "rd", "token"),
    ("AllDebrid", "ad", "token"),
    ("Premiumize", "pm", "token"),
    ("Debrid-Link", "dl", "token"),
]

# FenLight external scraper configuration
FENLIGHT_SCRAPER_CONFIG = {
    "provider.external": "true",
    "external_scraper.name": "CocoScrapers",
    "external_scraper.module": COCOSCRAPERS_ID,
}

# Default FenLight playback settings
FENLIGHT_PLAYBACK_CONFIG = {
    "auto_play": "true",
    "autoplay_quality": "1080p",
    "autoplay_hevc": "true",
    "results.sort_method": "quality",
    "results.filter_unknown": "true",
    "cache.enabled": "true",
}

# Default CocoScrapers quality settings
COCOSCRAPERS_QUALITY_CONFIG = {
    "quality.include_4k": "true",
    "quality.include_1080p": "true",
    "quality.include_720p": "true",
    "quality.include_sd": "false",
    "scraper.timeout": "30",
    "results.limit": "100",
}

# Default Fentastic skin settings
FENTASTIC_SKIN_CONFIG = {
    "home.widgets.enabled": "true",
    "home.background.type": "1",
    "home.poster.style": "1",
    "info.extendedinfo": "true",
    "info.ratings.enabled": "true",
}

# Directories to include in build packages
BUILD_INCLUDE_DIRS = [
    "addons",
    "userdata/addon_data",
    "userdata/keymaps",
]

# Patterns to exclude from build packages
BUILD_EXCLUDE_PATTERNS = [
    "*/Thumbnails/*",
    "*/cache/*",
    "*/temp/*",
    "*/.git/*",
    "*.log",
    "*.pyc",
    "*/__pycache__/*",
    "*/Textures*.db",
    "*/Addons*.db",
    "*/crash*.txt",
    "*/.DS_Store",
    "*/Thumbs.db",
]

# Directories to include in backups
BACKUP_DIRS = [
    "addon_data",
    "userdata",
]

# Cache directories for cleanup
CACHE_DIRS = [
    "cache",
    "temp",
    "userdata/Thumbnails",
]
