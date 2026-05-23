import os
import sys
import time
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QGroupBox, QLineEdit, QComboBox, 
    QTableWidget, QTableWidgetItem, QProgressBar, QTextEdit, 
    QCheckBox, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QColor, QPixmap

from style import DARK_STYLE
from adb_wrapper import ADBWrapper, ADBTaskWorker
from ui_components import APKDragDropArea, APKListWidget

class AndroidToolkitApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Android Multi-Device Farm Controller Pro v1.2")
        self.resize(1150, 780)
        
        # Khởi tạo ADB Wrapper
        self.adb = ADBWrapper()
        self.adb.set_demo_mode(False) # Mặc định tắt Demo Mode để chạy thiết bị thật
        
        self.devices_list = []
        self.active_worker = None
        self.output_dir = os.path.join(os.path.expanduser("~"), "Documents", "AndroidToolkit")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Thiết lập giao diện chính
        self.init_ui()
        self.setStyleSheet(DARK_STYLE)
        
        # Bộ đếm thời gian tự động quét thiết bị sau mỗi 3 giây
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.auto_refresh_device)
        self.refresh_timer.start(3000)
        
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
        
        body_layout.addWidget(right_group, 5)
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

    def toggle_demo_mode(self, state):
        enabled = (state == Qt.CheckState.Checked.value or state == True)
        self.adb.set_demo_mode(enabled)
        mode_text = "Chế độ mô phỏng (Demo Mode)" if enabled else "Chế độ tương tác thực tế (ADB/Fastboot)"
        self.log(f"Đã chuyển sang: {mode_text}")
        self.refresh_devices()

    def auto_map_python(self):
        """Tự động ánh xạ Python hiện tại vào PATH hệ thống và tạo file run.bat"""
        import sys
        import winreg
        import ctypes
        
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
                
                # Phương án dự phòng bằng setx nếu lỗi Registry
                try:
                    import subprocess
                    for p in paths_to_add:
                        subprocess.run(f'setx PATH "%PATH%;{p}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

    def farm_arrange_windows(self):
        """Tự động xếp lưới toàn bộ cửa sổ Scrcpy đang mở bằng Windows API."""
        import ctypes
        
        # Danh sách lưu các HWND
        hwnds = []
        
        # Định nghĩa kiểu dữ liệu callback
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        
        def enum_windows_callback(hwnd, lParam):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                # 1. Lấy Class Name
                class_buff = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetClassNameW(hwnd, class_buff, 256)
                class_name = class_buff.value
                
                # 2. Lấy tiêu đề cửa sổ
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    
                    # Cửa sổ Scrcpy có class name là "SDL_app" và tiêu đề chứa "scrcpy" hoặc ID thiết bị
                    is_scrcpy_class = (class_name == "SDL_app")
                    is_scrcpy_title = "scrcpy" in title.lower() or any(dev["id"] in title for dev in self.devices_list)
                    
                    if is_scrcpy_class and is_scrcpy_title:
                        hwnds.append(hwnd)
            return True
            
        # Gọi EnumWindows
        ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)
        
        if not hwnds:
            self.log("Không tìm thấy cửa sổ Scrcpy nào đang hoạt động trên màn hình.")
            QMessageBox.information(self, "Thông tin", "Không tìm thấy cửa sổ Scrcpy nào đang hoạt động trên màn hình.")
            return

        self.log(f"Đã phát hiện {len(hwnds)} cửa sổ Scrcpy đang chạy. Bắt đầu xếp lưới...")

        # Lấy kích thước màn hình
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.geometry()
            screen_w = screen_geo.width()
            screen_h = screen_geo.height()
        else:
            screen_w, screen_h = 1920, 1080

        # Lấy kích thước cửa sổ đã chọn để định vị
        size_text = self.cbo_scrcpy_size.currentText()
        w, h = 320, 640
        if "Trung bình" in size_text:
            w, h = 320, 640
        elif "Nhỏ" in size_text:
            w, h = 240, 480
        elif "Lớn" in size_text:
            w, h = 400, 800

        start_x, start_y = 60, 60
        gap_x, gap_y = 15, 45
        curr_x, curr_y = start_x, start_y

        for hwnd in hwnds:
            # SetWindowPos(hWnd, hWndInsertAfter, X, Y, cx, cy, uFlags)
            # 0x0004 = SWP_NOZORDER (giữ nguyên thứ tự Z)
            # 0x0040 = SWP_SHOWWINDOW (hiển thị cửa sổ)
            
            # Đưa cửa sổ lên phía trên và định vị lại
            ctypes.windll.user32.SetWindowPos(hwnd, 0, curr_x, curr_y, w, h, 0x0004 | 0x0040)
            self.log(f"Đã di chuyển cửa sổ HWND {hwnd} đến vị trí: x={curr_x}, y={curr_y}")
            
            curr_x += w + gap_x
            if curr_x + w > screen_w - 100:
                curr_x = start_x
                curr_y += h + gap_y

        self.log("🎯 Đã sắp xếp xếp lưới thành công toàn bộ cửa sổ Scrcpy trên màn hình!")

    def on_apks_selected(self, paths):
        self.apk_list.add_apks(paths)
        self.log(f"Đã chọn {len(paths)} file APK để chuẩn bị cài đặt hàng loạt.")

    def farm_install_apks(self):
        device_ids = self.get_checked_farm_devices()
        if not device_ids:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng tích chọn tối thiểu 1 thiết bị để cài đặt.")
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AndroidToolkitApp()
    window.show()
    sys.exit(app.exec())
