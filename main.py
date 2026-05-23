import os
import sys
import subprocess
import ctypes
import time
import json
import winreg
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QGroupBox, QLineEdit, QComboBox, 
    QTableWidget, QTableWidgetItem, QProgressBar, QTextEdit, 
    QCheckBox, QHeaderView, QMessageBox, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QColor, QPixmap, QShortcut, QKeySequence

from style import DARK_STYLE
from adb_wrapper import ADBWrapper, ADBTaskWorker
from ui_components import APKDragDropArea, APKListWidget

# Giới hạn số dòng tối đa trong console log để tránh rò rỉ bộ nhớ
MAX_LOG_LINES = 2000
# Giới hạn số tiến trình Scrcpy tối đa có thể khởi chạy đồng thời
MAX_SCRCPY_INSTANCES = 20

class AndroidToolkitApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Android Multi-Device Farm Controller Pro v1.3")
        self.resize(1200, 850)
        self.setMinimumSize(900, 650)
        
        # Khởi tạo ADB Wrapper
        self.adb = ADBWrapper()
        self.adb.set_demo_mode(False) # Mặc định tắt Demo Mode để chạy thiết bị thật
        
        self.devices_list = []
        self.active_worker = None
        self._model_cache = {}  # Cache model info để tránh gọi getprop liên tục
        self.output_dir = os.path.join(os.path.expanduser("~"), "Documents", "AndroidToolkit")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Thiết lập giao diện chính
        self.init_ui()
        self.setStyleSheet(DARK_STYLE)
        
        # Bộ đếm thời gian tự động quét thiết bị sau mỗi 5 giây (giảm tải ADB)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.auto_refresh_device)
        self.refresh_timer.start(5000)
        
        # Quét thiết bị lần đầu
        self.refresh_devices()

    def init_ui(self):
        # Widget trung tâm
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Bố cục tổng thể
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # --- HEADER AREA (Thanh Tiêu Đề Tối Giản) ---
        header_layout = QHBoxLayout()
        
        title_vbox = QVBoxLayout()
        title_label = QLabel("ANDROID MULTI-DEVICE CONTROLLER", self)
        title_label.setObjectName("titleLabel")
        title_vbox.addWidget(title_label)
        
        subtitle_label = QLabel("HỆ THỐNG ĐIỀU KHIỂN & TRÌNH CHIẾU ĐA THIẾT BỊ TẬP TRUNG (NO-TAB)", self)
        subtitle_label.setObjectName("subtitleLabel")
        title_vbox.addWidget(subtitle_label)
        header_layout.addLayout(title_vbox)
        
        header_layout.addStretch()
        
        # Nút Auto Map Python
        self.btn_map_python = QPushButton("🔗 Auto Map Python")
        self.btn_map_python.setObjectName("accentButton")
        self.btn_map_python.setToolTip("Tự động ánh xạ Python vào biến môi trường PATH và tạo tệp chạy nhanh .bat")
        self.btn_map_python.clicked.connect(self.auto_map_python)
        header_layout.addWidget(self.btn_map_python)

        # Công tắc Demo Mode
        self.demo_checkbox = QCheckBox("Demo Mode")
        self.demo_checkbox.setChecked(False)
        self.demo_checkbox.setStyleSheet("color: #00f0ff; font-weight: bold; font-size: 13px; margin-left: 10px;")
        self.demo_checkbox.stateChanged.connect(self.toggle_demo_mode)
        header_layout.addWidget(self.demo_checkbox)
        
        main_layout.addLayout(header_layout)
        
        # --- BODY AREA (Bố cục 2 Cột chính) ---
        body_layout = QHBoxLayout()
        body_layout.setSpacing(15)
        
        # CỘT TRÁI: Lưới thiết bị trong Farm (Chiếm 4 phần)
        left_group = QGroupBox("Danh sách thiết bị kết nối (Farm Grid)")
        left_layout = QVBoxLayout(left_group)
        left_layout.setContentsMargins(12, 15, 12, 12)
        left_layout.setSpacing(10)
        
        self.farm_table = QTableWidget(0, 4)
        self.farm_table.setHorizontalHeaderLabels(["", "Tên / Model thiết bị", "Mã Serial (ID)", "Trạng Thái"])
        self.farm_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.farm_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.farm_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.farm_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.farm_table.verticalHeader().setVisible(False)
        self.farm_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.farm_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        left_layout.addWidget(self.farm_table)
        
        # Nút chọn thiết bị nhanh
        select_layout = QHBoxLayout()
        btn_select_all = QPushButton("☑ Chọn tất cả")
        btn_select_all.clicked.connect(self.farm_select_all)
        select_layout.addWidget(btn_select_all)
        
        btn_deselect_all = QPushButton("☒ Bỏ chọn hết")
        btn_deselect_all.clicked.connect(self.farm_deselect_all)
        select_layout.addWidget(btn_deselect_all)
        
        btn_scan = QPushButton("🔄 Load thiết bị")
        btn_scan.setObjectName("accentButton")
        btn_scan.clicked.connect(self.refresh_devices)
        select_layout.addWidget(btn_scan)
        
        left_layout.addLayout(select_layout)
        body_layout.addWidget(left_group, 4)
        
        # CỘT PHẢI: Bảng điều khiển tác vụ tối giản (Chiếm 5 phần)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        
        right_group = QGroupBox("Bảng điều khiển tác vụ đồng loạt (Bulk Dashboard)")
        right_layout = QVBoxLayout(right_group)
        right_layout.setContentsMargins(15, 15, 15, 12)
        right_layout.setSpacing(12)
        
        # 1. Trình chiếu SCRCPY (Nổi bật nhất)
        scrcpy_group = QGroupBox("1. Trình chiếu Màn hình Thiết bị (Mirroring)")
        scrcpy_layout = QVBoxLayout(scrcpy_group)
        scrcpy_layout.setSpacing(8)
        
        self.btn_scrcpy = QPushButton("🖥️ Xem Màn Hình (Tải Gương Scrcpy)")
        self.btn_scrcpy.setObjectName("accentButton")
        self.btn_scrcpy.setFixedHeight(45)
        self.btn_scrcpy.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.btn_scrcpy.clicked.connect(self.farm_scrcpy_mirror)
        scrcpy_layout.addWidget(self.btn_scrcpy)
        
        # Cấu hình kích thước & xếp lưới Scrcpy
        config_layout = QHBoxLayout()
        config_layout.setSpacing(10)
        
        lbl_size = QLabel("Cỡ cửa sổ:")
        lbl_size.setStyleSheet("font-weight: bold; color: #8c8c9a;")
        config_layout.addWidget(lbl_size)
        
        self.cbo_scrcpy_size = QComboBox()
        self.cbo_scrcpy_size.addItems(["Trung bình (320x640)", "Nhỏ (240x480)", "Lớn (400x800)", "Mặc định (Tự do)"])
        self.cbo_scrcpy_size.setFixedWidth(160)
        config_layout.addWidget(self.cbo_scrcpy_size)
        
        config_layout.addStretch()
        
        self.btn_tile_windows = QPushButton("🧩 Xếp lưới cửa sổ")
        self.btn_tile_windows.setObjectName("accentButton")
        self.btn_tile_windows.setFixedWidth(150)
        self.btn_tile_windows.clicked.connect(self.farm_arrange_windows)
        config_layout.addWidget(self.btn_tile_windows)
        
        self.btn_close_all_scrcpy = QPushButton("❌ Đóng tất cả")
        self.btn_close_all_scrcpy.setObjectName("dangerButton")
        self.btn_close_all_scrcpy.setFixedWidth(120)
        self.btn_close_all_scrcpy.setToolTip("Đóng tất cả cửa sổ Scrcpy đang mở")
        self.btn_close_all_scrcpy.clicked.connect(self.farm_close_all_scrcpy)
        config_layout.addWidget(self.btn_close_all_scrcpy)
        
        scrcpy_layout.addLayout(config_layout)
        
        lbl_scrcpy_desc = QLabel("Bật cửa sổ tương tác Scrcpy song song cho toàn bộ thiết bị đang tích chọn.")
        lbl_scrcpy_desc.setStyleSheet("color: #8c8c9a; font-size: 11px; font-style: italic; text-align: center;")
        lbl_scrcpy_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scrcpy_layout.addWidget(lbl_scrcpy_desc)
        right_layout.addWidget(scrcpy_group)
        
        # 2. Cài đặt file APK
        apk_group = QGroupBox("2. Cài đặt APK hàng loạt")
        apk_layout = QVBoxLayout(apk_group)
        apk_layout.setSpacing(8)
        
        self.drag_area = APKDragDropArea()
        self.drag_area.setFixedHeight(95)
        self.drag_area.files_dropped.connect(self.on_apks_selected)
        apk_layout.addWidget(self.drag_area)
        
        self.apk_list = APKListWidget()
        self.apk_list.setFixedHeight(95)
        apk_layout.addWidget(self.apk_list)
        
        opts_layout = QHBoxLayout()
        self.chk_opt_r = QCheckBox("Ghi đè (-r)")
        self.chk_opt_r.setChecked(True)
        self.chk_opt_d = QCheckBox("Hạ cấp (-d)")
        self.chk_opt_d.setChecked(True)
        opts_layout.addWidget(self.chk_opt_r)
        opts_layout.addWidget(self.chk_opt_d)
        apk_layout.addLayout(opts_layout)
        
        self.btn_install = QPushButton("🚀 Khởi chạy Cài đặt APK đồng loạt")
        self.btn_install.setObjectName("primaryButton")
        self.btn_install.setFixedHeight(35)
        self.btn_install.clicked.connect(self.farm_install_apks)
        apk_layout.addWidget(self.btn_install)
        
        right_layout.addWidget(apk_group)
        
        # 3. Điều khiển nguồn (Reboot & Power Options)
        reboot_group = QGroupBox("3. Điều khiển Nguồn hàng loạt")
        reboot_layout = QVBoxLayout(reboot_group)
        reboot_layout.setSpacing(8)
        
        btn_grid = QHBoxLayout()
        self.btn_reboot_normal = QPushButton("🔄 Restart")
        self.btn_reboot_normal.clicked.connect(lambda: self.farm_reboot("system"))
        btn_grid.addWidget(self.btn_reboot_normal)
        
        self.btn_reboot_twrp = QPushButton("🛡️ Vào TWRP")
        self.btn_reboot_twrp.clicked.connect(lambda: self.farm_reboot("recovery"))
        btn_grid.addWidget(self.btn_reboot_twrp)
        
        self.btn_reboot_fb = QPushButton("⚡ Fastboot")
        self.btn_reboot_fb.clicked.connect(lambda: self.farm_reboot("bootloader"))
        btn_grid.addWidget(self.btn_reboot_fb)
        
        reboot_layout.addLayout(btn_grid)
        
        self.btn_power_off = QPushButton("❌ Tắt nguồn hoàn toàn (Power Off)")
        self.btn_power_off.setObjectName("dangerButton")
        self.btn_power_off.clicked.connect(lambda: self.farm_reboot("poweroff"))
        reboot_layout.addWidget(self.btn_power_off)
        
        right_layout.addWidget(reboot_group)

        # 4. Cấu hình Mạng & Hệ thống hàng loạt (Wifi, Ngôn ngữ, Múi giờ)
        system_group = QGroupBox("4. Cấu hình Mạng & Hệ thống hàng loạt")
        system_layout = QVBoxLayout(system_group)
        system_layout.setContentsMargins(12, 15, 12, 12)
        system_layout.setSpacing(8)

        # Wifi Row 1: SSID, Password, Security
        wifi_input_layout = QHBoxLayout()
        self.txt_wifi_ssid = QLineEdit()
        self.txt_wifi_ssid.setPlaceholderText("Tên WiFi (SSID)")
        self.txt_wifi_ssid.setToolTip("Nhập SSID của WiFi")

        self.txt_wifi_pass = QLineEdit()
        self.txt_wifi_pass.setPlaceholderText("Mật khẩu WiFi")
        self.txt_wifi_pass.setToolTip("Nhập mật khẩu WiFi (để trống nếu không mật khẩu)")

        self.cbo_wifi_sec = QComboBox()
        self.cbo_wifi_sec.addItems(["WPA2", "Open", "WPA3", "WEP"])
        self.cbo_wifi_sec.setFixedWidth(80)

        wifi_input_layout.addWidget(self.txt_wifi_ssid)
        wifi_input_layout.addWidget(self.txt_wifi_pass)
        wifi_input_layout.addWidget(self.cbo_wifi_sec)
        system_layout.addLayout(wifi_input_layout)

        # Wifi Row 2: Nút Kết nối Wifi
        self.btn_connect_wifi = QPushButton("📶 Kết nối WiFi hàng loạt")
        self.btn_connect_wifi.setObjectName("accentButton")
        self.btn_connect_wifi.clicked.connect(self.farm_connect_wifi)
        system_layout.addWidget(self.btn_connect_wifi)

        # Đường kẻ phân cách
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #23232a; max-height: 1px;")
        system_layout.addWidget(divider)

        # Hệ thống Row 1: Ngôn ngữ & Nút
        lang_layout = QHBoxLayout()
        self.cbo_language = QComboBox()
        self.cbo_language.addItem("Tiếng Việt (vi-VN)", "vi-VN")
        self.cbo_language.addItem("English (en-US)", "en-US")
        self.cbo_language.addItem("English (en-GB)", "en-GB")
        self.cbo_language.addItem("简体中文 (zh-CN)", "zh-CN")
        self.cbo_language.addItem("한국어 (ko-KR)", "ko-KR")
        self.cbo_language.addItem("日本語 (ja-JP)", "ja-JP")
        self.cbo_language.addItem("ภาษาไทย (th-TH)", "th-TH")

        self.btn_change_lang = QPushButton("🌐 Đổi Ngôn Ngữ")
        self.btn_change_lang.clicked.connect(self.farm_change_language)
        lang_layout.addWidget(self.cbo_language, 3)
        lang_layout.addWidget(self.btn_change_lang, 2)
        system_layout.addLayout(lang_layout)

        # Hệ thống Row 2: Múi giờ & Nút
        tz_layout = QHBoxLayout()
        self.cbo_timezone = QComboBox()
        self.cbo_timezone.addItem("Asia/Ho_Chi_Minh (GMT+7)", "Asia/Ho_Chi_Minh")
        self.cbo_timezone.addItem("Asia/Singapore (GMT+8)", "Asia/Singapore")
        self.cbo_timezone.addItem("Asia/Tokyo (GMT+9)", "Asia/Tokyo")
        self.cbo_timezone.addItem("Asia/Seoul (GMT+9)", "Asia/Seoul")
        self.cbo_timezone.addItem("Asia/Bangkok (GMT+7)", "Asia/Bangkok")
        self.cbo_timezone.addItem("America/New_York (GMT-5)", "America/New_York")
        self.cbo_timezone.addItem("America/Los_Angeles (GMT-8)", "America/Los_Angeles")
        self.cbo_timezone.addItem("Europe/London (GMT+0)", "Europe/London")

        self.btn_change_tz = QPushButton("🕒 Đổi Múi Giờ")
        self.btn_change_tz.clicked.connect(self.farm_change_timezone)
        tz_layout.addWidget(self.cbo_timezone, 3)
        tz_layout.addWidget(self.btn_change_tz, 2)
        system_layout.addLayout(tz_layout)

        right_layout.addWidget(system_group)

        right_scroll.setWidget(right_group)
        body_layout.addWidget(right_scroll, 5)
        main_layout.addLayout(body_layout)
        
        # --- FOOTER / LOG CONSOLE AREA ---
        footer_layout = QVBoxLayout()
        
        self.install_progress = QProgressBar()
        self.install_progress.setValue(0)
        self.install_progress.setVisible(False)
        footer_layout.addWidget(self.install_progress)
        
        footer_label = QLabel("Nhật ký hoạt động hệ thống (Console Log):")
        footer_label.setStyleSheet("color: #8c8c9a; font-size: 11px; font-weight: bold;")
        footer_layout.addWidget(footer_label)
        
        self.console_log = QTextEdit()
        self.console_log.setObjectName("consoleLog")
        self.console_log.setReadOnly(True)
        self.console_log.setFixedHeight(120)
        footer_layout.addWidget(self.console_log)
        
        log_ctrls = QHBoxLayout()
        log_ctrls.addStretch()
        
        clear_btn = QPushButton("Clear Log")
        clear_btn.setFixedSize(80, 24)
        clear_btn.setStyleSheet("font-size: 10px; padding: 2px;")
        clear_btn.clicked.connect(self.console_log.clear)
        log_ctrls.addWidget(clear_btn)
        
        copy_btn = QPushButton("Copy Log")
        copy_btn.setFixedSize(80, 24)
        copy_btn.setStyleSheet("font-size: 10px; padding: 2px;")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.console_log.toPlainText()))
        log_ctrls.addWidget(copy_btn)
        
        footer_layout.addLayout(log_ctrls)
        main_layout.addLayout(footer_layout)
        
        self.statusBar().showMessage("Ứng dụng chạy thành công. Đang ở chế độ tương tác thiết bị thật.")

    # ================= LOGIC & SỰ KIỆN XỬ LÝ HÀNG LOẠT =================

    def log(self, text):
        t_str = time.strftime("[%H:%M:%S]")
        self.console_log.append(f"{t_str} {text}")
        # Giới hạn số dòng log để tránh rò rỉ bộ nhớ (#21)
        doc = self.console_log.document()
        if doc.blockCount() > MAX_LOG_LINES:
            cursor = self.console_log.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, doc.blockCount() - MAX_LOG_LINES)
            cursor.removeSelectedText()
            cursor.deleteChar()  # Xóa newline thừa

    def toggle_demo_mode(self, state):
        enabled = (state == Qt.CheckState.Checked.value or state == True)
        self.adb.set_demo_mode(enabled)
        mode_text = "Chế độ mô phỏng (Demo Mode)" if enabled else "Chế độ tương tác thực tế (ADB/Fastboot)"
        self.log(f"Đã chuyển sang: {mode_text}")
        self.refresh_devices()

    def auto_map_python(self):
        """Tự động ánh xạ Python hiện tại vào PATH hệ thống và tạo file run.bat"""
        self.log("Bắt đầu tiến trình Tự động ánh xạ Python (Auto Map Python)...")
        
        try:
            # 1. Xác định thư mục Python hiện tại
            # Nếu đang chạy bằng virtualenv, sys.base_prefix sẽ trỏ tới thư mục cài đặt Python gốc
            # sys.executable là python.exe hiện tại đang chạy (có thể là trong .venv)
            base_py_dir = os.path.abspath(sys.base_prefix)
            base_scripts_dir = os.path.abspath(os.path.join(base_py_dir, "Scripts"))
            
            curr_py_dir = os.path.abspath(os.path.dirname(sys.executable))
            curr_scripts_dir = os.path.abspath(os.path.join(curr_py_dir, "Scripts"))
            
            paths_to_add = []
            
            # Thêm các đường dẫn gốc
            if os.path.exists(base_py_dir):
                paths_to_add.append(base_py_dir)
            if os.path.exists(base_scripts_dir):
                paths_to_add.append(base_scripts_dir)
                
            # Thêm các đường dẫn hiện tại nếu khác gốc
            if curr_py_dir != base_py_dir and os.path.exists(curr_py_dir):
                paths_to_add.append(curr_py_dir)
            if curr_scripts_dir != base_scripts_dir and os.path.exists(curr_scripts_dir):
                paths_to_add.append(curr_scripts_dir)
                
            # Loại bỏ trùng lặp
            paths_to_add = list(dict.fromkeys(paths_to_add))
            
            self.log(f"Phát hiện các thư mục Python: {', '.join(paths_to_add)}")
            
            # 2. Cập nhật PATH của User thông qua Windows Registry (An toàn, không bị giới hạn 1024 ký tự như setx)
            registry_success = False
            registry_msg = ""
            
            try:
                # Mở Registry khoá Environment của User hiện tại
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
                
                # Đọc PATH hiện tại
                try:
                    current_path, data_type = winreg.QueryValueEx(key, "PATH")
                except FileNotFoundError:
                    current_path = ""
                    data_type = winreg.REG_EXPAND_SZ
                
                # Tách các đường dẫn hiện có
                existing_paths = [p.strip().rstrip('\\') for p in current_path.split(';') if p.strip()]
                
                added_paths = []
                for p in paths_to_add:
                    p_clean = p.rstrip('\\')
                    # So sánh không phân biệt hoa thường
                    if not any(ex.lower() == p_clean.lower() for ex in existing_paths):
                        existing_paths.append(p_clean)
                        added_paths.append(p_clean)
                
                if added_paths:
                    new_path = ";".join(existing_paths)
                    winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
                    
                    # Phát tín hiệu thông báo cho toàn bộ hệ thống cập nhật môi trường mới
                    # HWND_BROADCAST = 0xFFFF, WM_SETTINGCHANGE = 0x001A
                    ctypes.windll.user32.SendMessageTimeoutW(
                        0xFFFF, 0x001A, 0, "Environment", 0x0002, 1000, ctypes.byref(ctypes.c_long())
                    )
                    
                    registry_success = True
                    registry_msg = f"Đã thêm thành công {len(added_paths)} đường dẫn mới vào Registry PATH:\n" + "\n".join([f"- {x}" for x in added_paths])
                else:
                    registry_success = True
                    registry_msg = "Đường dẫn cài đặt Python đã có sẵn trong biến môi trường PATH của bạn."
                
                winreg.CloseKey(key)
                
            except Exception as reg_err:
                registry_success = False
                registry_msg = f"Lỗi khi ghi Registry: {reg_err}"
                self.log("Gặp lỗi khi ghi vào Registry. Thử phương án dự phòng bằng lệnh setx...")
                
                # Phương án dự phòng bằng setx nếu lỗi Registry (không dùng shell=True để tránh injection)
                try:
                    for p in paths_to_add:
                        current_env_path = os.environ.get("PATH", "")
                        new_val = f"{current_env_path};{p}"
                        subprocess.run(["setx", "PATH", new_val], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    registry_success = True
                    registry_msg = "Đã thử ánh xạ Python thông qua phương thức dự phòng 'setx'."
                except Exception as setx_err:
                    registry_msg = f"Cả hai phương thức Registry và setx đều thất bại. Chi tiết lỗi Registry: {reg_err}, setx: {setx_err}"
            
            # 3. Tạo tệp khởi chạy nhanh run.bat cục bộ tại thư mục dự án
            bat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.bat")
            
            # Nội dung file BAT thông minh bằng tiếng Việt
            bat_content = f"""@echo off
title Khởi chạy Android Farm Controller Pro
chcp 65001 >nul
cd /d "%~dp0"
echo =======================================================
echo    KHỞI CHẠY ANDROID Farm Controller Pro v1.2
echo =======================================================
echo.

:: 1. Ưu tiên dùng môi trường ảo .venv cục bộ nếu tồn tại
if exist ".venv\\Scripts\\python.exe" (
    echo [OK] Phát hiện môi trường ảo .venv cục bộ.
    echo Đang khởi chạy ứng dụng...
    start "" ".venv\\Scripts\\python.exe" main.py
    exit /b
)

:: 2. Kiểm tra xem python trong PATH có hoạt động không
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Phát hiện Python hệ thống từ biến môi trường PATH.
    echo Đang khởi chạy ứng dụng...
    start "" python main.py
    exit /b
)

:: 3. Nếu không tìm thấy python, thử chạy bằng đường dẫn Python lúc ghi nhận
if exist "{sys.executable}" (
    echo [OK] Khởi chạy bằng đường dẫn Python lúc ghi nhận: "{sys.executable}"
    start "" "{sys.executable}" main.py
    exit /b
)

echo [LỖI] Không tìm thấy trình thông dịch Python phù hợp trên máy!
echo Vui lòng cài đặt Python và tích chọn "Add Python to PATH" lúc cài đặt.
echo.
pause
"""
            
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)
                
            self.log(f"Đã tạo thành công tệp khởi chạy nhanh cục bộ: '{bat_path}'")
            
            # Hiển thị thông báo kết quả cho người dùng bằng tiếng Việt
            if registry_success:
                self.log("Ánh xạ Python thành công!")
                QMessageBox.information(
                    self, 
                    "Thành công", 
                    f"🏆 TỰ ĐỘNG ÁNH XẠ PYTHON HOÀN TẤT!\n\n"
                    f"1. {registry_msg}\n\n"
                    f"2. Đã tạo tệp khởi chạy nhanh cục bộ 'run.bat' tại thư mục dự án.\n\n"
                    f"👉 LƯU Ý: Nếu chạy qua Command Prompt (CMD), bạn vui lòng ĐÓNG và MỞ LẠI cửa sổ CMD mới để Windows cập nhật biến môi trường PATH."
                )
            else:
                self.log(f"Ánh xạ thất bại: {registry_msg}")
                QMessageBox.critical(
                    self,
                    "Lỗi",
                    f"Không thể ánh xạ biến môi trường tự động.\n\nChi tiết lỗi:\n{registry_msg}\n\n"
                    f"Tuy nhiên, tệp khởi chạy nhanh 'run.bat' đã được tạo thành công trong thư mục dự án, bạn vẫn có thể đúp-click tệp đó để chạy."
                )
                
        except Exception as ex:
            self.log(f"Lỗi hệ thống khi thực thi Auto Map Python: {ex}")
            QMessageBox.critical(self, "Lỗi hệ thống", f"Có lỗi xảy ra: {str(ex)}")

    def auto_refresh_device(self):
        self.refresh_devices(silent=True)

    def refresh_devices(self, silent=False):
        try:
            devices = self.adb.get_devices()
            self.devices_list = devices
            
            checked_ids = self.get_checked_farm_devices()
            
            # Cache model info để tránh gọi getprop mỗi lần refresh (#4, #17)
            for dev in devices:
                if dev["id"] not in self._model_cache or dev.get("model") != self._model_cache.get(dev["id"]):
                    self._model_cache[dev["id"]] = dev.get("model", "Unknown Device")
            
            # Chỉ rebuild bảng nếu danh sách thiết bị thay đổi (#18)
            current_ids = [dev["id"] for dev in devices]
            table_ids = []
            for r in range(self.farm_table.rowCount()):
                id_item = self.farm_table.item(r, 2)
                if id_item:
                    table_ids.append(id_item.text())
            
            # So sánh: nếu danh sách không đổi, chỉ update trạng thái
            if current_ids == table_ids and len(devices) > 0:
                for idx, dev in enumerate(devices):
                    state_item = self.farm_table.item(idx, 3)
                    if state_item and state_item.text() != dev["state"].upper():
                        state_item.setText(dev["state"].upper())
                        if dev["state"] == "device":
                            state_item.setForeground(QColor("#00ff7f"))
                        elif dev["state"] in ["fastboot", "bootloader"]:
                            state_item.setForeground(QColor("#ffaa00"))
                        else:
                            state_item.setForeground(QColor("#00f0ff"))
                return
            
            # Rebuild toàn bộ bảng nếu danh sách thay đổi
            self.farm_table.setRowCount(0)
            
            if not devices:
                if not silent:
                    self.log("Không phát hiện thiết bị Android nào đang kết nối.")
                return
            
            for idx, dev in enumerate(devices):
                self.farm_table.insertRow(idx)
                
                chk = QCheckBox()
                chk.setStyleSheet("margin-left: 8px;")
                if dev["id"] in checked_ids or (not checked_ids and idx == 0):
                    chk.setChecked(True)
                self.farm_table.setCellWidget(idx, 0, chk)
                
                self.farm_table.setItem(idx, 1, QTableWidgetItem(f"📱 {dev['model']}"))
                self.farm_table.setItem(idx, 2, QTableWidgetItem(dev["id"]))
                
                state_item = QTableWidgetItem(dev["state"].upper())
                if dev["state"] == "device":
                    state_item.setForeground(QColor("#00ff7f"))
                elif dev["state"] in ["fastboot", "bootloader"]:
                    state_item.setForeground(QColor("#ffaa00"))
                else:
                    state_item.setForeground(QColor("#00f0ff"))
                self.farm_table.setItem(idx, 3, state_item)
                
        except Exception as e:
            if not silent:
                self.log(f"Lỗi khi quét thiết bị: {str(e)}")

    def get_checked_farm_devices(self):
        checked_ids = []
        if hasattr(self, 'farm_table'):
            for r in range(self.farm_table.rowCount()):
                chk = self.farm_table.cellWidget(r, 0)
                if chk and chk.isChecked():
                    id_item = self.farm_table.item(r, 2)
                    if id_item:
                        checked_ids.append(id_item.text())
        return checked_ids

    def farm_select_all(self):
        for r in range(self.farm_table.rowCount()):
            chk = self.farm_table.cellWidget(r, 0)
            if chk:
                chk.setChecked(True)
        self.log("Đã chọn toàn bộ thiết bị.")

    def farm_deselect_all(self):
        for r in range(self.farm_table.rowCount()):
            chk = self.farm_table.cellWidget(r, 0)
            if chk:
                chk.setChecked(False)
        self.log("Đã bỏ chọn toàn bộ thiết bị.")

    def farm_scrcpy_mirror(self):
        device_ids = self.get_checked_farm_devices()
        if not device_ids:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn tối thiểu 1 thiết bị để xem màn hình.")
            return

        # Giới hạn số tiến trình Scrcpy (#3)
        if len(device_ids) > MAX_SCRCPY_INSTANCES:
            QMessageBox.warning(
                self, "Cảnh báo",
                f"Số thiết bị đã chọn ({len(device_ids)}) vượt quá giới hạn {MAX_SCRCPY_INSTANCES} phiên Scrcpy đồng thời.\n"
                f"Vui lòng bỏ chọn bớt thiết bị."
            )
            return

        # Đọc kích thước cửa sổ từ Combobox
        size_text = self.cbo_scrcpy_size.currentText()
        w, h = None, None
        if "Trung bình" in size_text:
            w, h = 320, 640
        elif "Nhỏ" in size_text:
            w, h = 240, 480
        elif "Lớn" in size_text:
            w, h = 400, 800

        self.log(f"Bắt đầu khởi chạy trình chiếu Scrcpy trên {len(device_ids)} thiết bị (Cỡ: {size_text})...")
        for device_id in device_ids:
            res, rc = self.adb.launch_scrcpy(device_id, w=w, h=h)
            self.log(f"[{device_id}] {res}")

    def _find_scrcpy_windows(self):
        """Tìm tất cả cửa sổ Scrcpy đang mở bằng Windows API."""
        from ctypes import wintypes
        
        hwnds = []
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        
        def enum_windows_callback(hwnd, lParam):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                class_buff = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetClassNameW(hwnd, class_buff, 256)
                class_name = class_buff.value
                
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    
                    is_scrcpy_class = (class_name == "SDL_app")
                    is_scrcpy_title = "scrcpy" in title.lower() or any(dev["id"] in title for dev in self.devices_list)
                    
                    if is_scrcpy_class and is_scrcpy_title:
                        hwnds.append(hwnd)
            return True
        
        try:
            self.enum_callback = EnumWindowsProc(enum_windows_callback)
            ctypes.windll.user32.EnumWindows(self.enum_callback, 0)
        except Exception as e:
            self.log(f"Lỗi khi quét cửa sổ hệ thống: {e}")
        
        return hwnds

    def farm_arrange_windows(self):
        """Tự động xếp lưới toàn bộ cửa sổ Scrcpy đang mở bằng Windows API."""
        hwnds = self._find_scrcpy_windows()
        
        if not hwnds:
            self.log("Không tìm thấy cửa sổ Scrcpy nào đang hoạt động trên màn hình.")
            QMessageBox.information(self, "Thông tin", "Không tìm thấy cửa sổ Scrcpy nào đang hoạt động trên màn hình.")
            return

        self.log(f"Đã phát hiện {len(hwnds)} cửa sổ Scrcpy đang chạy. Bắt đầu xếp lưới...")

        # Lấy kích thước màn hình (trừ taskbar)
        screen = QApplication.primaryScreen()
        if screen:
            available_geo = screen.availableGeometry()
            screen_w = available_geo.width()
            screen_h = available_geo.height()
        else:
            screen_w, screen_h = 1920, 1000

        # Tính toán số cột tối ưu dựa trên số cửa sổ
        num_windows = len(hwnds)
        
        # Tính số cột dựa trên tỷ lệ màn hình và số cửa sổ
        # Scrcpy giữ tỷ lệ 9:16 (portrait) hoặc 16:9 (landscape)
        # Giả sử tỷ lệ portrait 9:19.5 (điện thoại hiện đại)
        aspect_ratio = 9 / 19.5
        
        # Tính số cột tối ưu để lấp đầy màn hình
        if num_windows <= 2:
            cols = num_windows
        elif num_windows <= 4:
            cols = 2
        elif num_windows <= 6:
            cols = 3
        elif num_windows <= 9:
            cols = 3
        elif num_windows <= 12:
            cols = 4
        else:
            cols = 5
        
        rows = (num_windows + cols - 1) // cols
        
        # Tính kích thước cửa sổ dựa trên không gian có sẵn
        padding = 10
        gap = 5
        
        available_w = screen_w - (padding * 2) - (gap * (cols - 1))
        available_h = screen_h - (padding * 2) - (gap * (rows - 1))
        
        cell_w = available_w // cols
        cell_h = available_h // rows
        
        # Tính kích thước cửa sổ giữ tỷ lệ trong ô
        if cell_w / cell_h > aspect_ratio:
            # Ô rộng hơn tỷ lệ -> giới hạn theo chiều cao
            win_h = cell_h
            win_w = int(cell_h * aspect_ratio)
        else:
            # Ô cao hơn tỷ lệ -> giới hạn theo chiều rộng
            win_w = cell_w
            win_h = int(cell_w / aspect_ratio)
        
        self.log(f"Xếp lưới {cols} cột x {rows} hàng, kích thước mỗi cửa sổ: {win_w}x{win_h}")

        for idx, hwnd in enumerate(hwnds):
            row = idx // cols
            col = idx % cols
            
            # Tính vị trí căn giữa trong ô
            cell_x = padding + col * (cell_w + gap)
            cell_y = padding + row * (cell_h + gap)
            
            # Căn giữa cửa sổ trong ô
            x = cell_x + (cell_w - win_w) // 2
            y = cell_y + (cell_h - win_h) // 2
            
            # Di chuyển cửa sổ (chỉ thay đổi vị trí, không ép kích thước)
            # SWP_NOSIZE = 0x0001 (giữ nguyên kích thước)
            # SWP_NOZORDER = 0x0004
            # SWP_SHOWWINDOW = 0x0040
            ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, 0, 0, 0x0001 | 0x0004 | 0x0040)
            self.log(f"Đã di chuyển cửa sổ {idx+1}/{num_windows} đến vị trí: ({x}, {y})")

        self.log("🎯 Đã sắp xếp lưới thành công toàn bộ cửa sổ Scrcpy trên màn hình!")

    def farm_close_all_scrcpy(self):
        """Đóng tất cả cửa sổ Scrcpy đang mở."""
        hwnds = self._find_scrcpy_windows()
        
        if not hwnds:
            self.log("Không tìm thấy cửa sổ Scrcpy nào để đóng.")
            QMessageBox.information(self, "Thông tin", "Không có cửa sổ Scrcpy nào đang mở.")
            return
        
        confirm = QMessageBox.question(
            self,
            "Xác nhận",
            f"Bạn có chắc chắn muốn đóng tất cả {len(hwnds)} cửa sổ Scrcpy đang mở?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.No:
            return
        
        self.log(f"Đang đóng {len(hwnds)} cửa sổ Scrcpy...")
        
        # WM_CLOSE = 0x0010
        closed_count = 0
        for hwnd in hwnds:
            try:
                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
                closed_count += 1
            except Exception as e:
                self.log(f"Lỗi khi đóng cửa sổ HWND {hwnd}: {e}")
        
        self.log(f"✅ Đã gửi lệnh đóng {closed_count}/{len(hwnds)} cửa sổ Scrcpy.")

    def on_apks_selected(self, paths):
        self.apk_list.add_apks(paths)
        self.log(f"Đã chọn {len(paths)} file APK để chuẩn bị cài đặt hàng loạt.")

    def farm_install_apks(self):
        device_ids = self.get_checked_farm_devices()
        if not device_ids:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng tích chọn tối thiểu 1 thiết bị để cài đặt.")
            return

        # Kiểm tra worker đang chạy (#6)
        if self.active_worker and self.active_worker.isRunning():
            QMessageBox.warning(self, "Cảnh báo", "Đang có tác vụ khác đang chạy. Vui lòng đợi hoàn tất.")
            return

        apk_paths = self.apk_list.get_all_paths()
        if not apk_paths:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng kéo thả hoặc chọn tối thiểu 1 file APK.")
            return

        opts = []
        if self.chk_opt_r.isChecked(): opts.append("-r")
        if self.chk_opt_d.isChecked(): opts.append("-d")

        self.btn_install.setEnabled(False)
        self.install_progress.setVisible(True)
        self.install_progress.setValue(0)
        
        self.log(f"Khởi động tiến trình cài đặt APK hàng loạt lên {len(device_ids)} thiết bị...")
        
        self.active_worker = ADBTaskWorker(
            self.adb, 
            "install_apk_bulk", 
            {"device_ids": device_ids, "apk_paths": apk_paths, "options": opts}
        )
        self.active_worker.progress.connect(self.on_task_progress)
        self.active_worker.finished.connect(self.on_bulk_install_finished)
        self.active_worker.start()

    def on_task_progress(self, percent, msg):
        self.install_progress.setValue(percent)
        self.log(msg)

    def on_bulk_install_finished(self, success, msg):
        self.btn_install.setEnabled(True)
        self.install_progress.setVisible(False)
        if success:
            QMessageBox.information(self, "Thành công", msg)
            self.apk_list.clear_all()
        else:
            QMessageBox.critical(self, "Lỗi cài đặt", msg)
        self.active_worker = None

    def farm_reboot(self, mode):
        device_ids = self.get_checked_farm_devices()
        if not device_ids:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn tối thiểu 1 thiết bị để thực hiện.")
            return

        # Kiểm tra worker đang chạy (#6)
        if self.active_worker and self.active_worker.isRunning():
            QMessageBox.warning(self, "Cảnh báo", "Đang có tác vụ khác đang chạy. Vui lòng đợi hoàn tất.")
            return

        mode_text = {
            "system": "Khởi động lại (Restart)",
            "recovery": "Vào TWRP Recovery",
            "bootloader": "Vào Fastboot Bootloader",
            "poweroff": "Tắt nguồn (Power Off)"
        }.get(mode, "system")

        confirm = QMessageBox.question(
            self, 
            "Xác nhận", 
            f"Bạn có chắc chắn muốn thực hiện hành động '{mode_text}' hàng loạt trên {len(device_ids)} thiết bị đã chọn?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.No:
            return

        self.log(f"Bắt đầu thực thi '{mode_text}' hàng loạt trên {len(device_ids)} thiết bị...")
        
        self.active_worker = ADBTaskWorker(
            self.adb, 
            "reboot_bulk", 
            {"device_ids": device_ids, "mode": mode}
        )
        self.active_worker.progress.connect(lambda pct, msg: self.log(msg))
        self.active_worker.finished.connect(self.on_farm_reboot_finished)
        self.active_worker.start()

    def on_farm_reboot_finished(self, success, msg):
        if success:
            self.log(f"🎯 Thực thi điều khiển nguồn hàng loạt hoàn tất!")
        else:
            self.log(f"❌ Có lỗi trong quá trình thực thi: {msg}")
        self.active_worker = None
        # Đợi 1.5 giây rồi quét lại trạng thái thiết bị
        QTimer.singleShot(1500, self.refresh_devices)

    def closeEvent(self, event):
        """Cleanup worker thread khi đóng ứng dụng (#5)."""
        self.refresh_timer.stop()
        if self.active_worker and self.active_worker.isRunning():
            self.active_worker.cancel()
            self.active_worker.wait(3000)  # Đợi tối đa 3 giây
        event.accept()

    def farm_connect_wifi(self):
        device_ids = self.get_checked_farm_devices()
        if not device_ids:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn tối thiểu 1 thiết bị để kết nối WiFi.")
            return

        ssid = self.txt_wifi_ssid.text().strip()
        password = self.txt_wifi_pass.text().strip()
        security = self.cbo_wifi_sec.currentText()

        if not ssid:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập tên WiFi (SSID).")
            return

        self.btn_connect_wifi.setEnabled(False)
        self.install_progress.setVisible(True)
        self.install_progress.setValue(0)

        self.log(f"Khởi động kết nối WiFi '{ssid}' hàng loạt lên {len(device_ids)} thiết bị...")

        self.active_worker = ADBTaskWorker(
            self.adb,
            "wifi_bulk",
            {
                "device_ids": device_ids,
                "ssid": ssid,
                "password": password,
                "security": security
            }
        )
        self.active_worker.progress.connect(self.on_task_progress)
        self.active_worker.finished.connect(self.on_wifi_bulk_finished)
        self.active_worker.start()

    def on_wifi_bulk_finished(self, success, msg):
        self.btn_connect_wifi.setEnabled(True)
        self.install_progress.setVisible(False)
        if success:
            QMessageBox.information(self, "Thành công", msg)
        else:
            QMessageBox.critical(self, "Lỗi kết nối", msg)
        self.active_worker = None

    def farm_change_language(self):
        device_ids = self.get_checked_farm_devices()
        if not device_ids:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn tối thiểu 1 thiết bị để đổi ngôn ngữ.")
            return

        index = self.cbo_language.currentIndex()
        locale = self.cbo_language.itemData(index)
        lang_text = self.cbo_language.currentText()

        if not locale:
            lang_map = {
                "Tiếng Việt (vi-VN)": "vi-VN",
                "English (en-US)": "en-US",
                "English (en-GB)": "en-GB",
                "简体中文 (zh-CN)": "zh-CN",
                "한국어 (ko-KR)": "ko-KR",
                "日本語 (ja-JP)": "ja-JP",
                "ภาษาไทย (th-TH)": "th-TH"
            }
            locale = lang_map.get(lang_text, "vi-VN")

        confirm = QMessageBox.question(
            self,
            "Xác nhận",
            f"Bạn có chắc chắn muốn đổi ngôn ngữ sang '{lang_text}' cho {len(device_ids)} thiết bị?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.No:
            return

        self.btn_change_lang.setEnabled(False)
        self.install_progress.setVisible(True)
        self.install_progress.setValue(0)

        self.log(f"Khởi động đổi ngôn ngữ sang '{lang_text}' hàng loạt trên {len(device_ids)} thiết bị...")

        self.active_worker = ADBTaskWorker(
            self.adb,
            "change_language_bulk",
            {
                "device_ids": device_ids,
                "locale": locale
            }
        )
        self.active_worker.progress.connect(self.on_task_progress)
        self.active_worker.finished.connect(self.on_change_language_finished)
        self.active_worker.start()

    def on_change_language_finished(self, success, msg):
        self.btn_change_lang.setEnabled(True)
        self.install_progress.setVisible(False)
        if success:
            QMessageBox.information(self, "Thành công", msg)
        else:
            QMessageBox.critical(self, "Lỗi đổi ngôn ngữ", msg)
        self.active_worker = None

    def farm_change_timezone(self):
        device_ids = self.get_checked_farm_devices()
        if not device_ids:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn tối thiểu 1 thiết bị để đổi múi giờ.")
            return

        index = self.cbo_timezone.currentIndex()
        timezone = self.cbo_timezone.itemData(index)
        tz_text = self.cbo_timezone.currentText()

        if not timezone:
            tz_map = {
                "Asia/Ho_Chi_Minh (GMT+7)": "Asia/Ho_Chi_Minh",
                "Asia/Singapore (GMT+8)": "Asia/Singapore",
                "Asia/Tokyo (GMT+9)": "Asia/Tokyo",
                "Asia/Seoul (GMT+9)": "Asia/Seoul",
                "Asia/Bangkok (GMT+7)": "Asia/Bangkok",
                "America/New_York (GMT-5)": "America/New_York",
                "America/Los_Angeles (GMT-8)": "America/Los_Angeles",
                "Europe/London (GMT+0)": "Europe/London"
            }
            timezone = tz_map.get(tz_text, "Asia/Ho_Chi_Minh")

        confirm = QMessageBox.question(
            self,
            "Xác nhận",
            f"Bạn có chắc chắn muốn đổi múi giờ sang '{tz_text}' cho {len(device_ids)} thiết bị?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.No:
            return

        self.btn_change_tz.setEnabled(False)
        self.install_progress.setVisible(True)
        self.install_progress.setValue(0)

        self.log(f"Khởi động cấu hình múi giờ sang '{tz_text}' hàng loạt trên {len(device_ids)} thiết bị...")

        self.active_worker = ADBTaskWorker(
            self.adb,
            "change_timezone_bulk",
            {
                "device_ids": device_ids,
                "timezone": timezone
            }
        )
        self.active_worker.progress.connect(self.on_task_progress)
        self.active_worker.finished.connect(self.on_change_timezone_finished)
        self.active_worker.start()

    def on_change_timezone_finished(self, success, msg):
        self.btn_change_tz.setEnabled(True)
        self.install_progress.setVisible(False)
        if success:
            QMessageBox.information(self, "Thành công", msg)
        else:
            QMessageBox.critical(self, "Lỗi cấu hình múi giờ", msg)
        self.active_worker = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AndroidToolkitApp()
    window.show()
    sys.exit(app.exec())
