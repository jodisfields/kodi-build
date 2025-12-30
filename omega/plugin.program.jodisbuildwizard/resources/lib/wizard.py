"""
Core wizard functionality for build installation and management.
Handles download, extraction, backup, restore, and configuration tasks.
"""

from __future__ import annotations

import hashlib
import zipfile
import shutil
import fnmatch
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, List, Dict
from urllib.request import urlretrieve, urlopen
from urllib.error import URLError, HTTPError
import xml.etree.ElementTree as ET
import logging

import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon

from . import config

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None]


class BuildWizard:
    """
    Handles build installation, updates, backups, and configuration.
    All filesystem operations use Kodi's special:// path translation.
    """

    CHUNK_SIZE = 1024 * 1024  # 1MB download chunks

    def __init__(self) -> None:
        self.addon = xbmcaddon.Addon()
        self.addon_name = self.addon.getAddonInfo("name")
        
        # Kodi paths via xbmcvfs translation
        self.kodi_home = Path(xbmcvfs.translatePath("special://home"))
        self.temp_dir = Path(xbmcvfs.translatePath("special://temp"))
        self.profile_dir = Path(xbmcvfs.translatePath("special://profile"))
        self.addon_data = self.kodi_home / "userdata" / "addon_data"

    def fresh_install(self) -> None:
        """
        Perform fresh build installation.
        Downloads build archive, verifies integrity, extracts to Kodi home.
        """
        dialog = xbmcgui.Dialog()

        # Confirmation with backup offer
        choice = dialog.yesnocustom(
            "Fresh Install",
            f"This will install {config.BUILD_NAME} and overwrite your current configuration.\n\n"
            "Do you want to create a backup first?",
            customlabel="Cancel",
            yeslabel="Backup First",
            nolabel="Skip Backup"
        )

        if choice == 2:  # Cancel
            return
        
        if choice == 1:  # Backup first
            self.create_backup()

        progress = xbmcgui.DialogProgress()
        progress.create(f"Installing {config.BUILD_NAME}", "Initializing...")

        try:
            # Download build archive
            progress.update(0, "Downloading build...")
            build_zip = self._download_build(
                lambda p, m: progress.update(int(p * 40), m)
            )

            if not build_zip or progress.iscanceled():
                raise RuntimeError("Download cancelled or failed")

            # Verify checksum
            progress.update(42, "Verifying file integrity...")
            if not self._verify_checksum(build_zip):
                if not dialog.yesno(
                    "Checksum Warning",
                    "Could not verify file integrity.\n"
                    "The download may be corrupted or the checksum file is unavailable.\n\n"
                    "Continue installation anyway?"
                ):
                    raise RuntimeError("Installation cancelled - checksum verification failed")

            # Extract build
            progress.update(45, "Extracting files...")
            self._extract_archive(
                build_zip,
                self.kodi_home,
                progress_callback=lambda p, m: progress.update(45 + int(p * 45), m)
            )

            # Post-install configuration
            progress.update(92, "Configuring Kodi...")
            self._post_install_setup()

            # Cleanup temp file
            progress.update(96, "Cleaning up...")
            if build_zip.exists():
                build_zip.unlink()

            progress.update(100, "Installation complete!")
            progress.close()

            # Prompt restart
            if dialog.yesno(
                "Installation Complete",
                f"{config.BUILD_NAME} has been installed successfully.\n\n"
                "Kodi must restart to apply changes.\n"
                "Restart now?"
            ):
                xbmc.executebuiltin("RestartApp")

        except Exception as e:
            progress.close()
            logger.exception("Fresh install failed")
            dialog.ok("Installation Failed", str(e))

    def update_build(self) -> None:
        """
        Update build add-ons while preserving user settings.
        Only extracts addons directory, keeps addon_data intact.
        """
        dialog = xbmcgui.Dialog()

        if not dialog.yesno(
            "Update Build",
            f"This will update {config.BUILD_NAME} add-ons to the latest version.\n\n"
            "Your settings, debrid configuration, and watch history will be preserved.\n\n"
            "Continue?"
        ):
            return

        progress = xbmcgui.DialogProgress()
        progress.create(f"Updating {config.BUILD_NAME}", "Downloading...")

        try:
            # Download build
            build_zip = self._download_build(
                lambda p, m: progress.update(int(p * 50), m)
            )

            if not build_zip or progress.iscanceled():
                raise RuntimeError("Download failed or cancelled")

            progress.update(52, "Verifying...")
            self._verify_checksum(build_zip)  # Non-fatal for updates

            # Extract only addons directory
            progress.update(55, "Updating add-ons...")
            self._extract_archive(
                build_zip,
                self.kodi_home,
                include_patterns=["addons/*"],
                exclude_patterns=["addon_data/*", "userdata/*"],
                progress_callback=lambda p, m: progress.update(55 + int(p * 40), m)
            )

            # Force addon database refresh
            progress.update(96, "Refreshing addon database...")
            self._refresh_addon_database()

            if build_zip.exists():
                build_zip.unlink()

            progress.close()

            if dialog.yesno(
                "Update Complete",
                "Add-ons have been updated successfully.\n\n"
                "Restart Kodi to apply changes?"
            ):
                xbmc.executebuiltin("RestartApp")

        except Exception as e:
            progress.close()
            logger.exception("Update failed")
            dialog.ok("Update Failed", str(e))

    def configure_debrid(self) -> None:
        """
        Configure debrid service authentication for FenLight and CocoScrapers.
        """
        dialog = xbmcgui.Dialog()

        # Check FenLight is installed
        fenlight_addon = self.kodi_home / "addons" / config.FENLIGHT_ID
        if not fenlight_addon.exists():
            dialog.ok(
                "FenLight Not Found",
                "FenLight is not installed.\n\n"
                "Please run Fresh Install first to install the build."
            )
            return

        # Select debrid service
        service_names = [s[0] for s in config.DEBRID_SERVICES]
        selection = dialog.select("Select Debrid Service", service_names)

        if selection < 0:
            return

        service_name, service_key, auth_type = config.DEBRID_SERVICES[selection]

        # Get API token
        token = dialog.input(
            f"Enter {service_name} API Token",
            type=xbmcgui.INPUT_ALPHANUM
        )

        if not token or not token.strip():
            dialog.ok("Cancelled", "No token provided.")
            return

        token = token.strip()

        # Configure services
        try:
            configured = []

            # Configure FenLight
            if self._configure_addon_debrid(
                config.FENLIGHT_ID,
                service_key,
                token,
                config.FENLIGHT_SCRAPER_CONFIG
            ):
                configured.append("FenLight")

            # Configure CocoScrapers if present
            if self._configure_addon_debrid(
                config.COCOSCRAPERS_ID,
                service_key,
                token
            ):
                configured.append("CocoScrapers")

            # Configure MyAccounts if present
            if self._configure_addon_debrid(
                config.MYACCOUNTS_ID,
                service_key,
                token
            ):
                configured.append("MyAccounts")

            if configured:
                dialog.ok(
                    "Configuration Complete",
                    f"{service_name} has been configured for:\n"
                    f"• {chr(10).join(configured)}\n\n"
                    "You may need to restart Kodi for changes to take effect."
                )
            else:
                dialog.ok(
                    "Configuration Issue",
                    "No add-ons were configured.\n"
                    "Ensure the build is installed correctly."
                )

        except Exception as e:
            logger.exception("Debrid configuration failed")
            dialog.ok("Configuration Failed", str(e))

    def create_backup(self) -> None:
        """
        Create timestamped backup of user configuration.
        Backs up addon_data and userdata directories.
        """
        dialog = xbmcgui.Dialog()
        progress = xbmcgui.DialogProgress()
        progress.create("Creating Backup", "Preparing...")

        backup_dir = self.kodi_home / "backups"
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}.zip"
        backup_path = backup_dir / backup_name

        try:
            # Collect files to backup
            files_to_backup: List[tuple] = []
            
            for dir_name in config.BACKUP_DIRS:
                source_dir = self.kodi_home / dir_name
                if not source_dir.exists():
                    continue

                for file_path in source_dir.rglob("*"):
                    if file_path.is_file() and not self._should_exclude(file_path):
                        rel_path = file_path.relative_to(self.kodi_home)
                        files_to_backup.append((file_path, rel_path))

            if not files_to_backup:
                progress.close()
                dialog.ok("No Data", "No configuration data found to backup.")
                return

            # Create backup archive
            total_files = len(files_to_backup)
            
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, (file_path, arc_path) in enumerate(files_to_backup):
                    if progress.iscanceled():
                        progress.close()
                        if backup_path.exists():
                            backup_path.unlink()
                        return

                    progress.update(
                        int((i / total_files) * 100),
                        f"Backing up: {arc_path.name}"
                    )
                    
                    try:
                        zf.write(file_path, arc_path)
                    except (OSError, PermissionError) as e:
                        logger.warning(f"Could not backup {file_path}: {e}")

            progress.close()

            backup_size = backup_path.stat().st_size / (1024 * 1024)
            dialog.ok(
                "Backup Complete",
                f"Backup saved successfully.\n\n"
                f"File: {backup_name}\n"
                f"Size: {backup_size:.1f} MB\n"
                f"Files: {total_files}"
            )

        except Exception as e:
            progress.close()
            logger.exception("Backup failed")
            if backup_path.exists():
                backup_path.unlink()
            dialog.ok("Backup Failed", str(e))

    def restore_backup(self) -> None:
        """
        Restore configuration from existing backup.
        """
        dialog = xbmcgui.Dialog()
        backup_dir = self.kodi_home / "backups"

        if not backup_dir.exists():
            dialog.ok("No Backups", "Backup directory not found.")
            return

        # List available backups (newest first)
        backups = sorted(backup_dir.glob("backup_*.zip"), reverse=True)

        if not backups:
            dialog.ok("No Backups", "No backup files found.")
            return

        # Format backup names with dates
        backup_labels = []
        for b in backups:
            size_mb = b.stat().st_size / (1024 * 1024)
            # Parse timestamp from filename
            try:
                ts = b.stem.replace("backup_", "")
                dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
                label = f"{dt.strftime('%Y-%m-%d %H:%M')} ({size_mb:.1f} MB)"
            except ValueError:
                label = f"{b.name} ({size_mb:.1f} MB)"
            backup_labels.append(label)

        selection = dialog.select("Select Backup to Restore", backup_labels)

        if selection < 0:
            return

        selected_backup = backups[selection]

        if not dialog.yesno(
            "Confirm Restore",
            f"Restore from:\n{selected_backup.name}\n\n"
            "This will overwrite your current settings.\n"
            "Continue?"
        ):
            return

        progress = xbmcgui.DialogProgress()
        progress.create("Restoring Backup", "Extracting...")

        try:
            self._extract_archive(
                selected_backup,
                self.kodi_home,
                progress_callback=lambda p, m: progress.update(int(p * 100), m)
            )

            progress.close()

            if dialog.yesno(
                "Restore Complete",
                "Configuration has been restored.\n\n"
                "Restart Kodi to apply changes?"
            ):
                xbmc.executebuiltin("RestartApp")

        except Exception as e:
            progress.close()
            logger.exception("Restore failed")
            dialog.ok("Restore Failed", str(e))

    def clear_cache(self) -> None:
        """
        Clear Kodi cache, thumbnails, and texture database.
        """
        dialog = xbmcgui.Dialog()

        if not dialog.yesno(
            "Clear Cache",
            "This will delete:\n"
            "• Thumbnail images\n"
            "• Cached data\n"
            "• Temporary files\n"
            "• Texture database\n\n"
            "Kodi will rebuild thumbnails as needed.\n\n"
            "Continue?"
        ):
            return

        progress = xbmcgui.DialogProgress()
        progress.create("Clearing Cache", "Working...")

        cleared_bytes = 0
        cleared_files = 0

        cache_paths = [self.kodi_home / d for d in config.CACHE_DIRS]

        for i, cache_dir in enumerate(cache_paths):
            if not cache_dir.exists():
                continue

            progress.update(
                int((i / len(cache_paths)) * 80),
                f"Clearing: {cache_dir.name}"
            )

            for item in cache_dir.rglob("*"):
                if item.is_file():
                    try:
                        cleared_bytes += item.stat().st_size
                        item.unlink()
                        cleared_files += 1
                    except (OSError, PermissionError):
                        pass

        # Clear texture databases
        progress.update(85, "Clearing texture database...")
        db_dir = self.kodi_home / "userdata" / "Database"
        
        for db_file in db_dir.glob("Textures*.db"):
            try:
                cleared_bytes += db_file.stat().st_size
                db_file.unlink()
                cleared_files += 1
            except (OSError, PermissionError):
                pass

        progress.close()

        cleared_mb = cleared_bytes / (1024 * 1024)
        dialog.ok(
            "Cache Cleared",
            f"Freed {cleared_mb:.1f} MB\n"
            f"Deleted {cleared_files} files"
        )

    def _download_build(
        self,
        progress_callback: Optional[ProgressCallback] = None
    ) -> Optional[Path]:
        """
        Download build archive from configured URL.
        
        Args:
            progress_callback: Function(progress: 0-1, message: str)
            
        Returns:
            Path to downloaded file or None on failure
        """
        output_path = self.temp_dir / "build_download.zip"

        try:
            # Get file size for progress tracking
            with urlopen(config.BUILD_URL, timeout=30) as response:
                total_size = int(response.headers.get("Content-Length", 0))

            # Download with progress reporting
            downloaded = [0]

            def report_hook(block_num: int, block_size: int, total: int) -> None:
                downloaded[0] = block_num * block_size
                if progress_callback and total > 0:
                    progress = min(downloaded[0] / total, 1.0)
                    size_mb = downloaded[0] / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    progress_callback(
                        progress,
                        f"Downloading: {size_mb:.1f} / {total_mb:.1f} MB"
                    )

            urlretrieve(config.BUILD_URL, output_path, report_hook)

            logger.info(f"Downloaded build to {output_path}")
            return output_path

        except HTTPError as e:
            logger.error(f"HTTP error downloading build: {e.code} {e.reason}")
            return None
        except URLError as e:
            logger.error(f"URL error downloading build: {e.reason}")
            return None
        except OSError as e:
            logger.error(f"OS error downloading build: {e}")
            if output_path.exists():
                output_path.unlink()
            return None

    def _verify_checksum(self, file_path: Path) -> bool:
        """
        Verify MD5 checksum of downloaded file.
        
        Args:
            file_path: Path to file to verify
            
        Returns:
            True if checksum matches, False otherwise
        """
        try:
            with urlopen(config.CHECKSUM_URL, timeout=30) as response:
                checksum_content = response.read().decode().strip()
                # Handle both "hash  filename" and plain hash formats
                expected_md5 = checksum_content.split()[0].lower()

            with open(file_path, "rb") as f:
                actual_md5 = hashlib.md5(f.read()).hexdigest().lower()

            match = expected_md5 == actual_md5
            logger.info(f"Checksum verification: {'passed' if match else 'failed'}")
            return match

        except Exception as e:
            logger.warning(f"Checksum verification error: {e}")
            return False

    def _extract_archive(
        self,
        archive_path: Path,
        destination: Path,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        progress_callback: Optional[ProgressCallback] = None
    ) -> None:
        """
        Extract zip archive with optional filtering.
        
        Args:
            archive_path: Path to zip file
            destination: Extraction destination directory
            include_patterns: Glob patterns to include (None = all)
            exclude_patterns: Glob patterns to exclude
            progress_callback: Function(progress: 0-1, message: str)
        """
        exclude_patterns = exclude_patterns or []

        with zipfile.ZipFile(archive_path, "r") as zf:
            members = zf.namelist()

            # Apply include filter
            if include_patterns:
                members = [
                    m for m in members
                    if any(fnmatch.fnmatch(m, p) for p in include_patterns)
                ]

            # Apply exclude filter
            members = [
                m for m in members
                if not any(fnmatch.fnmatch(m, p) for p in exclude_patterns)
            ]

            total = len(members)

            for i, member in enumerate(members):
                if progress_callback:
                    progress_callback(
                        i / total if total > 0 else 1.0,
                        f"Extracting: {Path(member).name}"
                    )

                target_path = destination / member

                if member.endswith("/"):
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src:
                        target_path.write_bytes(src.read())

            logger.info(f"Extracted {total} files to {destination}")

    def _post_install_setup(self) -> None:
        """
        Run post-installation configuration tasks.
        Sets default skin and refreshes addon database.
        """
        # Set Fentastic as default skin in guisettings.xml
        guisettings = self.kodi_home / "userdata" / "guisettings.xml"

        if guisettings.exists():
            try:
                tree = ET.parse(guisettings)
                root = tree.getroot()

                # Find or create skin setting
                skin_elem = root.find(".//setting[@id='lookandfeel.skin']")
                if skin_elem is not None:
                    skin_elem.text = config.FENTASTIC_ID
                else:
                    setting = ET.SubElement(root, "setting", id="lookandfeel.skin")
                    setting.text = config.FENTASTIC_ID

                tree.write(guisettings, encoding="unicode", xml_declaration=True)
                logger.info("Updated guisettings.xml with Fentastic skin")

            except ET.ParseError as e:
                logger.warning(f"Failed to parse guisettings.xml: {e}")

        # Force addon database refresh
        self._refresh_addon_database()

    def _refresh_addon_database(self) -> None:
        """Delete addon database to force Kodi to rescan add-ons."""
        db_dir = self.kodi_home / "userdata" / "Database"
        
        for db_file in db_dir.glob("Addons*.db"):
            try:
                db_file.unlink()
                logger.info(f"Deleted {db_file.name}")
            except OSError as e:
                logger.warning(f"Could not delete {db_file}: {e}")

    def _configure_addon_debrid(
        self,
        addon_id: str,
        service_key: str,
        token: str,
        extra_settings: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Configure debrid settings for an addon.
        
        Args:
            addon_id: Addon identifier
            service_key: Debrid service key (rd, ad, pm, dl)
            token: API token
            extra_settings: Additional settings to write
            
        Returns:
            True if configuration was written
        """
        settings_dir = self.addon_data / addon_id
        
        # Check addon exists
        if not (self.kodi_home / "addons" / addon_id).exists():
            return False

        settings_dir.mkdir(parents=True, exist_ok=True)
        settings_path = settings_dir / "settings.xml"

        # Build settings dict
        settings = {
            f"{service_key}.enabled": "true",
            f"{service_key}.token": token,
            "debrid.priority": service_key,
        }

        if extra_settings:
            settings.update(extra_settings)

        self._write_settings_xml(settings_path, settings)
        logger.info(f"Configured {addon_id} with {service_key}")
        return True

    def _write_settings_xml(
        self,
        path: Path,
        settings: Dict[str, str],
        merge: bool = True
    ) -> None:
        """
        Write or update Kodi settings XML file.
        
        Args:
            path: Path to settings.xml
            settings: Dictionary of setting_id -> value
            merge: If True, merge with existing settings
        """
        if merge and path.exists():
            try:
                tree = ET.parse(path)
                root = tree.getroot()
            except ET.ParseError:
                root = ET.Element("settings", version="2")
                tree = ET.ElementTree(root)
        else:
            root = ET.Element("settings", version="2")
            tree = ET.ElementTree(root)

        for setting_id, value in settings.items():
            elem = root.find(f".//setting[@id='{setting_id}']")
            if elem is None:
                elem = ET.SubElement(root, "setting", id=setting_id)
            elem.text = value

        path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(path, encoding="unicode", xml_declaration=True)

    def _should_exclude(self, path: Path) -> bool:
        """
        Check if path should be excluded from backup.
        
        Args:
            path: Path to check
            
        Returns:
            True if path matches exclusion patterns
        """
        path_str = str(path)
        
        for pattern in config.BUILD_EXCLUDE_PATTERNS:
            if fnmatch.fnmatch(path_str, pattern):
                return True
                
        return False
