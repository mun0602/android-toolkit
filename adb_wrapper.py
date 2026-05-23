import os
import subprocess
import shutil
import time
import re
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal

class ADBWrapper:
    def __init__(self, custom_path=None):
        self.custom_path = custom_path
        self.adb_bin = "adb"
        self.fastboot_bin = "fastboot"
        self.demo_mode = False
        
        # Danh sách thiết bị giả lập trong Demo Mode
        self.demo_devices = [
            {"id": "PX8P2026DEMO", "state": "device", "model": "Google Pixel 8 Pro [DEMO]", "type": "adb"},
            {"id": "XM14U2026DEMO", "state": "device", "model": "Xiaomi 14 Ultra [DEMO]", "type": "adb"},
            {"id": "SS24U2026DEMO", "state": "device", "model": "Samsung Galaxy S24 Ultra [DEMO]", "type": "adb"},
            {"id": "OP12U2026DEMO", "state": "device", "model": "OnePlus 12 [DEMO]", "type": "adb"},
            {"id": "ROG8P2026DEMO", "state": "device", "model": "Asus ROG Phone 8 Pro [DEMO]", "type": "adb"}
        ]
        
        self.update_bin_paths()

    def set_demo_mode(self, enabled):
        self.demo_mode = enabled

    def update_bin_paths(self):
        # 1. Ưu tiên tìm adb cục bộ trong thư mục scrcpy-bin đi kèm (biến ứng dụng thành Portable)
        local_dir = os.path.join(os.path.dirname(__file__), "scrcpy-bin")
        if os.path.exists(local_dir):
            adb_ext = ".exe" if os.name == "nt" else ""
            test_adb = os.path.join(local_dir, f"adb{adb_ext}")
            test_fb = os.path.join(local_dir, f"fastboot{adb_ext}")
            if os.path.exists(test_adb):
                self.adb_bin = test_adb
            if os.path.exists(test_fb):
                self.fastboot_bin = test_fb

        # 2. Nếu không tìm thấy cục bộ, kiểm tra custom_path hoặc tìm trong PATH hệ thống
        if self.adb_bin == "adb":
            if self.custom_path and os.path.isdir(self.custom_path):
                adb_ext = ".exe" if os.name == "nt" else ""
                test_adb = os.path.join(self.custom_path, f"adb{adb_ext}")
                test_fb = os.path.join(self.custom_path, f"fastboot{adb_ext}")
                if os.path.exists(test_adb):
                    self.adb_bin = test_adb
                if os.path.exists(test_fb):
                    self.fastboot_bin = test_fb
            else:
                # Tìm trong PATH
                adb_path = shutil.which("adb")
                fastboot_path = shutil.which("fastboot")
                if adb_path:
                    self.adb_bin = adb_path
                if fastboot_path:
                    self.fastboot_bin = fastboot_path

    def run_command(self, cmd_args, is_fastboot=False):
        """Chạy một lệnh hệ thống và trả về stdout, stderr, returncode."""
        if self.demo_mode:
            return "", "", 0

        binary = self.fastboot_bin if is_fastboot else self.adb_bin
        full_cmd = [binary] + cmd_args
        
        try:
            # Chạy ẩn cửa sổ console trên Windows
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0 # SW_HIDE

            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                text=True,
                encoding="utf-8",
                errors="ignore"
            )
            stdout, stderr = process.communicate()
            return stdout, stderr, process.returncode
        except Exception as e:
            return "", str(e), -1

    def check_dependencies(self):
        """Kiểm tra adb và fastboot có chạy được không."""
        if self.demo_mode:
            return True, True
        
        adb_ok = shutil.which(self.adb_bin) is not None or os.path.exists(self.adb_bin)
        fb_ok = shutil.which(self.fastboot_bin) is not None or os.path.exists(self.fastboot_bin)
        return adb_ok, fb_ok

    def get_devices(self):
        """Lấy danh sách thiết bị kết nối."""
        if self.demo_mode:
            # Trả về cả hai thiết bị giả lập trong Demo Mode
            return self.demo_devices

        devices = []
        # 1. Quét thiết bị ADB
        stdout, _, rc = self.run_command(["devices"])
        if rc == 0:
            lines = stdout.strip().split("\n")
            for line in lines[1:]: # bỏ dòng đầu "List of devices attached"
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    dev_id = parts[0]
                    state = parts[1] # 'device', 'recovery', 'unauthorized', 'sideload'
                    devices.append({"id": dev_id, "state": state, "type": "adb"})

        # 2. Quét thiết bị Fastboot
        stdout, _, rc = self.run_command(["devices"], is_fastboot=True)
        if rc == 0:
            lines = stdout.strip().split("\n")
            for line in lines:
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    dev_id = parts[0]
                    state = parts[1] # 'fastboot', 'fastbootd'
                    devices.append({"id": dev_id, "state": state, "type": "fastboot"})

        # Thêm thông tin Model cho thiết bị
        for dev in devices:
            if dev["type"] == "adb" and dev["state"] == "device":
                model_out, _, _ = self.run_command(["-s", dev["id"], "shell", "getprop", "ro.product.model"])
                dev["model"] = model_out.strip() or "Unknown Device"
            elif dev["type"] == "fastboot":
                dev["model"] = "Android Device (Fastboot Mode)"
            else:
                dev["model"] = f"Android Device ({dev['state']})"

        return devices

    def get_device_details(self, device_id):
        """Lấy thông tin chi tiết qua getprop (chỉ khả dụng trong chế độ device)."""
        if self.demo_mode:
            # Trả về thông tin khác nhau tùy thuộc vào thiết bị Demo được chọn
            brand_map = {
                "PX8P": ("Google", "Google Pixel 8 Pro [DEMO]", "14", "34", "85%", "arm64-v8a (Google Tensor G3)", "Unlocked [DEMO]"),
                "XM14": ("Xiaomi", "Xiaomi 14 Ultra [DEMO]", "13", "33", "92%", "arm64-v8a (Snapdragon 8 Gen 3)", "Locked [DEMO]"),
                "SS24": ("Samsung", "Samsung Galaxy S24 Ultra [DEMO]", "14", "34", "78%", "arm64-v8a (Snapdragon 8 Gen 3)", "Locked [DEMO]"),
                "OP12": ("OnePlus", "OnePlus 12 [DEMO]", "14", "34", "65%", "arm64-v8a (Snapdragon 8 Gen 3)", "Unlocked [DEMO]"),
                "ROG8": ("Asus", "Asus ROG Phone 8 Pro [DEMO]", "14", "34", "99%", "arm64-v8a (Snapdragon 8 Gen 3)", "Unlocked [DEMO]")
            }
            prefix = device_id[:4]
            if prefix in brand_map:
                brand, model, release, sdk, battery, cpu, bl = brand_map[prefix]
                return {
                    "Brand": brand,
                    "Model": model,
                    "Android Version": release,
                    "SDK Level": sdk,
                    "Battery Level": battery,
                    "CPU Architecture": cpu,
                    "Bootloader Status": bl,
                    "Serial Number": device_id
                }
            return {
                "Brand": "Android",
                "Model": "Generic Device [DEMO]",
                "Android Version": "14",
                "SDK Level": "34",
                "Battery Level": "50%",
                "CPU Architecture": "arm64-v8a",
                "Bootloader Status": "Locked [DEMO]",
                "Serial Number": device_id
            }

        details = {}
        props = {
            "Brand": "ro.product.brand",
            "Model": "ro.product.model",
            "Android Version": "ro.build.version.release",
            "SDK Level": "ro.build.version.sdk",
            "CPU Architecture": "ro.product.cpu.abi",
            "Serial Number": "ro.serialno"
        }
        
        for label, prop in props.items():
            stdout, _, _ = self.run_command(["-s", device_id, "shell", "getprop", prop])
            details[label] = stdout.strip().capitalize() or "Unknown"

        # Lấy mức pin
        bat_out, _, _ = self.run_command(["-s", device_id, "shell", "dumpsys", "battery"])
        bat_match = re.search(r"level:\s*(\d+)", bat_out)
        details["Battery Level"] = f"{bat_match.group(1)}%" if bat_match else "Unknown"

        # Kiểm tra trạng thái Bootloader
        bl_out, _, _ = self.run_command(["-s", device_id, "shell", "getprop", "ro.boot.flash.locked"])
        if bl_out.strip() == "0":
            details["Bootloader Status"] = "Unlocked"
        elif bl_out.strip() == "1":
            details["Bootloader Status"] = "Locked"
        else:
            details["Bootloader Status"] = "Unknown"

        return details

    def reboot(self, device_id, mode, is_fastboot=False):
        """Khởi động lại thiết bị."""
        if self.demo_mode:
            # Tìm thiết bị demo tương ứng và cập nhật trạng thái giả lập của nó
            for dev in self.demo_devices:
                if dev["id"] == device_id:
                    if mode == "bootloader":
                        dev["state"] = "fastboot"
                        dev["type"] = "fastboot"
                        dev["model"] = f"{dev['model'].split(' [')[0]} (Fastboot Mode) [DEMO]"
                    elif mode == "recovery":
                        dev["state"] = "recovery"
                        dev["type"] = "adb"
                        dev["model"] = f"{dev['model'].split(' [')[0]} (Recovery Mode) [DEMO]"
                    elif mode == "system":
                        dev["state"] = "device"
                        dev["type"] = "adb"
                        # Reset model name
                        clean_name = dev['model'].split(' (')[0].split(' [')[0]
                        dev["model"] = f"{clean_name} [DEMO]"
                    elif mode == "poweroff":
                        dev["state"] = "offline"
                        dev["type"] = "adb"
                        dev["model"] = f"{dev['model'].split(' [')[0]} (Offline) [DEMO]"
                    break
            return "Khởi động lại thành công (Chế độ mô phỏng)", 0

        if is_fastboot:
            if mode == "system" or mode == "reboot":
                stdout, stderr, rc = self.run_command(["reboot"], is_fastboot=True)
            elif mode == "recovery":
                stdout, stderr, rc = self.run_command(["reboot-recovery"], is_fastboot=True)
            elif mode == "bootloader":
                stdout, stderr, rc = self.run_command(["reboot-bootloader"], is_fastboot=True)
            else:
                return "Lệnh fastboot reboot không hỗ trợ chế độ này", -1
            return stdout or stderr, rc

        # Chế độ ADB
        if mode == "system":
            args = ["-s", device_id, "reboot"]
        elif mode == "bootloader":
            args = ["-s", device_id, "reboot", "bootloader"]
        elif mode == "recovery":
            args = ["-s", device_id, "reboot", "recovery"]
        elif mode == "edl":
            args = ["-s", device_id, "reboot", "edl"]
        elif mode == "poweroff":
            args = ["-s", device_id, "shell", "reboot", "-p"]
        elif mode == "soft":
            args = ["-s", device_id, "shell", "setprop", "ctl.restart", "zygote"]
        else:
            return "Chế độ không hợp lệ", -1

        stdout, stderr, rc = self.run_command(args)
        return stdout or stderr or "Lệnh đã được gửi đi.", rc

    def launch_scrcpy(self, device_id, x=None, y=None, w=None, h=None):
        """Khởi chạy Scrcpy để mirror màn hình thiết bị (hỗ trợ vị trí và kích cỡ cửa sổ)."""
        if self.demo_mode:
            coord_str = f" với vị trí ({x}, {y}) và kích thước {w}x{h}" if x is not None else ""
            return f"Đang mở cửa sổ Mirror (Chế độ Demo){coord_str}...", 0

        # Kiểm tra xem có scrcpy.exe ở thư mục cục bộ dự án không (ưu tiên hàng đầu)
        local_scrcpy = os.path.join(os.path.dirname(__file__), "scrcpy-bin", "scrcpy.exe")
        if os.path.exists(local_scrcpy):
            scrcpy_bin = local_scrcpy
        else:
            # Tìm scrcpy trong PATH hoặc vị trí tùy chỉnh
            scrcpy_bin = shutil.which("scrcpy") or "scrcpy"
            
            # Nếu có custom_path và có scrcpy.exe trong đó
            if self.custom_path and os.path.isdir(self.custom_path):
                test_scrcpy = os.path.join(self.custom_path, "scrcpy.exe")
                if os.path.exists(test_scrcpy):
                    scrcpy_bin = test_scrcpy

        # Xây dựng các đối số lệnh
        args = [scrcpy_bin, "-s", device_id, f"--window-title=Scrcpy - {device_id}"]
        
        # Tích hợp các tham số tối ưu hóa hiệu năng cao từ Git Scrcpy để chạy nhiều thiết bị mượt mà không bị đơ
        args.append("--no-audio")          # Tắt truyền âm thanh (giảm cực lớn tải CPU & băng thông USB)
        args.append("--max-fps=30")        # Giới hạn 30 FPS (tiết kiệm 50% tải xử lý hình ảnh của GPU)
        args.append("--max-size=1024")     # Giới hạn độ phân giải luồng video về tối đa 1024px (giải mã cực nhẹ)
        args.append("--video-bit-rate=2M") # Giới hạn bitrate 2Mbps (tránh nghẽn băng thông Hub USB khi chạy farm)
        args.append("--video-codec=h264")  # Bộ codec H.264 ổn định và giải mã phần cứng tương thích tốt nhất
        
        # Bổ sung các tùy chọn vị trí và kích thước nếu có
        if x is not None:
            args.append(f"--window-x={x}")
        if y is not None:
            args.append(f"--window-y={y}")
        if w is not None:
            args.append(f"--window-width={w}")
        if h is not None:
            args.append(f"--window-height={h}")

        try:
            # Khởi chạy scrcpy độc lập dưới nền (không chặn luồng chính)
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Đã gửi yêu cầu mở màn hình gương Scrcpy cho thiết bị {device_id}.", 0
        except Exception as e:
            return f"Lỗi khởi chạy Scrcpy: {str(e)}. Hãy chắc chắn Scrcpy đã được cài đặt.", -1


class ADBTaskWorker(QThread):
    """Lớp xử lý luồng con để chạy các tác vụ ADB/Fastboot nặng không bị đơ UI."""
    progress = pyqtSignal(int, str) # phần trăm tiến độ, tin nhắn log
    finished = pyqtSignal(bool, str) # thành công/thất bại, tin nhắn kết quả

    def __init__(self, wrapper: ADBWrapper, task_type: str, args: dict):
        super().__init__()
        self.wrapper = wrapper
        self.task_type = task_type
        self.args = args
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if self.task_type == "install_apk":
                self.run_install_apk()
            elif self.task_type == "install_apk_bulk":
                self.run_install_apk_bulk()
            elif self.task_type == "uninstall_app_bulk":
                self.run_uninstall_app_bulk()
            elif self.task_type == "shell_command_bulk":
                self.run_shell_command_bulk()
            elif self.task_type == "reboot_bulk":
                self.run_reboot_bulk()
            elif self.task_type == "screenshot_bulk":
                self.run_screenshot_bulk()
            elif self.task_type == "flash_img":
                self.run_flash_img()
            elif self.task_type == "sideload":
                self.run_sideload()
            elif self.task_type == "extract_apk":
                self.run_extract_apk()
            else:
                self.finished.emit(False, "Tác vụ không xác định.")
        except Exception as e:
            self.finished.emit(False, f"Lỗi tác vụ: {str(e)}")

    def run_install_apk(self):
        device_id = self.args.get("device_id")
        apk_paths = self.args.get("apk_paths", [])
        opts = self.args.get("options", [])

        if not apk_paths:
            self.finished.emit(False, "Không có file APK nào được chọn.")
            return

        total = len(apk_paths)
        for idx, apk in enumerate(apk_paths):
            if self._is_cancelled:
                self.finished.emit(False, "Tác vụ đã bị hủy bỏ bởi người dùng.")
                return

            filename = os.path.basename(apk)
            self.progress.emit(int((idx / total) * 100), f"[{device_id}] Đang cài đặt ({idx+1}/{total}): {filename}...")

            if self.wrapper.demo_mode:
                for p in range(10, 101, 30):
                    time.sleep(0.4)
                    self.progress.emit(int(((idx + (p/100.0)) / total) * 100), f"[{device_id}] Đang đẩy file {filename} ({p}%)...")
                time.sleep(0.2)
                continue

            cmd = ["-s", device_id, "install"] + opts + [apk]
            stdout, stderr, rc = self.wrapper.run_command(cmd)
            
            if rc != 0:
                self.finished.emit(False, f"Cài đặt thất bại tệp {filename} trên {device_id}: {stderr or stdout}")
                return

        self.progress.emit(100, f"[{device_id}] Tất cả file APK đã được cài đặt thành công!")
        self.finished.emit(True, f"Cài đặt hoàn tất trên thiết bị {device_id}!")

    def run_flash_img(self):
        device_id = self.args.get("device_id")
        partition = self.args.get("partition")
        img_path = self.args.get("img_path")
        boot_only = self.args.get("boot_only", False)

        if not img_path or not os.path.exists(img_path):
            self.finished.emit(False, "Tệp Image không tồn tại hoặc chưa chọn.")
            return

        filename = os.path.basename(img_path)
        
        if boot_only:
            self.progress.emit(20, f"[{device_id}] Đang tải và boot trực tiếp: {filename}...")
            if self.wrapper.demo_mode:
                time.sleep(2)
                # Đổi trạng thái thiết bị demo này thành recovery
                for dev in self.wrapper.demo_devices:
                    if dev["id"] == device_id:
                        dev["state"] = "recovery"
                        dev["type"] = "adb"
                        dev["model"] = f"{dev['model'].split(' (')[0].split(' [')[0]} (Recovery Mode) [DEMO]"
                        break
                self.finished.emit(True, f"Đã boot trực tiếp {filename} thành công trên {device_id}! Thiết bị hiện đang ở Recovery mode.")
                return
            
            stdout, stderr, rc = self.wrapper.run_command(["-s", device_id, "boot", img_path], is_fastboot=True)
        else:
            self.progress.emit(20, f"[{device_id}] Đang xóa và flash phân vùng {partition} bằng tệp {filename}...")
            if self.wrapper.demo_mode:
                time.sleep(1)
                self.progress.emit(60, "Đang ghi phân vùng (writing)...")
                time.sleep(1)
                self.finished.emit(True, f"Đã nạp thành công {filename} vào phân vùng {partition} của thiết bị {device_id}!")
                return
            
            stdout, stderr, rc = self.wrapper.run_command(["-s", device_id, "flash", partition, img_path], is_fastboot=True)

        if rc == 0:
            self.finished.emit(True, stdout or f"Nạp tệp {filename} thành công trên {device_id}!")
        else:
            self.finished.emit(False, f"Flash thất bại: {stderr or stdout}")

    def run_sideload(self):
        device_id = self.args.get("device_id")
        zip_path = self.args.get("zip_path")

        if not zip_path or not os.path.exists(zip_path):
            self.finished.emit(False, "Tệp ZIP không tồn tại.")
            return

        filename = os.path.basename(zip_path)
        self.progress.emit(10, f"[{device_id}] Bắt đầu Sideload tệp: {filename}...")

        if self.wrapper.demo_mode:
            for p in range(20, 101, 20):
                time.sleep(0.5)
                self.progress.emit(p, f"Đang gửi {filename} ({p}%)...")
            self.finished.emit(True, f"Đã sideload thành công tệp {filename} trên {device_id}!")
            return

        cmd = ["-s", device_id, "sideload", zip_path]
        stdout, stderr, rc = self.wrapper.run_command(cmd)
        if rc == 0:
            self.finished.emit(True, f"Đã hoàn thành Sideload {filename} trên {device_id}!")
        else:
            self.finished.emit(False, f"Sideload thất bại: {stderr or stdout}")

    def run_extract_apk(self):
        device_id = self.args.get("device_id")
        package_name = self.args.get("package_name")
        dest_dir = self.args.get("dest_dir")

        self.progress.emit(10, f"[{device_id}] Đang tìm đường dẫn APK của {package_name}...")
        
        if self.wrapper.demo_mode:
            time.sleep(1.5)
            self.finished.emit(True, f"Đã trích xuất thành công {package_name} từ {device_id} vào thư mục:\n{dest_dir}!")
            return

        stdout, stderr, rc = self.wrapper.run_command(["-s", device_id, "shell", "pm", "path", package_name])
        if rc != 0 or not stdout.strip():
            self.finished.emit(False, f"Không tìm thấy ứng dụng hoặc lỗi: {stderr or stdout}")
            return

        paths = [line.replace("package:", "").strip() for line in stdout.strip().split("\n") if line.strip()]
        
        total = len(paths)
        for idx, remote_path in enumerate(paths):
            self.progress.emit(int(((idx+0.2)/total)*100), f"Đang copy file {idx+1}/{total} về máy tính...")
            local_name = f"{package_name}_{idx}.apk" if total > 1 else f"{package_name}.apk"
            local_path = os.path.join(dest_dir, local_name)
            
            p_out, p_err, p_rc = self.wrapper.run_command(["-s", device_id, "pull", remote_path, local_path])
            if p_rc != 0:
                self.finished.emit(False, f"Lỗi khi tải file từ thiết bị: {p_err or p_out}")
                return

        self.finished.emit(True, f"Đã trích xuất thành công {total} file APK của {package_name} vào thư mục:\n{dest_dir}")

    def run_install_apk_bulk(self):
        device_ids = self.args.get("device_ids", [])
        apk_paths = self.args.get("apk_paths", [])
        opts = self.args.get("options", [])

        if not device_ids:
            self.finished.emit(False, "Không có thiết bị nào được chọn.")
            return

        if not apk_paths:
            self.finished.emit(False, "Không có file APK nào được chọn.")
            return

        total_devices = len(device_ids)
        total_apks = len(apk_paths)
        total_steps = total_devices * total_apks
        step = 0

        for dev_idx, device_id in enumerate(device_ids):
            for apk_idx, apk in enumerate(apk_paths):
                if self._is_cancelled:
                    self.finished.emit(False, "Tác vụ cài đặt hàng loạt đã bị hủy bởi người dùng.")
                    return

                filename = os.path.basename(apk)
                pct = int((step / total_steps) * 100)
                self.progress.emit(pct, f"[{device_id}] Đang cài đặt ({apk_idx+1}/{total_apks}): {filename}...")

                if self.wrapper.demo_mode:
                    for p in range(20, 101, 40):
                        time.sleep(0.3)
                        self.progress.emit(int(((step + (p/100.0)) / total_steps) * 100), f"[{device_id}] Đẩy file {filename} ({p}%)...")
                    step += 1
                    continue

                cmd = ["-s", device_id, "install"] + opts + [apk]
                stdout, stderr, rc = self.wrapper.run_command(cmd)
                
                if rc != 0:
                    self.progress.emit(pct, f"❌ Cài đặt thất bại tệp {filename} trên {device_id}: {stderr or stdout}")
                else:
                    self.progress.emit(pct, f"✅ Cài đặt thành công {filename} trên {device_id}")
                
                step += 1

        self.progress.emit(100, "Cài đặt hàng loạt hoàn tất trên tất cả thiết bị đã chọn!")
        self.finished.emit(True, "Đã hoàn thành cài đặt hàng loạt!")

    def run_uninstall_app_bulk(self):
        device_ids = self.args.get("device_ids", [])
        package_name = self.args.get("package_name")

        if not device_ids:
            self.finished.emit(False, "Không có thiết bị nào được chọn.")
            return
        if not package_name:
            self.finished.emit(False, "Tên gói ứng dụng trống.")
            return

        total = len(device_ids)
        for idx, device_id in enumerate(device_ids):
            if self._is_cancelled:
                self.finished.emit(False, "Bị hủy.")
                return

            pct = int((idx / total) * 100)
            self.progress.emit(pct, f"[{device_id}] Đang gỡ cài đặt {package_name}...")

            if self.wrapper.demo_mode:
                time.sleep(0.5)
                self.progress.emit(pct, f"✅ Đã gỡ thành công {package_name} trên {device_id}")
                continue

            cmd = ["-s", device_id, "uninstall", package_name]
            stdout, stderr, rc = self.wrapper.run_command(cmd)
            if rc != 0:
                self.progress.emit(pct, f"❌ Thất bại trên {device_id}: {stderr or stdout}")
            else:
                self.progress.emit(pct, f"✅ Thành công trên {device_id}")

        self.progress.emit(100, "Đã hoàn tất gỡ cài đặt hàng loạt!")
        self.finished.emit(True, "Gỡ cài đặt hàng loạt hoàn tất!")

    def run_shell_command_bulk(self):
        device_ids = self.args.get("device_ids", [])
        shell_cmd = self.args.get("shell_command")

        if not device_ids:
            self.finished.emit(False, "Không có thiết bị nào được chọn.")
            return
        if not shell_cmd:
            self.finished.emit(False, "Lệnh shell trống.")
            return

        total = len(device_ids)
        for idx, device_id in enumerate(device_ids):
            if self._is_cancelled:
                self.finished.emit(False, "Bị hủy.")
                return

            pct = int((idx / total) * 100)
            self.progress.emit(pct, f"[{device_id}] Đang thực thi: adb shell {shell_cmd}...")

            if self.wrapper.demo_mode:
                time.sleep(0.4)
                self.progress.emit(pct, f"[{device_id}] Trả về: (Chế độ Demo) Lệnh đã chạy thành công.")
                continue

            cmd = ["-s", device_id, "shell"] + shell_cmd.split()
            stdout, stderr, rc = self.wrapper.run_command(cmd)
            
            log_msg = f"[{device_id}] Kết quả:\n"
            if stdout.strip():
                log_msg += f"stdout: {stdout.strip()}\n"
            if stderr.strip():
                log_msg += f"stderr: {stderr.strip()}\n"
            log_msg += f"Exit code: {rc}"
            
            self.progress.emit(pct, log_msg)

        self.progress.emit(100, "Đã hoàn tất thực thi lệnh hàng loạt!")
        self.finished.emit(True, "Thực thi lệnh hàng loạt hoàn tất!")

    def run_reboot_bulk(self):
        device_ids = self.args.get("device_ids", [])
        mode = self.args.get("mode", "system")

        if not device_ids:
            self.finished.emit(False, "Không có thiết bị nào được chọn.")
            return

        total = len(device_ids)
        for idx, device_id in enumerate(device_ids):
            if self._is_cancelled:
                self.finished.emit(False, "Bị hủy.")
                return

            pct = int((idx / total) * 100)
            self.progress.emit(pct, f"[{device_id}] Đang khởi động lại ở chế độ {mode}...")

            res, rc = self.wrapper.reboot(device_id, mode)
            self.progress.emit(pct, f"[{device_id}] {res}")

        self.progress.emit(100, "Khởi động lại hàng loạt hoàn tất!")
        self.finished.emit(True, "Đã hoàn thành khởi động lại hàng loạt!")

    def run_screenshot_bulk(self):
        device_ids = self.args.get("device_ids", [])
        dest_dir = self.args.get("dest_dir")

        if not device_ids:
            self.finished.emit(False, "Không có thiết bị nào được chọn.")
            return

        total = len(device_ids)
        screenshot_paths = {}
        
        for idx, device_id in enumerate(device_ids):
            if self._is_cancelled:
                self.finished.emit(False, "Bị hủy.")
                return

            pct = int((idx / total) * 100)
            self.progress.emit(pct, f"[{device_id}] Đang chụp màn hình...")

            filename = f"screenshot_{device_id}_{int(time.time())}.png"
            local_path = os.path.join(dest_dir, filename)

            if self.wrapper.demo_mode:
                time.sleep(0.5)
                screenshot_paths[device_id] = "demo"
                self.progress.emit(pct, f"✅ Đã chụp thành công màn hình {device_id} (Mô phỏng)")
                continue

            c1_out, c1_err, c1_rc = self.wrapper.run_command(["-s", device_id, "shell", "screencap", "-p", "/sdcard/screen.png"])
            if c1_rc != 0:
                self.progress.emit(pct, f"❌ Thất bại trên {device_id} khi screencap: {c1_err or c1_out}")
                continue

            c2_out, c2_err, c2_rc = self.wrapper.run_command(["-s", device_id, "pull", "/sdcard/screen.png", local_path])
            if c2_rc != 0:
                self.progress.emit(pct, f"❌ Thất bại trên {device_id} khi pull file: {c2_err or c2_out}")
                continue

            self.wrapper.run_command(["-s", device_id, "shell", "rm", "/sdcard/screen.png"])

            screenshot_paths[device_id] = local_path
            self.progress.emit(pct, f"✅ Đã chụp và tải về thành công: {filename}")

        import json
        self.finished.emit(True, json.dumps(screenshot_paths))
