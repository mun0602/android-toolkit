# Style Sheet cho Android Toolkit (QSS)
# Mang phong cách Dark Mode cao cấp, hiện đại và công nghệ.

DARK_STYLE = """
QMainWindow {
    background-color: #0f0f12;
}

/* Tab Widget Styling */
QTabWidget::pane {
    border: 1px solid #23232a;
    background-color: #16161a;
    border-radius: 12px;
    top: -1px;
}

QTabWidget {
    background-color: transparent;
}

QTabBar::tab {
    background-color: #1a1a22;
    color: #8c8c9a;
    border: 1px solid #23232a;
    border-bottom: none;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 500;
    font-family: 'Segoe UI', Arial, sans-serif;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
}

QTabBar::tab:hover {
    background-color: #23232e;
    color: #e0e0e0;
}

QTabBar::tab:selected {
    background-color: #16161a;
    color: #00f0ff;
    border-bottom: 2px solid #00f0ff;
    font-weight: bold;
}

/* Buttons Styling */
QPushButton {
    background-color: #1f1f27;
    color: #ffffff;
    border: 1px solid #32323f;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    font-family: 'Segoe UI', Arial, sans-serif;
}

QPushButton:hover {
    background-color: #2b2b37;
    border-color: #00f0ff;
}

QPushButton:pressed {
    background-color: #181820;
}

QPushButton:disabled {
    background-color: #141418;
    color: #52525c;
    border-color: #1a1a22;
}

/* Primary/Accent Buttons */
QPushButton#primaryButton {
    background-color: #00adb5;
    color: #0f0f12;
    border: none;
    font-weight: bold;
}

QPushButton#primaryButton:hover {
    background-color: #00f0ff;
}

QPushButton#primaryButton:pressed {
    background-color: #008f95;
}

/* Danger Buttons */
QPushButton#dangerButton {
    background-color: #2d181b;
    color: #ff5555;
    border: 1px solid #5a262b;
}

QPushButton#dangerButton:hover {
    background-color: #ff5555;
    color: #0f0f12;
}

QPushButton#dangerButton:pressed {
    background-color: #bd3c3c;
}

/* Line Edits & Spin Boxes */
QLineEdit, QComboBox {
    background-color: #1b1b22;
    color: #ffffff;
    border: 1px solid #32323f;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
    font-family: 'Segoe UI', sans-serif;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #00f0ff;
}

QComboBox::drop-down {
    border: none;
    padding-right: 10px;
}

/* Labels */
QLabel {
    color: #e2e2e8;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

QLabel#titleLabel {
    color: #ffffff;
    font-size: 22px;
    font-weight: bold;
    letter-spacing: 1px;
}

QLabel#subtitleLabel {
    color: #00f0ff;
    font-size: 12px;
    font-weight: 500;
}

QLabel#sectionHeader {
    color: #00f0ff;
    font-size: 15px;
    font-weight: bold;
    border-bottom: 1px solid #23232a;
    padding-bottom: 5px;
    margin-bottom: 10px;
}

/* Group Box */
QGroupBox {
    border: 1px solid #23232a;
    border-radius: 8px;
    margin-top: 15px;
    font-size: 13px;
    font-weight: bold;
    color: #00f0ff;
    background-color: #141418;
    padding-top: 15px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 15px;
    padding: 0 5px;
    background-color: #0f0f12;
}

/* Table Widget */
QTableWidget {
    background-color: #141418;
    color: #ffffff;
    gridline-color: #23232a;
    border: 1px solid #23232a;
    border-radius: 8px;
}

QTableWidget::item {
    padding: 6px;
}

QTableWidget::item:selected {
    background-color: #00adb5;
    color: #0f0f12;
}

QHeaderView::section {
    background-color: #1b1b22;
    color: #8c8c9a;
    padding: 6px;
    border: 1px solid #23232a;
    font-weight: bold;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #23232a;
    border-radius: 6px;
    background-color: #141418;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
    height: 18px;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00adb5, stop:1 #00f0ff);
    border-radius: 5px;
}

/* Text Edit (Log/Console) */
QTextEdit#consoleLog {
    background-color: #0c0c0e;
    color: #00f0ff;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    border: 1px solid #23232a;
    border-radius: 8px;
    padding: 8px;
}

QTextEdit#logcatConsole {
    background-color: #09090b;
    color: #a0a0a5;
    font-family: 'Consolas', monospace;
    font-size: 11px;
    border: 1px solid #23232a;
    border-radius: 8px;
}

/* Scroll Bars */
QScrollBar:vertical {
    border: none;
    background: #141418;
    width: 10px;
    margin: 0px 0 0px 0;
}

QScrollBar::handle:vertical {
    background: #2b2b35;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #00adb5;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}

/* Status Bar */
QStatusBar {
    background-color: #131317;
    color: #8c8c9a;
    border-top: 1px solid #23232a;
}

/* Multi-device Farm Tab styling */
QFrame#deviceCard {
    background-color: #16161c;
    border: 1px solid #252530;
    border-radius: 10px;
}

QFrame#deviceCard:hover {
    border: 1px solid #00f0ff;
    background-color: #1b1b26;
}

QLabel#deviceModelLabel {
    color: #ffffff;
    font-size: 13px;
    font-weight: bold;
}

QLabel#deviceSerialLabel {
    color: #7c7c8a;
    font-size: 11px;
    font-family: 'Consolas', monospace;
}

QPushButton#accentButton {
    background-color: #002d34;
    color: #00f0ff;
    border: 1px solid #005f73;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton#accentButton:hover {
    background-color: #00adb5;
    color: #0f0f12;
    border-color: #00f0ff;
}

QPushButton#accentButton:pressed {
    background-color: #008f95;
}

/* QMessageBox Styling - Đảm bảo chữ đối lập nền dễ nhìn */
QMessageBox {
    background-color: #141418;
}

QMessageBox QLabel {
    color: #ffffff;
    font-size: 13px;
    font-family: 'Segoe UI', Arial, sans-serif;
    min-height: 40px;
}

QMessageBox QPushButton {
    background-color: #1f1f27;
    color: #ffffff;
    border: 1px solid #32323f;
    border-radius: 6px;
    padding: 6px 16px;
    min-width: 75px;
    font-weight: bold;
}

QMessageBox QPushButton:hover {
    background-color: #00adb5;
    color: #0f0f12;
    border-color: #00f0ff;
}

QMessageBox QPushButton:pressed {
    background-color: #008f95;
}
"""
