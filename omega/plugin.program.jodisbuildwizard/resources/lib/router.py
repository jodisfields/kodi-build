"""
URL router for wizard plugin.
Handles Kodi plugin:// URL parsing and action dispatch.
"""

from __future__ import annotations

import sys
from urllib.parse import parse_qsl, urlencode
from typing import Dict, Callable, Optional

import xbmcgui
import xbmcplugin
import xbmcaddon

from . import wizard
from . import config

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_NAME = ADDON.getAddonInfo("name")
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1


def build_url(action: str, **params) -> str:
    """
    Build plugin URL for action routing.
    
    Args:
        action: Action identifier
        **params: Additional URL parameters
        
    Returns:
        Formatted plugin:// URL
    """
    query = urlencode({"action": action, **params})
    return f"plugin://{ADDON_ID}/?{query}"


def get_params() -> Dict[str, str]:
    """
    Parse URL parameters from sys.argv.
    
    Returns:
        Dictionary of parameter key-value pairs
    """
    if len(sys.argv) < 3:
        return {}
    return dict(parse_qsl(sys.argv[2].lstrip("?")))


def add_menu_item(
    label: str,
    action: str,
    description: str = "",
    icon: Optional[str] = None,
    **params
) -> None:
    """
    Add item to plugin directory listing.
    
    Args:
        label: Display label
        action: Action identifier for routing
        description: Item description (shown in info panel)
        icon: Optional icon path
        **params: Additional URL parameters
    """
    li = xbmcgui.ListItem(label)
    
    info_tag = li.getVideoInfoTag()
    info_tag.setPlot(description)
    
    if icon:
        li.setArt({"icon": icon, "thumb": icon})
    
    url = build_url(action, **params)
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=url,
        listitem=li,
        isFolder=False
    )


def main_menu() -> None:
    """Display main wizard menu."""
    menu_items = [
        (
            "[B]Fresh Install[/B]",
            "fresh_install",
            f"Install complete {config.BUILD_NAME} build. This will overwrite your current Kodi configuration with Fentastic skin, FenLight, and CocoScrapers preconfigured."
        ),
        (
            "[B]Update Build[/B]",
            "update_build",
            "Update add-ons to latest versions while preserving your settings, debrid configuration, and watched history."
        ),
        (
            "Configure Debrid Services",
            "configure_debrid",
            "Set up Real-Debrid, AllDebrid, Premiumize, or Debrid-Link authentication for premium streaming links."
        ),
        (
            "Backup Current Setup",
            "backup",
            "Create a timestamped backup of your current add-on settings and configuration. Backups are stored locally."
        ),
        (
            "Restore Backup",
            "restore",
            "Restore Kodi configuration from a previous backup."
        ),
        (
            "Clear Cache",
            "clear_cache",
            "Clear thumbnails, temporary files, and texture database to free up space and resolve image issues."
        ),
        (
            "Build Information",
            "build_info",
            f"View information about {config.BUILD_NAME} and installed components."
        ),
    ]

    for label, action, description in menu_items:
        add_menu_item(label, action, description)

    xbmcplugin.setContent(HANDLE, "files")
    xbmcplugin.endOfDirectory(HANDLE)


def show_build_info() -> None:
    """Display build information dialog."""
    dialog = xbmcgui.Dialog()
    
    info_lines = [
        f"[B]{config.BUILD_NAME}[/B] v{config.BUILD_VERSION}",
        "",
        "[B]Included Add-ons:[/B]",
        f"• Skin: {config.FENTASTIC_ID}",
        f"• Video: {config.FENLIGHT_ID}",
        f"• Scrapers: {config.COCOSCRAPERS_ID}",
        "",
        "[B]Repository:[/B]",
        config.REPO_URL,
        "",
        "Created by jodisfields",
    ]
    
    dialog.textviewer("Build Information", "\n".join(info_lines))


def run() -> None:
    """
    Main router entry point.
    Parse URL parameters and dispatch to appropriate handler.
    """
    params = get_params()
    action = params.get("action", "")

    # Initialise wizard instance
    wiz = wizard.BuildWizard()

    # Action dispatch table
    actions: Dict[str, Callable[[], None]] = {
        "": main_menu,
        "fresh_install": wiz.fresh_install,
        "update_build": wiz.update_build,
        "configure_debrid": wiz.configure_debrid,
        "backup": wiz.create_backup,
        "restore": wiz.restore_backup,
        "clear_cache": wiz.clear_cache,
        "build_info": show_build_info,
    }

    handler = actions.get(action, main_menu)
    handler()
