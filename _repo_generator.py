#!/usr/bin/env python3
"""
Kodi Repository Generator

Generates addons.xml, addons.xml.md5, and addon zip files for GitHub Pages hosting.
Based on drinfernoo/repository.example pattern.

Usage:
    python _repo_generator.py

Output:
    Creates zips/ directory containing:
    - addons.xml (combined addon metadata)
    - addons.xml.md5 (checksum)
    - {addon_id}/{addon_id}-{version}.zip (per addon)
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Optional, List
import xml.etree.ElementTree as ET
import shutil
import sys

# Source directories containing addon folders (relative to script)
SOURCE_DIRS = ["omega"]

# Files and folders to exclude from addon zips
EXCLUDE_PATTERNS = [
    ".git",
    ".gitignore",
    ".github",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
    "Thumbs.db",
    "*.bak",
    "zips",
]


def should_exclude(path: str) -> bool:
    """
    Check if path matches any exclusion pattern.
    
    Args:
        path: Relative path string to check
        
    Returns:
        True if path should be excluded
    """
    path_lower = path.lower()
    
    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith("*"):
            if path_lower.endswith(pattern[1:]):
                return True
        elif pattern.lower() in path_lower.split("/"):
            return True
        elif pattern.lower() in path_lower.split("\\"):
            return True
            
    return False


def parse_addon_xml(addon_dir: Path) -> Optional[ET.Element]:
    """
    Parse addon.xml and return root element.
    
    Args:
        addon_dir: Directory containing addon.xml
        
    Returns:
        ElementTree Element or None if parsing fails
    """
    addon_xml_path = addon_dir / "addon.xml"
    
    if not addon_xml_path.exists():
        return None

    try:
        tree = ET.parse(addon_xml_path)
        return tree.getroot()
    except ET.ParseError as e:
        print(f"  ERROR: Failed to parse {addon_xml_path}: {e}")
        return None


def create_addon_zip(addon_dir: Path, output_dir: Path) -> Optional[Path]:
    """
    Create versioned zip file for addon.
    
    Args:
        addon_dir: Source addon directory
        output_dir: Base output directory for zips
        
    Returns:
        Path to created zip file or None on failure
    """
    addon_xml = parse_addon_xml(addon_dir)
    if addon_xml is None:
        return None

    addon_id = addon_xml.get("id")
    version = addon_xml.get("version")

    if not addon_id or not version:
        print(f"  ERROR: Missing id or version in {addon_dir}/addon.xml")
        return None

    # Create output directory for this addon
    addon_output = output_dir / addon_id
    addon_output.mkdir(parents=True, exist_ok=True)

    zip_name = f"{addon_id}-{version}.zip"
    zip_path = addon_output / zip_name

    print(f"  Creating: {zip_name}")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in addon_dir.rglob("*"):
            if not file_path.is_file():
                continue

            # Archive path includes addon folder name
            rel_path = file_path.relative_to(addon_dir.parent)
            rel_path_str = str(rel_path).replace("\\", "/")

            if should_exclude(rel_path_str):
                continue

            zf.write(file_path, rel_path)

    return zip_path


def generate_addons_xml(source_dir: Path) -> int:
    """
    Generate addons.xml and zip files for all addons in source directory.
    
    Args:
        source_dir: Directory containing addon folders
        
    Returns:
        Number of addons processed
    """
    print(f"\nProcessing: {source_dir.name}/")

    zips_dir = source_dir / "zips"
    
    # Clean existing zips directory
    if zips_dir.exists():
        shutil.rmtree(zips_dir)
    zips_dir.mkdir()

    addons_root = ET.Element("addons")
    addon_count = 0

    # Process each subdirectory
    for item in sorted(source_dir.iterdir()):
        if not item.is_dir():
            continue
        if item.name == "zips":
            continue

        addon_xml = parse_addon_xml(item)
        if addon_xml is None:
            continue

        addon_id = addon_xml.get("id")
        version = addon_xml.get("version")
        
        print(f"  Found: {addon_id} v{version}")

        # Create addon zip
        zip_path = create_addon_zip(item, zips_dir)
        if zip_path is None:
            continue

        # Add to combined addons.xml
        addons_root.append(addon_xml)
        addon_count += 1

    # Write addons.xml
    addons_xml_path = zips_dir / "addons.xml"
    
    # Format XML with declaration
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content = ET.tostring(addons_root, encoding="unicode")
    full_content = xml_declaration + xml_content

    addons_xml_path.write_text(full_content, encoding="utf-8")
    print(f"  Generated: addons.xml ({addon_count} addons)")

    # Generate MD5 checksum
    md5_hash = hashlib.md5(full_content.encode("utf-8")).hexdigest()
    md5_path = zips_dir / "addons.xml.md5"
    md5_path.write_text(md5_hash)
    print(f"  Generated: addons.xml.md5 ({md5_hash})")

    return addon_count


def copy_repo_zip_to_root(script_dir: Path) -> None:
    """
    Copy repository addon zip to root for easy installation.
    
    Args:
        script_dir: Repository root directory
    """
    # Find repository addon zip
    for source_name in SOURCE_DIRS:
        source_dir = script_dir / source_name
        zips_dir = source_dir / "zips"
        
        if not zips_dir.exists():
            continue

        for addon_dir in zips_dir.iterdir():
            if not addon_dir.is_dir():
                continue
            if not addon_dir.name.startswith("repository."):
                continue

            for zip_file in addon_dir.glob("*.zip"):
                dest = script_dir / zip_file.name
                shutil.copy2(zip_file, dest)
                print(f"\nCopied to root: {zip_file.name}")
                
                # Update index.html
                update_index_html(script_dir, zip_file.name)
                return


def update_index_html(script_dir: Path, zip_filename: str) -> None:
    """
    Update index.html with correct zip filename.
    
    Args:
        script_dir: Repository root directory
        zip_filename: Repository zip filename
    """
    index_path = script_dir / "index.html"
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Jodisfields Kodi Repository</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
        }}
        h1 {{ color: #00d4ff; }}
        a {{
            color: #00d4ff;
            text-decoration: none;
            padding: 10px 20px;
            border: 1px solid #00d4ff;
            border-radius: 5px;
            display: inline-block;
            margin: 10px 0;
        }}
        a:hover {{
            background: #00d4ff;
            color: #1a1a2e;
        }}
        .instructions {{
            background: #16213e;
            padding: 20px;
            border-radius: 10px;
            margin-top: 30px;
        }}
        code {{
            background: #0f3460;
            padding: 2px 8px;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <h1>Jodisfields Kodi Repository</h1>
    
    <p>Repository for custom Kodi build with Fentastic, FenLight, and CocoScrapers.</p>
    
    <a href="{zip_filename}">{zip_filename}</a>
    
    <div class="instructions">
        <h2>Installation Instructions</h2>
        <ol>
            <li>Open Kodi and go to <strong>Settings</strong> → <strong>File Manager</strong></li>
            <li>Select <strong>Add Source</strong> and enter:<br>
                <code>https://jodisfields.github.io/kodi-build/</code></li>
            <li>Name it <code>jodisfields</code> and click OK</li>
            <li>Go back to Settings → <strong>Add-ons</strong> → <strong>Install from zip file</strong></li>
            <li>Select <code>jodisfields</code> → <code>{zip_filename}</code></li>
            <li>Wait for "Add-on installed" notification</li>
            <li>Go to <strong>Install from repository</strong> → <strong>Jodisfields Repository</strong></li>
            <li>Select <strong>Program add-ons</strong> → <strong>Jodis Build Wizard</strong> → Install</li>
            <li>Run the wizard from Program add-ons to install the build</li>
        </ol>
    </div>
</body>
</html>
"""
    
    index_path.write_text(html_content)
    print(f"Updated: index.html")


def main() -> int:
    """
    Main entry point.
    
    Returns:
        Exit code (0 = success)
    """
    script_dir = Path(__file__).parent.resolve()

    print("=" * 60)
    print("Kodi Repository Generator")
    print("=" * 60)

    total_addons = 0

    for source_name in SOURCE_DIRS:
        source_dir = script_dir / source_name
        
        if not source_dir.exists():
            print(f"\nWARNING: Source directory not found: {source_name}/")
            continue

        addon_count = generate_addons_xml(source_dir)
        total_addons += addon_count

    # Copy repository zip to root
    copy_repo_zip_to_root(script_dir)

    print("\n" + "=" * 60)
    print(f"Complete! Processed {total_addons} addon(s)")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
