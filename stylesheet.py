# Master QSS Stylesheet for MultiMangaScraper

# Colors
SURFACE_0 = "#0d0d12"
SURFACE_1 = "#13131a"
SURFACE_2 = "#1c1c27"
SURFACE_3 = "#252535"
BORDER = "#2e2e42"
ACCENT = "#e8523a"
ACCENT_DIM = "#7a2a1f"
TEXT_PRIMARY = "#f0f0f5"
TEXT_SECONDARY = "#8a8aa0"
TEXT_MUTED = "#55556a"
SUCCESS = "#2ecc71"
WARNING = "#f39c12"
INFO = "#3498db"

STYLESHEET = f"""
* {{
    font-family: "DM Sans", "Segoe UI", sans-serif;
    font-size: 14px;
    color: {TEXT_PRIMARY};
}}

QMainWindow, QDialog, QWidget#centralWidget, QScrollArea, QStackedWidget {{
    background-color: {SURFACE_0};
}}

/* Ensure all generic containers inherit background */
#DetailPanel, #SidePanel, QScrollArea QWidget {{
    background-color: transparent;
}}

/* Top Bar */
#TopBar {{
    background-color: {SURFACE_1};
    border-bottom: 1px solid {BORDER};
    min-height: 56px;
    max-height: 56px;
}}

/* Side Panel */
#SidePanel {{
    background-color: {SURFACE_1};
    border-right: 1px solid {BORDER};
    min-width: 280px;
    max-width: 280px;
}}

/* Generic Containers */
QFrame#ControlsBar, QFrame#OptionsBar {{
    background-color: {SURFACE_1};
    border-top: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
}}

/* Inputs */
QLineEdit {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    selection-background-color: {ACCENT};
}}

QLineEdit:focus {{
    border: 1px solid {ACCENT};
}}

/* Buttons */
QPushButton {{
    background-color: {SURFACE_3};
    border: 1px solid {BORDER};
    border-radius: 18px;
    padding: 8px 20px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {SURFACE_2};
}}

QPushButton:pressed {{
    background-color: {SURFACE_3};
}}

QPushButton#AccentButton {{
    background-color: {ACCENT};
    color: white;
    border: none;
}}

QPushButton#AccentButton:hover {{
    background-color: #f06a55;
}}

QPushButton#LibraryButton {{
    background-color: {SURFACE_3};
    border: 1px solid {BORDER};
}}

/* Combo Box */
QComboBox {{
    background-color: {SURFACE_3};
    border: 1px solid {BORDER};
    border-radius: 18px;
    padding: 4px 12px;
    min-width: 130px;
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {SURFACE_3};
}}

/* Tree and Table Widgets */
QTreeWidget, QTableWidget {{
    background-color: {SURFACE_0};
    border: none;
    alternate-background-color: #0f0f16;
    color: {TEXT_PRIMARY};
}}

QTreeWidget::item {{
    color: {TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: {SURFACE_1};
    color: {TEXT_MUTED};
    padding: 8px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-size: 11px;
    text-transform: uppercase;
    font-weight: bold;
}}

QTreeView::item, QTableView::item {{
    padding: 10px;
    border-bottom: 1px solid {BORDER};
}}

QTreeView::item:hover, QTableView::item:hover {{
    background-color: {SURFACE_2};
}}

QTreeView::item:selected, QTableView::item:selected {{
    background-color: {SURFACE_2};
    border-left: 3px solid {ACCENT};
}}

/* ScrollBars */
QScrollBar:vertical {{
    border: none;
    background: {SURFACE_1};
    width: 8px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 20px;
    border-radius: 4px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    border: none;
    background: {SURFACE_1};
    height: 8px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER};
    min-width: 20px;
    border-radius: 4px;
}}

/* Labels */
QLabel#MangaTitle {{
    font-size: 32px;
    font-weight: 800;
    color: {TEXT_PRIMARY};
}}

QLabel#SectionHeader {{
    font-size: 13px;
    font-weight: bold;
    color: {TEXT_SECONDARY};
    text-transform: uppercase;
}}

QLabel#Badge {{
    padding: 2px 10px;
    border-radius: 11px;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
}}

/* Checkboxes */
QCheckBox {{
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1.5px solid {BORDER};
    border-radius: 4px;
    background-color: {SURFACE_2};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border: 1.5px solid {ACCENT};
    image: url(icons/check.svg); /* Fallback to custom drawing if needed */
}}

/* Splitter */
QSplitter::handle {{
    background-color: {BORDER};
}}
"""
