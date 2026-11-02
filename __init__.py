from __future__ import annotations

from typing import Optional

from aqt import gui_hooks, mw
from aqt.browser import Browser, SearchContext
from aqt.qt import QCheckBox, QComboBox, QHBoxLayout, QWidget


ADDON_NAME = "Field Filter"


def get_decks() -> list[dict]:
    if mw.col is None:
        return []
    return sorted(mw.col.decks.all(), key=lambda deck: deck["name"].casefold())


def get_deck_field_names(deck_name: str) -> list[str]:
    """Fields actually used in this deck and its descendants."""
    if mw.col is None or not deck_name:
        return []
    deck_ids = [
        int(deck["id"]) for deck in get_decks()
        if deck["name"] == deck_name or deck["name"].startswith(deck_name + "::")
    ]
    if not deck_ids:
        return []
    placeholders = ",".join("?" for _ in deck_ids)
    model_ids = mw.col.db.list(
        "select distinct n.mid from notes n join cards c on c.nid = n.id "
        f"where c.did in ({placeholders}) or c.odid in ({placeholders})",
        *deck_ids, *deck_ids,
    )
    names: set[str] = set()
    for model_id in model_ids:
        note_type = mw.col.models.get(model_id)
        if note_type:
            names.update(field["name"] for field in note_type.get("flds", []) if field.get("name"))
    return sorted(names, key=str.casefold)


def refresh_field_combo(browser: Browser) -> None:
    combo = browser._field_filter_combo
    previous = combo.currentText()
    combo.blockSignals(True)
    try:
        combo.clear()
        combo.addItems(get_deck_field_names(browser._field_filter_deck_combo.currentText()))
        index = combo.findText(previous)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.setEnabled(combo.count() > 0)
        combo.setToolTip("Choose the field to search in." if combo.count() else "No fields in this deck.")
    finally:
        combo.blockSignals(False)


def refresh_deck_combo(browser: Browser) -> None:
    combo = browser._field_filter_deck_combo
    previous_id = combo.currentData()
    if previous_id is None and mw.col is not None:
        previous_id = mw.col.decks.current()["id"]
    combo.blockSignals(True)
    try:
        combo.clear()
        for deck in get_decks():
            combo.addItem(deck["name"], deck["id"])
        index = combo.findData(previous_id)
        if index >= 0:
            combo.setCurrentIndex(index)
    finally:
        combo.blockSignals(False)
    refresh_field_combo(browser)


def setup_field_filter(browser: Browser) -> None:
    if hasattr(browser, "_field_filter_checkbox"):
        refresh_deck_combo(browser)
        return

    checkbox = QCheckBox("Field Filter", browser)
    checkbox.setToolTip("Search a field in the selected deck and its subdecks.")
    deck_combo = QComboBox(browser)
    deck_combo.setMinimumWidth(140)
    deck_combo.setMaximumWidth(260)
    deck_combo.setToolTip("Choose the deck to search (including subdecks).")
    deck_combo.setVisible(False)
    combo = QComboBox(browser)
    combo.setMinimumWidth(120)
    combo.setMaximumWidth(220)
    combo.setVisible(False)

    browser._field_filter_checkbox = checkbox
    browser._field_filter_deck_combo = deck_combo
    browser._field_filter_combo = combo
    refresh_deck_combo(browser)

    container = QWidget(browser)
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    row.addWidget(checkbox)
    row.addWidget(deck_combo)
    row.addWidget(combo)
    browser._field_filter_container = container

    checkbox.toggled.connect(deck_combo.setVisible)
    checkbox.toggled.connect(combo.setVisible)
    checkbox.toggled.connect(lambda enabled: refresh_deck_combo(browser) if enabled else None)
    deck_combo.currentIndexChanged.connect(lambda _index: refresh_field_combo(browser))

    layout = browser.form.gridLayout
    layout.addWidget(container, 0, 2)
    layout.setColumnStretch(1, 1)


def escape_search_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def apply_field_filter(context: SearchContext) -> None:
    if context.ids is not None:
        return
    browser = context.browser
    checkbox: Optional[QCheckBox] = getattr(browser, "_field_filter_checkbox", None)
    combo: Optional[QComboBox] = getattr(browser, "_field_filter_combo", None)
    deck_combo: Optional[QComboBox] = getattr(browser, "_field_filter_deck_combo", None)
    if checkbox is None or combo is None or deck_combo is None or not checkbox.isChecked():
        return
    field_name = combo.currentText()
    deck_name = deck_combo.currentText()
    search_text = context.search.strip()
    if not deck_name or not search_text:
        return
    deck_query = f'"deck:{escape_search_value(deck_name)}"'
    if not field_name:
        # An empty deck must not accidentally fall back to a collection-wide search.
        context.search = f'{deck_query} "{escape_search_value(search_text)}"'
        return
    field_query = escape_search_value(f"{field_name}:{search_text}")
    context.search = f'{deck_query} "{field_query}"'


gui_hooks.browser_will_show.append(setup_field_filter)
gui_hooks.browser_will_search.append(apply_field_filter)
