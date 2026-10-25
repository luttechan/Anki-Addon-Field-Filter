from __future__ import annotations

from typing import Any, Optional

from aqt import gui_hooks, mw
from aqt.qt import (
    QAction, QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
    QLabel, QMenu, QSpinBox, QTimer, QVBoxLayout, QWidget, qconnect,
)
from aqt.utils import showInfo

ADDON_NAME = "Periodic Auto Sync"
DEFAULT_CONFIG = {
    "enabled": True,
    "interval_minutes": 10,
    "sync_on_start": False,
}

_timer: Optional[QTimer] = None
_sync_in_progress = False
_paused = False

_menu: Optional[QMenu] = None
_sync_now_action: Optional[QAction] = None
_pause_action: Optional[QAction] = None
_settings_action: Optional[QAction] = None


def get_config() -> dict[str, Any]:
    stored = mw.addonManager.getConfig(__name__) or {}
    cfg = DEFAULT_CONFIG.copy()
    cfg.update(stored)
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    mw.addonManager.writeConfig(__name__, cfg)


def get_interval_minutes() -> int:
    try:
        value = int(get_config().get("interval_minutes", 10))
    except (TypeError, ValueError):
        value = 10
    return max(1, min(value, 1440))


def ensure_timer() -> QTimer:
    global _timer
    if _timer is None:
        _timer = QTimer(mw)
        _timer.setSingleShot(False)
        qconnect(_timer.timeout, auto_sync)
    return _timer


def stop_timer() -> None:
    if _timer is not None:
        _timer.stop()


def start_timer() -> None:
    cfg = get_config()

    if (
        mw.col is None
        or not cfg.get("enabled", True)
        or _paused
        or _sync_in_progress
    ):
        stop_timer()
        update_menu_state()
        return

    timer = ensure_timer()
    timer.setInterval(get_interval_minutes() * 60 * 1000)
    timer.start()
    update_menu_state()


def restart_timer() -> None:
    stop_timer()
    start_timer()


def automatic_sync_allowed() -> bool:
    cfg = get_config()

    if mw.col is None:
        return False
    if not cfg.get("enabled", True):
        return False
    if _paused or _sync_in_progress:
        return False

    try:
        if mw.media_syncer.is_syncing():
            return False
    except Exception:
        pass

    try:
        if not mw.pm.sync_auth():
            return False
    except Exception:
        return False

    return True


def auto_sync() -> None:
    if not automatic_sync_allowed():
        return

    handler = getattr(mw, "on_sync_button_clicked", None)
    if callable(handler):
        handler()


def sync_now() -> None:
    if mw.col is None:
        showInfo("Open an Anki profile before syncing.")
        return

    if _sync_in_progress:
        showInfo("A sync is already in progress.")
        return

    handler = getattr(mw, "on_sync_button_clicked", None)
    if not callable(handler):
        showInfo("This version of Anki does not expose the expected sync action.")
        return

    handler()


def on_sync_will_start() -> None:
    global _sync_in_progress
    _sync_in_progress = True
    stop_timer()
    update_menu_state()


def on_sync_did_finish() -> None:
    global _sync_in_progress
    _sync_in_progress = False
    start_timer()


def set_paused(value: bool) -> None:
    global _paused
    _paused = value

    if _paused:
        stop_timer()
    else:
        start_timer()

    update_menu_state()


class AutoSyncSettingsDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Periodic Auto Sync Settings")
        self.setMinimumWidth(400)

        cfg = get_config()

        root = QVBoxLayout(self)

        description = QLabel(
            "Automatically synchronize Anki with AnkiWeb at a configurable "
            "interval while a profile is open."
        )
        description.setWordWrap(True)
        root.addWidget(description)

        form = QFormLayout()

        self.enabled = QCheckBox("Enable periodic automatic sync")
        self.enabled.setChecked(bool(cfg.get("enabled", True)))
        form.addRow("Auto Sync:", self.enabled)

        self.interval = QSpinBox()
        self.interval.setRange(1, 1440)
        self.interval.setSuffix(" minutes")
        self.interval.setValue(get_interval_minutes())
        form.addRow("Sync interval:", self.interval)

        self.startup = QCheckBox(
            "Run an additional sync shortly after opening a profile"
        )
        self.startup.setChecked(bool(cfg.get("sync_on_start", False)))
        form.addRow("Startup sync:", self.startup)

        root.addLayout(form)

        note = QLabel(
            "Pause Auto Sync is temporary and applies only to the current "
            "Anki session."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        qconnect(buttons.accepted, self.accept)
        qconnect(buttons.rejected, self.reject)
        root.addWidget(buttons)

        qconnect(self.enabled.toggled, self._update_controls)
        self._update_controls(self.enabled.isChecked())

    def _update_controls(self, enabled: bool) -> None:
        self.interval.setEnabled(enabled)
        self.startup.setEnabled(enabled)

    def accept(self) -> None:
        global _paused

        cfg = {
            "enabled": self.enabled.isChecked(),
            "interval_minutes": self.interval.value(),
            "sync_on_start": self.startup.isChecked(),
        }
        save_config(cfg)

        if not cfg["enabled"]:
            _paused = False

        restart_timer()
        update_menu_state()
        super().accept()


def show_settings() -> None:
    AutoSyncSettingsDialog(mw).exec()


def update_menu_state() -> None:
    cfg = get_config()
    enabled = bool(cfg.get("enabled", True))
    profile_open = mw.col is not None

    if _sync_now_action is not None:
        _sync_now_action.setEnabled(profile_open and not _sync_in_progress)

    if _pause_action is not None:
        _pause_action.setEnabled(enabled and profile_open and not _sync_in_progress)
        _pause_action.blockSignals(True)
        _pause_action.setChecked(_paused)
        _pause_action.blockSignals(False)


def setup_tools_menu() -> None:
    global _menu, _sync_now_action, _pause_action, _settings_action

    if _menu is not None:
        return

    _menu = QMenu(ADDON_NAME, mw)
    mw.form.menuTools.addMenu(_menu)

    _sync_now_action = QAction("Sync Now", mw)
    qconnect(_sync_now_action.triggered, sync_now)
    _menu.addAction(_sync_now_action)

    _pause_action = QAction("Pause Auto Sync", mw)
    _pause_action.setCheckable(True)
    qconnect(_pause_action.toggled, set_paused)
    _menu.addAction(_pause_action)

    _menu.addSeparator()

    _settings_action = QAction("Settings...", mw)
    qconnect(_settings_action.triggered, show_settings)
    _menu.addAction(_settings_action)

    update_menu_state()


def on_profile_open() -> None:
    start_timer()
    update_menu_state()

    if get_config().get("sync_on_start", False) and not _paused:
        QTimer.singleShot(5000, auto_sync)


def on_profile_close() -> None:
    stop_timer()
    update_menu_state()


gui_hooks.profile_did_open.append(on_profile_open)
gui_hooks.profile_will_close.append(on_profile_close)
gui_hooks.sync_will_start.append(on_sync_will_start)
gui_hooks.sync_did_finish.append(on_sync_did_finish)

setup_tools_menu()
