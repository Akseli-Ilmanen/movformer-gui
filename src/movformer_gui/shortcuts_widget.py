"""Widget displaying all keyboard and mouse shortcuts."""

from qtpy.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ShortcutsDialog(QDialog):
    """Dialog displaying all available keyboard and mouse shortcuts in a table."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("Keyboard & Mouse Shortcuts")
        self.setModal(False)  # Allow interaction with napari while open
        self.resize(800, 600)  # Large size to span across napari
        self._setup_ui()
        self._populate_shortcuts_table()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Create shortcuts table
        self.shortcuts_table = QTableWidget()
        self.shortcuts_table.setColumnCount(3)
        self.shortcuts_table.setHorizontalHeaderLabels(["Shortcut", "Category", "Description"])

        # Hide row numbers (left column)
        self.shortcuts_table.verticalHeader().setVisible(False)

        # Set column widths - make description column much wider
        header = self.shortcuts_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Shortcut column - fixed width
        header.setSectionResizeMode(1, QHeaderView.Fixed)  # Category column - fixed width
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Description column - stretches

        # Set specific widths - description column will be ~10x wider due to stretch
        self.shortcuts_table.setColumnWidth(0, 80)  # Shortcut column
        self.shortcuts_table.setColumnWidth(1, 100)  # Category column
        # Description column will automatically use remaining space (~620px with stretch)

        # Make table read-only
        self.shortcuts_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.shortcuts_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        # Enable word wrap for better text display
        self.shortcuts_table.setWordWrap(True)

        layout.addWidget(self.shortcuts_table)

        # Add close button
        button_layout = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

    def _populate_shortcuts_table(self):
        """Populate the shortcuts table with all available shortcuts."""
        shortcuts_data = [
            # Navigation
            ("M", "Navigation", "Go to next trial"),
            ("N", "Navigation", "Go to previous trial"),
            ("Ctrl+Alt+P", "Navigation", "Play/pause video (napari built-in)"),
            ("", "", ""),  # Empty row for spacing
            # Motif Labeling
            (
                "1",
                "Motif Label",
                "Motif 1 - Press key, then click twice on plot to define start/end",
            ),
            (
                "2",
                "Motif Label",
                "Motif 2 - Press key, then click twice on plot to define start/end",
            ),
            (
                "3",
                "Motif Label",
                "Motif 3 - Press key, then click twice on plot to define start/end",
            ),
            (
                "4",
                "Motif Label",
                "Motif 4 - Press key, then click twice on plot to define start/end",
            ),
            (
                "5",
                "Motif Label",
                "Motif 5 - Press key, then click twice on plot to define start/end",
            ),
            (
                "6",
                "Motif Label",
                "Motif 6 - Press key, then click twice on plot to define start/end",
            ),
            (
                "7",
                "Motif Label",
                "Motif 7 - Press key, then click twice on plot to define start/end",
            ),
            (
                "8",
                "Motif Label",
                "Motif 8 - Press key, then click twice on plot to define start/end",
            ),
            (
                "9",
                "Motif Label",
                "Motif 9 - Press key, then click twice on plot to define start/end",
            ),
            (
                "0",
                "Motif Label",
                "Motif 10 - Press key, then click twice on plot to define start/end",
            ),
            (
                "Q",
                "Motif Label",
                "Motif 11 - Press key, then click twice on plot to define start/end",
            ),
            (
                "W",
                "Motif Label",
                "Motif 12 - Press key, then click twice on plot to define start/end",
            ),
            (
                "R",
                "Motif Label",
                "Motif 13 - Press key, then click twice on plot to define start/end",
            ),
            (
                "T",
                "Motif Label",
                "Motif 14 - Press key, then click twice on plot to define start/end",
            ),
            ("", "", ""),  # Empty row for spacing
            # Motif Operations
            (
                "E",
                "Motif Edit",
                "Edit selected motif boundaries - Click on motif to select, then press E, then click twice to redefine boundaries",
            ),
            ("D", "Motif Edit", "Delete selected motif - Click on motif to select, then press D"),
            ("", "", ""),  # Empty row for spacing
            # Mouse Controls
            ("Left Click", "Mouse", "Click on motif to select, then press E (Edit) or D (Delete)."),
            (
                "Left Click x2",
                "Mouse",
                "After pressing a motif shortcut key (1-9, 0, Q, W, R, T), click twice on the plot to define start and end of new motif region",
            ),
            (
                "Right Click",
                "Mouse",
                "Play motif segment at cursor position - if clicked on an existing motif, plays that segment",
            ),
            (
                "Right Click x2",
                "Mouse",
                "Interrupt current video playback - click right mouse button again while video is playing to stop it",
            ),
        ]

        self.shortcuts_table.setRowCount(len(shortcuts_data))

        for row, (shortcut, category, description) in enumerate(shortcuts_data):
            # Shortcut column
            shortcut_item = QTableWidgetItem(shortcut)
            self.shortcuts_table.setItem(row, 0, shortcut_item)

            # Category column
            category_item = QTableWidgetItem(category)
            self.shortcuts_table.setItem(row, 1, category_item)

            # Description column
            description_item = QTableWidgetItem(description)
            self.shortcuts_table.setItem(row, 2, description_item)

        # Resize rows to fit content
        self.shortcuts_table.resizeRowsToContents()


class ShortcutsWidget(QWidget):
    """Widget that provides a button to show the shortcuts dialog."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.dialog = None
        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Create button to show shortcuts
        show_button = QPushButton("Show All Shortcuts")
        show_button.clicked.connect(self.show_shortcuts)
        layout.addWidget(show_button)

    def show_shortcuts(self):
        """Show the shortcuts dialog."""
        if self.dialog is None:
            self.dialog = ShortcutsDialog(parent=self.parent())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _populate_shortcuts_table(self):
        """Populate the shortcuts table with all available shortcuts."""
        shortcuts_data = [
            # Navigation
            ("", "Navigation", ""),
            ("M", "Navigation", "Go to next trial"),
            ("N", "Navigation", "Go to previous trial"),
            ("Ctrl+Alt+P", "Navigation", "Play/pause video (napari built-in)"),
            # Motif Shortcuting - Numbers
            ("1", "Motif Shortcut", "Motif 1"),
            ("2", "Motif Shortcut", "Motif 2"),
            ("3", "Motif Shortcut", "Motif 3"),
            ("4", "Motif Shortcut", "Motif 4"),
            ("5", "Motif Shortcut", "Motif 5"),
            ("6", "Motif Shortcut", "Motif 6"),
            ("7", "Motif Shortcut", "Motif 7"),
            ("8", "Motif Shortcut", "Motif 8"),
            ("9", "Motif Shortcut", "Motif 9"),
            ("0", "Motif Shortcut", "Motif 10"),
            # Motif Shortcuting - Letters
            ("Q", "Motif Shortcut", "Motif 11"),
            ("W", "Motif Shortcut", "Motif 12"),
            ("R", "Motif Shortcut", "Motif 13"),
            ("T", "Motif Shortcut", "Motif 14"),
            # Mouse Controls
            ("", "Mouse", ""),  # Empty row for spacing
            (
                "Left Click",
                "Mouse",
                "(After motif shortcut button), click 2x to select start/end for new motif",
            ),
            (
                "Left Click",
                "Mouse",
                "Click on motif, then 'D' for delete or 'E + LeftClick + LeftClick' for edit",
            ),
            ("Right Click", "Mouse", "Play motif segment at cursor position"),
            ("Right Click×2", "Mouse", "Interrupt current video playback"),
            # Motif Operations
            ("E", "Motif Edit", "Edit selected motif boundaries"),
            ("D", "Motif Edit", "Delete selected motif"),
        ]

        self.shortcuts_table.setRowCount(len(shortcuts_data))

        for row, (shortcut, category, description) in enumerate(shortcuts_data):
            # Shortcut column
            shortcut_item = QTableWidgetItem(shortcut)
            self.shortcuts_table.setItem(row, 0, shortcut_item)

            # Category column
            category_item = QTableWidgetItem(category)
            self.shortcuts_table.setItem(row, 1, category_item)

            # Description column
            description_item = QTableWidgetItem(description)
            self.shortcuts_table.setItem(row, 2, description_item)
