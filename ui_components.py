import os
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QFileDialog, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

class APKDragDropArea(QFrame):
    """Vùng kéo thả file APK trực quan, bo góc và có viền đứt nét hiện đại."""
    files_dropped = pyqtSignal(list) # Phát tín hiệu danh sách đường dẫn file APK khi kéo thả hoặc chọn

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("DragDropArea")
        
        # Style mặc định
        self.default_style = """
            QFrame#DragDropArea {
                border: 2px dashed #32323f;
                border-radius: 12px;
                background-color: #141418;
            }
            QFrame#DragDropArea:hover {
                border: 2px dashed #00adb5;
                background-color: #181822;
            }
        """
        # Style khi đang kéo file qua
        self.drag_style = """
            QFrame#DragDropArea {
                border: 2px dashed #00f0ff;
                border-radius: 12px;
                background-color: #1a1a2e;
            }
        """
        self.setStyleSheet(self.default_style)
        
        # Bố cục bên trong
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.icon_label = QLabel("📥", self)
        self.icon_label.setStyleSheet("font-size: 40px; margin-bottom: 5px;")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)
        
        self.text_label = QLabel("Kéo thả các file .APK vào đây\nhoặc nhấn để chọn file từ máy tính", self)
        self.text_label.setStyleSheet("color: #a0a0a5; font-size: 13px; font-weight: 500; line-height: 18px;")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.text_label)
        
        self.selected_files = []

    def mousePressEvent(self, event):
        """Mở hộp thoại chọn tệp khi người dùng click vào vùng này."""
        if event.button() == Qt.MouseButton.LeftButton:
            files, _ = QFileDialog.getOpenFileNames(
                self, 
                "Chọn các file APK để cài đặt", 
                "", 
                "Android Packages (*.apk)"
            )
            if files:
                self.selected_files = files
                self.files_dropped.emit(files)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Kích hoạt khi bắt đầu kéo file vào vùng."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self.drag_style)

    def dragLeaveEvent(self, event):
        """Khôi phục style khi kéo file ra ngoài."""
        self.setStyleSheet(self.default_style)

    def dropEvent(self, event: QDropEvent):
        """Lấy danh sách file khi thả chuột."""
        self.setStyleSheet(self.default_style)
        urls = event.mimeData().urls()
        apks = []
        for url in urls:
            filepath = url.toLocalFile()
            if filepath.lower().endswith(".apk"):
                apks.append(filepath)
        
        if apks:
            self.selected_files = apks
            self.files_dropped.emit(apks)
        event.acceptProposedAction()


class APKListWidget(QFrame):
    """Danh sách các file APK đã chọn hiển thị kèm nút xóa."""
    file_removed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #141418;
                border: 1px solid #23232a;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
                color: #ffffff;
            }
            QListWidget::item {
                border-bottom: 1px solid #1c1c22;
                padding: 6px;
            }
            QListWidget::item:hover {
                background-color: #1b1b22;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.list_widget)
        self.apks_map = {}

    def add_apks(self, apk_paths):
        for path in apk_paths:
            if path in self.apks_map:
                continue
            
            # Validate file tồn tại và có kích thước > 0 (#12)
            if not os.path.isfile(path):
                continue
            file_size = os.path.getsize(path)
            if file_size == 0:
                continue
            
            filename = os.path.basename(path)
            size_mb = file_size / (1024 * 1024)
            
            item = QListWidgetItem()
            self.list_widget.addItem(item)
            
            # Khởi tạo widget cho dòng
            row_widget = QFrame()
            row_widget.setStyleSheet("background-color: transparent; border: none;")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(5, 2, 5, 2)
            
            name_label = QLabel(f"📦 {filename} ({size_mb:.2f} MB)")
            name_label.setStyleSheet("color: #ffffff; font-weight: 500;")
            row_layout.addWidget(name_label)
            
            row_layout.addStretch()
            
            del_btn = QPushButton("✕")
            del_btn.setFixedSize(22, 22)
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2d181b;
                    color: #ff5555;
                    border: none;
                    border-radius: 11px;
                    font-weight: bold;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background-color: #ff5555;
                    color: #0f0f12;
                }
            """)
            
            # Bắt sự kiện xóa
            del_btn.clicked.connect(lambda checked, p=path, it=item: self.remove_apk(p, it))
            row_layout.addWidget(del_btn)
            
            item.setSizeHint(row_widget.sizeHint())
            self.list_widget.setItemWidget(item, row_widget)
            self.apks_map[path] = item

    def remove_apk(self, path, item):
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)
        if path in self.apks_map:
            del self.apks_map[path]
        self.file_removed.emit(path)

    def clear_all(self):
        self.list_widget.clear()
        self.apks_map.clear()

    def get_all_paths(self):
        return list(self.apks_map.keys())
