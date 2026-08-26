# Privacy Policy

**Effective date:** August 26, 2026
**Application:** File Manager ("the Application")

## 1. Summary

File Manager is a local desktop application. **It does not collect, transmit, sell, or share any personal data.** There are no accounts, no telemetry, no analytics, no advertising, and no network communication of user data.

## 2. Data Stored on Your Device

The Application stores a small settings file **locally only**, at:

| Platform | Location |
|---|---|
| Linux | `~/.config/file-manager/settings.json` (or `$XDG_CONFIG_HOME`) |
| macOS | `~/Library/Application Support/file-manager/settings.json` |
| Windows | `%APPDATA%\file-manager\settings.json` |

This file contains:

- **Window geometry** — size/position so the window can be restored.
- **Preferences** — show-hidden-files toggle, folder-sizes toggle, sort order.
- **Last visited folder** — reopened on startup.
- **Recent folders** — up to 8 recently visited directory paths, shown in the sidebar.

This data never leaves your device. You may delete the settings file at any time; the Application will recreate it with defaults.

## 3. Filesystem Access

The Application reads, writes, moves, renames, compresses, and deletes files **only within the folders you explicitly navigate to and act upon**. It performs no background scanning except when you invoke the Temp File Cleaner, which scans only the folder you specify.

Deletion uses your operating system's trash when available (`send2trash`); otherwise deletion is permanent after explicit confirmation.

## 4. Network Access

The Application makes **no network connections**. The only subprocesses it launches are desktop-environment helpers you explicitly trigger (e.g., `xdg-open` to open a file with its default application).

## 5. Third Parties

No third parties receive any data from the Application. Third-party libraries bundled as dependencies (`ttkbootstrap`, `send2trash`) run locally and do not transmit data.

## 6. Children's Privacy

The Application does not knowingly collect any information from anyone, including children under 13, because it collects no information at all.

## 7. Changes to This Policy

Changes will be published in the source repository with an updated effective date.

## 8. Contact

Privacy questions may be raised via the issue tracker of the project's source repository.
