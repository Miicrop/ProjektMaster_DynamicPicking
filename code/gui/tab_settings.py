"""Tab "Einstellungen": all values of config/system.yaml as an editable tree.

Changes apply immediately to the running session (image processing reads the config on
every call); camera source and robot IP take effect after reconnecting. "Speichern"
writes the file - comments are preserved.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from gui.config_store import ConfigStore, eol_comment, format_value, parse_value

PATH_ROLE = Qt.ItemDataRole.UserRole


class SettingsTab(QWidget):
    changed = Signal()      # config edited (not necessarily saved)

    def __init__(self, store: ConfigStore, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store
        self._loading = False

        self.filter = QLineEdit(placeholderText="Filter, z. B. hole, robot, px_per_mm …")
        self.filter.textChanged.connect(self._apply_filter)
        self.btn_save = QPushButton("Speichern")
        self.btn_reload = QPushButton("Verwerfen / neu laden")
        self.btn_save.clicked.connect(self.save)
        self.btn_reload.clicked.connect(self.reload)
        self.state = QLabel()
        bar = QHBoxLayout()
        bar.addWidget(self.filter, 1)
        bar.addWidget(self.state)
        bar.addWidget(self.btn_save)
        bar.addWidget(self.btn_reload)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Schlüssel", "Wert", "Kommentar"])
        self.tree.setAlternatingRowColors(True)
        self.tree.itemChanged.connect(self._edited)

        hint = QLabel("Doppelklick auf einen Wert zum Bearbeiten. Listen als <code>[1.0, 2.0]</code>. "
                      "Bildverarbeitung übernimmt Änderungen sofort, Kamera-Quelle und Roboter-IP "
                      "nach erneutem Verbinden.")
        hint.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addLayout(bar)
        layout.addWidget(self.tree, 1)
        layout.addWidget(hint)
        self.populate()

    # -- tree ----------------------------------------------------------------------
    def populate(self) -> None:
        self._loading = True
        self.tree.clear()
        self._add(self.tree.invisibleRootItem(), self.store.data, [])
        self.tree.expandToDepth(0)
        self.tree.resizeColumnToContents(0)
        self.tree.setColumnWidth(1, 260)
        self._loading = False
        self._update_state()

    def _add(self, parent: QTreeWidgetItem, mapping: Any, path: list) -> None:
        for key, value in mapping.items():
            item = QTreeWidgetItem(parent, [str(key), "", eol_comment(mapping, key)])
            item.setForeground(2, QBrush(QColor("#777")))
            if isinstance(value, dict):
                f = item.font(0)
                f.setBold(True)
                item.setFont(0, f)
                self._add(item, value, path + [key])
            else:
                item.setText(1, format_value(value))
                item.setData(0, PATH_ROLE, path + [key])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

    def _edited(self, item: QTreeWidgetItem, column: int) -> None:
        if self._loading or column != 1:
            return
        path = item.data(0, PATH_ROLE)
        old = self.store.get(path)
        try:
            value = parse_value(item.text(1), old)
        except Exception as e:
            QMessageBox.warning(self, "Ungültiger Wert", f"{'.'.join(map(str, path))}: {e}")
            self._loading = True
            item.setText(1, format_value(old))
            self._loading = False
            return
        self.store.set(path, value)
        item.setBackground(1, QBrush(QColor("#fff59d")))
        self._update_state()
        self.changed.emit()

    def _apply_filter(self, text: str) -> None:
        text = text.lower().strip()

        def visit(item: QTreeWidgetItem, parent_match: bool) -> bool:
            match = not text or parent_match or any(text in item.text(c).lower() for c in range(3))
            child_match = False
            for i in range(item.childCount()):
                child_match |= visit(item.child(i), match and bool(text))
            item.setHidden(not (match or child_match))
            if text and (child_match or match) and item.childCount():
                item.setExpanded(True)
            return match or child_match
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            visit(root.child(i), False)

    # -- file ----------------------------------------------------------------------
    def _update_state(self) -> None:
        self.state.setText("<b style='color:#e65100'>ungespeicherte Änderungen</b>" if self.store.dirty
                           else "gespeichert")

    def save(self) -> None:
        try:
            self.store.save()
        except Exception as e:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(e))
            return
        self.populate()

    def reload(self) -> None:
        if self.store.dirty and QMessageBox.question(
                self, "Verwerfen?", "Ungespeicherte Änderungen verwerfen?") != QMessageBox.StandardButton.Yes:
            return
        self.store.reload()
        self.populate()
        self.changed.emit()

    def refresh(self) -> None:
        """Called when the tab becomes visible - values may have been changed elsewhere."""
        self.populate()
        self._apply_filter(self.filter.text())
