# Jodisfields Kodi Repository

Custom Kodi 21.3 Omega repository with build wizard for installing preconfigured builds featuring Fentastic skin, FenLight, and CocoScrapers.

## Repository URL

```
https://jodisfields.github.io/kodi-build/
```

## Installation

### Add Repository to Kodi

1. Open Kodi → **Settings** → **File Manager**
2. Select **Add Source**
3. Enter URL: `https://jodisfields.github.io/kodi-build/`
4. Name it `jodisfields` → **OK**
5. Go to **Settings** → **Add-ons** → **Install from zip file**
6. Select `jodisfields` → `repository.jodisfields-1.0.0.zip`
7. Wait for "Add-on installed" notification

### Install Build Wizard

1. **Install from repository** → **Jodisfields Repository**
2. **Program add-ons** → **Jodis Build Wizard** → **Install**
3. Run wizard from **Add-ons** → **Program add-ons**

### Fire TV Installation

```bash
# Connect to Fire TV
adb connect <FIRE_TV_IP>:5555

# Push repository zip
adb push repository.jodisfields-1.0.0.zip /sdcard/Download/

# Then install via Kodi: Add-ons → Install from zip → /storage/emulated/0/Download/
```

## Build Features

- **Fentastic Skin**: Modern UI based on Estuary with enhanced widgets
- **FenLight**: Video addon for streaming content
- **CocoScrapers**: External scraper module for FenLight
- **Debrid Support**: Real-Debrid, AllDebrid, Premiumize, Debrid-Link

## Wizard Functions

| Function | Description |
|----------|-------------|
| Fresh Install | Download and install complete build |
| Update Build | Update addons while preserving settings |
| Configure Debrid | Set up debrid service authentication |
| Backup | Create timestamped configuration backup |
| Restore | Restore from previous backup |
| Clear Cache | Clear thumbnails and temp files |

## Repository Structure

```
kodi-build/
├── _repo_generator.py          # Generates zips and addons.xml
├── index.html                   # GitHub Pages landing page
├── repository.jodisfields-X.X.X.zip
├── omega/                       # Kodi 21 Omega addons
│   ├── repository.jodisfields/
│   ├── plugin.program.jodisbuildwizard/
│   └── zips/                    # Generated output
└── builds/                      # Build archives
    ├── jodisbuild-latest.zip
    └── jodisbuild-latest.zip.md5
```

## Development

### Generate Repository

```bash
python _repo_generator.py
```

### Package Build

```bash
# From configured Kodi installation
python scripts/package_build.py ~/.kodi ./builds --name jodisbuild --version 1.0.0

# From Fire TV (after adb pull)
python scripts/package_build.py ./kodi-source ./builds
```

### Deploy

```bash
git add .
git commit -m "Update repository"
git push origin main
```

GitHub Pages will automatically deploy from the main branch.

## Requirements

- Kodi 21.3 Omega
- Python 3.11+ (for build scripts)
- Git

## License

GPL-3.0
