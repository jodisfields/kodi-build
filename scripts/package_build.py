#!/usr/bin/env python3
"""
Kodi Build Packager

Packages a configured Kodi installation into a distributable build zip
with Fentastic, FenLight, and CocoScrapers preconfigured.

Usage:
    python package_build.py <kodi_home> <output_dir> [--name NAME] [--version VERSION]

Example:
    python package_build.py ~/.kodi ./builds --name jodisbuild --version 1.0.0
    
    # For Fire TV (after adb pull):
    python package_build.py ./kodi-source ./builds --name jodisbuild --version 1.0.0
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import xml.etree.ElementTree as ET
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Required addons for build validation
REQUIRED_ADDONS = [
    "skin.fentastic",
    "plugin.video.fenlight",
    "script.module.cocoscrapers",
]

# Directories to include in build
BUILD_DIRS = [
    "addons",
    "userdata/addon_data",
    "userdata/keymaps",
]

# Patterns to exclude from build
EXCLUDE_PATTERNS = [
    "*/Thumbnails/*",
    "*/cache/*",
    "*/temp/*",
    "*/.git/*",
    "*/.github/*",
    "*.log",
    "*.pyc",
    "*.pyo",
    "*/__pycache__/*",
    "*/Textures*.db",
    "*/Addons*.db",
    "*/MyVideos*.db",
    "*/MyMusic*.db",
    "*/Epg*.db",
    "*/TV*.db",
    "*/crash*.txt",
    "*/.DS_Store",
    "*/Thumbs.db",
    "*/peripheral_data/*",
]


def should_exclude(path: str) -> bool:
    """Check if path matches any exclusion pattern."""
    for pattern in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def validate_kodi_home(kodi_home: Path) -> bool:
    """
    Validate that path is a Kodi home directory.
    
    Args:
        kodi_home: Path to validate
        
    Returns:
        True if valid Kodi home
    """
    required_dirs = ["addons", "userdata"]
    
    for dir_name in required_dirs:
        if not (kodi_home / dir_name).exists():
            logger.error(f"Missing required directory: {dir_name}")
            return False
            
    return True


def check_required_addons(kodi_home: Path) -> List[str]:
    """
    Check for required addons and return list of missing ones.
    
    Args:
        kodi_home: Kodi home directory
        
    Returns:
        List of missing addon IDs
    """
    addons_dir = kodi_home / "addons"
    missing = []
    
    for addon_id in REQUIRED_ADDONS:
        addon_path = addons_dir / addon_id
        if not addon_path.exists():
            missing.append(addon_id)
            
    return missing


def generate_guisettings(output_path: Path) -> None:
    """
    Generate guisettings.xml with Fentastic as default skin.
    
    Args:
        output_path: Path to write guisettings.xml
    """
    root = ET.Element("settings", version="2")

    settings = {
        "lookandfeel.skin": "skin.fentastic",
        "lookandfeel.skinzoom": "0",
        "locale.language": "resource.language.en_gb",
        "filelists.showparentdiritems": "true",
        "filelists.showextensions": "true",
        "videoplayer.adjustrefreshrate": "2",
        "videoplayer.usedisplayasclock": "true",
    }

    for setting_id, value in settings.items():
        ET.SubElement(root, "setting", id=setting_id).text = value

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_path, encoding="unicode", xml_declaration=True)
    logger.info(f"Generated: guisettings.xml")


def generate_addon_settings(addon_data_dir: Path) -> None:
    """
    Generate preconfigured addon settings for FenLight, CocoScrapers, Fentastic.
    
    Args:
        addon_data_dir: Path to userdata/addon_data
    """
    
    # FenLight settings
    fenlight_dir = addon_data_dir / "plugin.video.fenlight"
    fenlight_dir.mkdir(parents=True, exist_ok=True)
    
    fenlight_settings = {
        "provider.external": "true",
        "external_scraper.name": "CocoScrapers",
        "external_scraper.module": "script.module.cocoscrapers",
        "auto_play": "true",
        "autoplay_quality": "1080p",
        "autoplay_hevc": "true",
        "results.sort_method": "quality",
        "results.filter_unknown": "true",
        "cache.enabled": "true",
        "cache.duration": "4",
    }
    
    write_settings_xml(fenlight_dir / "settings.xml", fenlight_settings)
    logger.info("Generated: FenLight settings")

    # CocoScrapers settings
    coco_dir = addon_data_dir / "script.module.cocoscrapers"
    coco_dir.mkdir(parents=True, exist_ok=True)
    
    coco_settings = {
        "quality.include_4k": "true",
        "quality.include_1080p": "true",
        "quality.include_720p": "true",
        "quality.include_sd": "false",
        "scraper.timeout": "30",
        "results.limit": "100",
    }
    
    write_settings_xml(coco_dir / "settings.xml", coco_settings)
    logger.info("Generated: CocoScrapers settings")

    # Fentastic skin settings
    skin_dir = addon_data_dir / "skin.fentastic"
    skin_dir.mkdir(parents=True, exist_ok=True)
    
    skin_settings = {
        "home.widgets.enabled": "true",
        "home.background.type": "1",
        "home.poster.style": "1",
        "info.extendedinfo": "true",
        "info.ratings.enabled": "true",
    }
    
    write_settings_xml(skin_dir / "settings.xml", skin_settings)
    logger.info("Generated: Fentastic settings")


def write_settings_xml(path: Path, settings: Dict[str, str]) -> None:
    """Write Kodi settings XML file."""
    root = ET.Element("settings", version="2")

    for setting_id, value in settings.items():
        ET.SubElement(root, "setting", id=setting_id).text = value

    tree = ET.ElementTree(root)
    tree.write(path, encoding="unicode", xml_declaration=True)


def package_build(
    kodi_home: Path,
    output_dir: Path,
    build_name: str,
    version: str
) -> Path:
    """
    Create build package from Kodi home directory.
    
    Args:
        kodi_home: Source Kodi home directory
        output_dir: Output directory for build zip
        build_name: Build name for zip filename
        version: Build version string
        
    Returns:
        Path to created build zip
    """
    timestamp = datetime.now().strftime("%Y%m%d")
    zip_name = f"{build_name}-{version}-{timestamp}.zip"
    zip_path = output_dir / zip_name

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Packaging build from: {kodi_home}")
    logger.info(f"Output: {zip_path}")

    # Validate required addons
    missing = check_required_addons(kodi_home)
    if missing:
        logger.warning(f"Missing addons: {', '.join(missing)}")
        logger.warning("Build may be incomplete - install missing addons first")

    # Generate default settings if not present
    guisettings = kodi_home / "userdata" / "guisettings.xml"
    if not guisettings.exists():
        generate_guisettings(guisettings)

    addon_data = kodi_home / "userdata" / "addon_data"
    generate_addon_settings(addon_data)

    # Collect files for archive
    files_to_add: List[tuple] = []
    
    for dir_pattern in BUILD_DIRS:
        source_dir = kodi_home / dir_pattern

        if not source_dir.exists():
            logger.warning(f"Directory not found: {dir_pattern}")
            continue

        for file_path in source_dir.rglob("*"):
            if not file_path.is_file():
                continue

            rel_path = file_path.relative_to(kodi_home)
            rel_path_str = str(rel_path).replace("\\", "/")

            if should_exclude(rel_path_str):
                continue

            files_to_add.append((file_path, rel_path))

    # Also include guisettings.xml
    if guisettings.exists():
        rel_path = guisettings.relative_to(kodi_home)
        files_to_add.append((guisettings, rel_path))

    logger.info(f"Packaging {len(files_to_add)} files...")

    # Create zip archive
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path, arc_path in files_to_add:
            try:
                zf.write(file_path, arc_path)
            except (OSError, PermissionError) as e:
                logger.warning(f"Could not add {file_path}: {e}")

    zip_size = zip_path.stat().st_size / (1024 * 1024)
    logger.info(f"Created: {zip_path.name} ({zip_size:.1f} MB)")

    # Generate MD5 checksum
    with open(zip_path, "rb") as f:
        md5_hash = hashlib.md5(f.read()).hexdigest()

    checksum_path = zip_path.with_suffix(".zip.md5")
    checksum_path.write_text(f"{md5_hash}  {zip_path.name}\n")
    logger.info(f"Checksum: {md5_hash}")

    # Create "latest" copy
    latest_zip = output_dir / f"{build_name}-latest.zip"
    latest_md5 = output_dir / f"{build_name}-latest.zip.md5"

    if latest_zip.exists():
        latest_zip.unlink()
    if latest_md5.exists():
        latest_md5.unlink()

    shutil.copy2(zip_path, latest_zip)
    shutil.copy2(checksum_path, latest_md5)

    logger.info(f"Created: {latest_zip.name}")

    return zip_path


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Package Kodi build with Fentastic, FenLight, and CocoScrapers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Package from local Kodi installation
    python package_build.py ~/.kodi ./builds

    # Package from Fire TV pull (after: adb pull /sdcard/Android/data/org.xbmc.kodi/files/.kodi ./kodi-source)
    python package_build.py ./kodi-source ./builds --name jodisbuild --version 1.0.0
        """
    )
    
    parser.add_argument(
        "kodi_home",
        type=Path,
        help="Path to configured Kodi home directory"
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Output directory for build zip"
    )
    parser.add_argument(
        "--name",
        default="jodisbuild",
        help="Build name (default: jodisbuild)"
    )
    parser.add_argument(
        "--version",
        default="1.0.0",
        help="Build version (default: 1.0.0)"
    )

    args = parser.parse_args()

    # Validate source directory
    if not args.kodi_home.exists():
        logger.error(f"Kodi home directory not found: {args.kodi_home}")
        return 1

    if not validate_kodi_home(args.kodi_home):
        logger.error("Invalid Kodi home directory structure")
        return 1

    try:
        package_build(
            args.kodi_home,
            args.output_dir,
            args.name,
            args.version
        )
        return 0
        
    except Exception as e:
        logger.exception(f"Build packaging failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
