import os
import sys
import threading
import time
import urllib.parse

import cv2
import numpy as np

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


load_dotenv()

USER = os.getenv("CAMERA_USER")
PASS = os.getenv("CAMERA_PASS")
IP_ADDR = os.getenv("CAMERA_IP")

if not USER or not PASS or not IP_ADDR:
    print("HATA: .env dosyasi bulunamadi veya eksik.")
    sys.exit()

safe_pass = urllib.parse.quote(PASS)
URL = f"rtsp://{USER}:{safe_pass}@{IP_ADDR}/axis-media/media.amp?resolution=1280x720"


class CameraStream:
    def __init__(self, url):
        self.cap = cv2.VideoCapture(url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.started = False
        self.read_lock = threading.Lock()
        self.ret = False
        self.frame = None

    def start(self):
        if not self.cap.isOpened():
            return False
        self.started = True
        threading.Thread(target=self.update, daemon=True).start()
        return True

    def update(self):
        while self.started:
            ret, frame = self.cap.read()
            if ret:
                with self.read_lock:
                    self.ret = ret
                    self.frame = frame
            else:
                time.sleep(0.01)

    def read(self):
        with self.read_lock:
            return self.ret, self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.started = False
        if self.cap.isOpened():
            self.cap.release()


class CubukSayimSistemi(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Zeynep - Cubuk Sayim Dashboard v32.0")
        self.setGeometry(50, 50, 1400, 800)
        self.setStyleSheet("background-color: #f4f6f9;")

        self.sayilan_adet = 0
        self.tracked_objects = {}
        self.next_obj_id = 0
        self.cizgi_x = 450
        self.frame_index = 0
        self.warmup_until_frame = 45
        self.prev_roi_gray = None
        self.recent_count_events = []
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        self.track_timeout_frames = 10
        self.count_band_half_width = 34
        self.vertical_match_limit = 28
        self.count_cooldown_seconds = 0.85
        self.max_vertical_speed = 6.5
        self.min_horizontal_speed = 1.2

        self.ebat_ayarlari = {
            "8 mm": {
                "kernel": 3,
                "min_a": 10,
                "max_a": 2200,
                "dist": 80,
                "limit_w": 16,
                "limit_h": 12,
                "motion_threshold": 16,
                "bright_percentile": 76,
                "peak_threshold": 158,
            },
            "10 mm": {
                "kernel": 3,
                "min_a": 12,
                "max_a": 2600,
                "dist": 90,
                "limit_w": 18,
                "limit_h": 14,
                "motion_threshold": 17,
                "bright_percentile": 75,
                "peak_threshold": 160,
            },
            "12 mm": {
                "kernel": 5,
                "min_a": 16,
                "max_a": 3200,
                "dist": 95,
                "limit_w": 20,
                "limit_h": 16,
                "motion_threshold": 18,
                "bright_percentile": 74,
                "peak_threshold": 162,
            },
            "14 mm": {
                "kernel": 5,
                "min_a": 20,
                "max_a": 3800,
                "dist": 100,
                "limit_w": 22,
                "limit_h": 18,
                "motion_threshold": 19,
                "bright_percentile": 73,
                "peak_threshold": 164,
            },
            "16 mm": {
                "kernel": 7,
                "min_a": 24,
                "max_a": 4600,
                "dist": 110,
                "limit_w": 24,
                "limit_h": 18,
                "motion_threshold": 20,
                "bright_percentile": 72,
                "peak_threshold": 166,
            },
            "20 mm": {
                "kernel": 9,
                "min_a": 28,
                "max_a": 5600,
                "dist": 120,
                "limit_w": 28,
                "limit_h": 20,
                "motion_threshold": 21,
                "bright_percentile": 71,
                "peak_threshold": 168,
            },
        }
        self.aktif_ayar = self.ebat_ayarlari["10 mm"]

        self.init_ui()
        self.vs = CameraStream(URL)
        self.vs.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.main_loop)
        self.timer.start(30)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        left_panel = QVBoxLayout()
        left_panel.setAlignment(Qt.AlignmentFlag.AlignTop)

        label_style = (
            "font-weight: bold; font-size: 16px; color: #2c3e50; margin-bottom: 5px;"
        )
        input_style = (
            "background-color: white; border: 2px solid #bdc3c7; border-radius: 5px; "
            "padding: 10px; font-size: 18px; color: black;"
        )

        self.lbl_ebat = QLabel("Ebat Sec")
        self.lbl_ebat.setStyleSheet(label_style)
        self.combo_ebat = QComboBox()
        self.combo_ebat.addItems(["8 mm", "10 mm", "12 mm", "14 mm", "16 mm", "20 mm"])
        self.combo_ebat.setStyleSheet(input_style)
        self.combo_ebat.setCurrentText("10 mm")
        self.combo_ebat.currentTextChanged.connect(self.ebat_degistir)
        left_panel.addWidget(self.lbl_ebat)
        left_panel.addWidget(self.combo_ebat)

        self.lbl_ebat_uyari = QLabel("Dikkat: Yanlis ebat secimi sayimi bozabilir.")
        self.lbl_ebat_uyari.setStyleSheet(
            "color: #e74c3c; font-size: 13px; font-weight: bold; margin-top: -5px;"
        )
        left_panel.addWidget(self.lbl_ebat_uyari)
        left_panel.addSpacing(20)

        self.lbl_hedef = QLabel("Hedef (Adet)")
        self.lbl_hedef.setStyleSheet(label_style)
        self.input_hedef = QLineEdit()
        self.input_hedef.setPlaceholderText("Orn: 500")
        self.input_hedef.setStyleSheet(input_style)
        self.input_hedef.textChanged.connect(self.hedef_kontrol)
        left_panel.addWidget(self.lbl_hedef)
        left_panel.addWidget(self.input_hedef)
        left_panel.addSpacing(40)

        self.lbl_sayilan_baslik = QLabel("SAYILAN")
        self.lbl_sayilan_baslik.setStyleSheet(label_style)

        self.label_sayac = QLabel("0")
        self.sayac_normal_stil = (
            "background-color: #27ae60; border: 3px solid #2ecc71; border-radius: 10px; "
            "padding: 20px; font-size: 70px; font-weight: bold; color: white;"
        )
        self.sayac_hedef_stil = (
            "background-color: #f1c40f; border: 4px solid #f39c12; border-radius: 10px; "
            "padding: 20px; font-size: 70px; font-weight: bold; color: #2c3e50;"
        )
        self.label_sayac.setStyleSheet(self.sayac_normal_stil)
        self.label_sayac.setAlignment(Qt.AlignmentFlag.AlignCenter)

        left_panel.addWidget(self.lbl_sayilan_baslik)
        left_panel.addWidget(self.label_sayac)
        left_panel.addSpacing(40)

        btn_reset = QPushButton("SIFIRLA")
        btn_reset.clicked.connect(self.reset_count)
        btn_reset.setStyleSheet(
            "padding: 15px; background-color: #e74c3c; color: white; "
            "font-weight: bold; font-size: 18px; border-radius: 5px;"
        )
        left_panel.addWidget(btn_reset)

        self.live_view = QLabel()
        self.live_view.setMinimumSize(960, 540)
        self.live_view.setStyleSheet("border: 5px solid #34495e; background-color: black;")
        self.live_view.mousePressEvent = self.set_line_position

        main_layout.addLayout(left_panel, stretch=1)
        main_layout.addWidget(self.live_view, stretch=4)

    def ebat_degistir(self, secilen_ebat):
        self.aktif_ayar = self.ebat_ayarlari[secilen_ebat]
        self._reset_analysis_state(extra_warmup=20)

    def set_line_position(self, event):
        self.cizgi_x = int(event.pos().x() * (1280 / self.live_view.width()))
        self._reset_analysis_state(extra_warmup=20)

    def reset_count(self):
        self.sayilan_adet = 0
        self.label_sayac.setText("0")
        self.label_sayac.setStyleSheet(self.sayac_normal_stil)
        self._reset_analysis_state(extra_warmup=35)

    def _reset_analysis_state(self, extra_warmup):
        self.tracked_objects = {}
        self.recent_count_events = []
        self.prev_roi_gray = None
        self.next_obj_id = 0
        self.warmup_until_frame = self.frame_index + extra_warmup

    def hedef_kontrol(self):
        hedef_metin = self.input_hedef.text()
        if hedef_metin.isdigit():
            hedef_sayi = int(hedef_metin)
            if hedef_sayi > 0 and self.sayilan_adet >= hedef_sayi:
                self.label_sayac.setStyleSheet(self.sayac_hedef_stil)
            else:
                self.label_sayac.setStyleSheet(self.sayac_normal_stil)

    def closeEvent(self, event):
        self.timer.stop()
        self.vs.stop()
        super().closeEvent(event)

    def _smooth_profile(self, profile):
        if len(profile) < 5:
            return profile
        kernel = np.array([1, 2, 3, 2, 1], dtype=np.float32)
        kernel /= kernel.sum()
        return np.convolve(profile, kernel, mode="same")

    def _get_roi_bounds(self, frame_shape):
        h, w = frame_shape[:2]
        roi_y1 = int(h * 0.22)
        roi_y2 = int(h * 0.41)
        roi_x1 = max(0, self.cizgi_x - 260)
        roi_x2 = min(w, self.cizgi_x + 210)
        return roi_x1, roi_x2, roi_y1, roi_y2

    def _normalize_roi(self, roi):
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = self.clahe.apply(gray)
        return cv2.GaussianBlur(gray, (5, 5), 0)

    def _build_motion_mask(self, roi_gray):
        if self.prev_roi_gray is None or self.prev_roi_gray.shape != roi_gray.shape:
            self.prev_roi_gray = roi_gray.copy()
            return np.zeros_like(roi_gray)

        diff = roi_gray.astype(np.int16) - self.prev_roi_gray.astype(np.int16)
        diff -= int(np.median(diff))
        diff = np.abs(diff).clip(0, 255).astype(np.uint8)

        _, motion_mask = cv2.threshold(
            diff, self.aktif_ayar["motion_threshold"], 255, cv2.THRESH_BINARY
        )
        motion_mask = cv2.medianBlur(motion_mask, 5)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_OPEN, kernel)
        motion_mask = cv2.dilate(motion_mask, kernel, iterations=1)

        self.prev_roi_gray = roi_gray.copy()
        return motion_mask

    def _build_structure_mask(self, roi_gray):
        bright_floor = np.percentile(roi_gray, self.aktif_ayar["bright_percentile"])
        bright_floor = min(245, max(120, int(bright_floor)))
        _, bright_mask = cv2.threshold(roi_gray, bright_floor, 255, cv2.THRESH_BINARY)

        top_hat_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        top_hat = cv2.morphologyEx(roi_gray, cv2.MORPH_TOPHAT, top_hat_kernel)
        _, detail_mask = cv2.threshold(top_hat, 12, 255, cv2.THRESH_BINARY)

        structure_mask = cv2.bitwise_and(bright_mask, detail_mask)

        ignore_start = int(roi_gray.shape[0] * 0.72)
        structure_mask[ignore_start:, :] = 0
        return structure_mask

    def _extract_detections(self, frame, roi_x1, roi_x2, roi_y1, roi_y2):
        roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
        roi_gray = self._normalize_roi(roi)
        motion_mask = self._build_motion_mask(roi_gray)
        structure_mask = self._build_structure_mask(roi_gray)

        final_mask = cv2.bitwise_and(motion_mask, structure_mask)
        k_boyut = self.aktif_ayar["kernel"]
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_boyut, k_boyut))
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_OPEN, kernel)
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_CLOSE, kernel)
        final_mask = cv2.dilate(final_mask, kernel, iterations=1)

        contours, _ = cv2.findContours(
            final_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        detections = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (self.aktif_ayar["min_a"] < area < self.aktif_ayar["max_a"]):
                continue

            x_c, y_c, w_c, h_c = cv2.boundingRect(cnt)
            if w_c < 4 or h_c < 4:
                continue
            if h_c > max(26, self.aktif_ayar["limit_h"] * 2):
                continue

            aspect_ratio = float(w_c) / max(h_c, 1)
            if aspect_ratio > 2.8:
                continue

            roi_gray_local = roi_gray[y_c:y_c + h_c, x_c:x_c + w_c]
            if roi_gray_local.size == 0:
                continue

            if w_c > int(self.aktif_ayar["limit_w"] * 1.35):
                profile = np.mean(roi_gray_local, axis=0)
                profile = self._smooth_profile(profile)
                min_peak_gap = max(8, int(self.aktif_ayar["limit_w"] * 0.7))
                peak_floor = max(
                    self.aktif_ayar["peak_threshold"],
                    float(profile.mean() + profile.std() * 0.35),
                )

                peaks = []
                for i in range(1, len(profile) - 1):
                    center_val = profile[i]
                    if (
                        center_val >= profile[i - 1]
                        and center_val >= profile[i + 1]
                        and center_val >= peak_floor
                    ):
                        if not peaks or (i - peaks[-1]) > min_peak_gap:
                            peaks.append(i)
                        elif center_val > profile[peaks[-1]]:
                            peaks[-1] = i

                if len(peaks) > 1:
                    for peak_x in peaks:
                        detections.append(
                            {
                                "cx": x_c + peak_x + roi_x1,
                                "cy": y_c + (h_c // 2) + roi_y1,
                                "w": self.aktif_ayar["limit_w"],
                                "h": h_c,
                            }
                        )
                    continue

            detections.append(
                {
                    "cx": x_c + (w_c // 2) + roi_x1,
                    "cy": y_c + (h_c // 2) + roi_y1,
                    "w": w_c,
                    "h": h_c,
                }
            )

        detections.sort(key=lambda item: (item["cy"], item["cx"]))
        return detections, final_mask

    def _predict_position(self, data):
        gap = max(1, data["missing"] + 1)
        return data["cx"] + data["vx"] * gap, data["cy"] + data["vy"] * gap

    def _build_track(self, detection):
        return {
            "cx": detection["cx"],
            "cy": detection["cy"],
            "start_x": detection["cx"],
            "start_y": detection["cy"],
            "prev_x": detection["cx"],
            "prev_y": detection["cy"],
            "vx": 0.0,
            "vy": 0.0,
            "frames_seen": 1,
            "missing": 0,
            "counted": False,
            "min_x": detection["cx"],
            "max_x": detection["cx"],
            "w": detection["w"],
            "h": detection["h"],
        }

    def _update_track(self, data, detection):
        prev_x, prev_y = data["cx"], data["cy"]
        gap = max(1, data["missing"] + 1)
        inst_vx = (detection["cx"] - prev_x) / gap
        inst_vy = (detection["cy"] - prev_y) / gap

        if data["frames_seen"] == 1:
            vx, vy = inst_vx, inst_vy
        else:
            vx = 0.60 * data["vx"] + 0.40 * inst_vx
            vy = 0.60 * data["vy"] + 0.40 * inst_vy

        return {
            "cx": detection["cx"],
            "cy": detection["cy"],
            "start_x": data["start_x"],
            "start_y": data["start_y"],
            "prev_x": prev_x,
            "prev_y": prev_y,
            "vx": vx,
            "vy": vy,
            "frames_seen": data["frames_seen"] + 1,
            "missing": 0,
            "counted": data["counted"],
            "min_x": min(data["min_x"], detection["cx"]),
            "max_x": max(data["max_x"], detection["cx"]),
            "w": detection["w"],
            "h": detection["h"],
        }

    def _match_tracks(self, detections):
        available_tracks = {
            obj_id: data
            for obj_id, data in self.tracked_objects.items()
            if data["missing"] <= self.track_timeout_frames
        }
        new_tracks = {}
        candidates = []

        for det_index, detection in enumerate(detections):
            for obj_id, data in available_tracks.items():
                pred_x, pred_y = self._predict_position(data)
                dx = detection["cx"] - pred_x
                dy = detection["cy"] - pred_y
                adaptive_x_limit = max(
                    self.aktif_ayar["dist"],
                    abs(data["vx"]) * (data["missing"] + 2) + self.count_band_half_width,
                )
                adaptive_y_limit = max(
                    self.vertical_match_limit, detection["h"] * 1.2, data["h"] * 1.2
                )
                if abs(dx) <= adaptive_x_limit and abs(dy) <= adaptive_y_limit:
                    score = abs(dx) + abs(dy) * 2 + data["missing"] * 12
                    candidates.append((score, obj_id, det_index))

        matched_tracks = set()
        matched_detections = set()

        for _, obj_id, det_index in sorted(candidates, key=lambda item: item[0]):
            if obj_id in matched_tracks or det_index in matched_detections:
                continue
            updated = self._update_track(available_tracks[obj_id], detections[det_index])
            new_tracks[obj_id] = updated
            matched_tracks.add(obj_id)
            matched_detections.add(det_index)

        for obj_id, data in available_tracks.items():
            if obj_id in matched_tracks:
                continue
            if data["missing"] + 1 <= self.track_timeout_frames:
                stale_track = dict(data)
                stale_track["prev_x"] = data["cx"]
                stale_track["prev_y"] = data["cy"]
                stale_track["cx"], stale_track["cy"] = self._predict_position(data)
                stale_track["missing"] = data["missing"] + 1
                new_tracks[obj_id] = stale_track

        for det_index, detection in enumerate(detections):
            if det_index in matched_detections:
                continue
            new_tracks[self.next_obj_id] = self._build_track(detection)
            self.next_obj_id += 1

        self.tracked_objects = new_tracks

    def _prune_count_events(self):
        now = time.monotonic()
        self.recent_count_events = [
            event
            for event in self.recent_count_events
            if now - event["time"] <= self.count_cooldown_seconds
        ]

    def _can_register_count(self, track, direction):
        self._prune_count_events()
        min_lane_gap = max(7, self.aktif_ayar["limit_h"] // 2)
        for event in self.recent_count_events:
            if event["direction"] == direction and abs(event["cy"] - track["cy"]) <= min_lane_gap:
                return False
        return True

    def _register_count(self, track, direction):
        self.sayilan_adet += 1
        self.label_sayac.setText(str(self.sayilan_adet))
        self.hedef_kontrol()
        self.recent_count_events.append(
            {"time": time.monotonic(), "cy": track["cy"], "direction": direction}
        )

    def _count_if_needed(self):
        if self.frame_index < self.warmup_until_frame:
            return

        for data in self.tracked_objects.values():
            if data["counted"] or data["missing"] > 0:
                continue

            net_dx = data["cx"] - data["start_x"]
            avg_vx = net_dx / max(1, data["frames_seen"] - 1)
            crossed_line = (
                (data["prev_x"] <= self.cizgi_x < data["cx"])
                or (data["cx"] < self.cizgi_x <= data["prev_x"])
            )
            touched_both_sides = (
                data["min_x"] <= self.cizgi_x - self.count_band_half_width
                and data["max_x"] >= self.cizgi_x + self.count_band_half_width
            )

            direction = 1 if net_dx > 0 else -1
            start_side_ok = (
                data["start_x"] < self.cizgi_x - self.count_band_half_width
                if direction > 0
                else data["start_x"] > self.cizgi_x + self.count_band_half_width
            )
            end_side_ok = (
                data["cx"] > self.cizgi_x + 6
                if direction > 0
                else data["cx"] < self.cizgi_x - 6
            )

            enough_motion = abs(net_dx) >= max(40, self.aktif_ayar["limit_w"] * 2)
            stable_direction = abs(avg_vx) >= self.min_horizontal_speed and np.sign(avg_vx) == direction
            stable_vertical_motion = abs(data["vy"]) <= self.max_vertical_speed

            if (
                data["frames_seen"] >= 2
                and enough_motion
                and stable_direction
                and stable_vertical_motion
                and start_side_ok
                and end_side_ok
                and (crossed_line or touched_both_sides)
                and self._can_register_count(data, direction)
            ):
                data["counted"] = True
                self._register_count(data, direction)

    def main_loop(self):
        ret, frame = self.vs.read()
        if not ret or frame is None:
            return

        self.frame_index += 1
        h, w = frame.shape[:2]
        roi_x1, roi_x2, roi_y1, roi_y2 = self._get_roi_bounds(frame.shape)

        detections, final_mask = self._extract_detections(
            frame, roi_x1, roi_x2, roi_y1, roi_y2
        )
        self._match_tracks(detections)
        self._count_if_needed()

        cv2.rectangle(frame, (self.cizgi_x - self.count_band_half_width, 0),
                      (self.cizgi_x + self.count_band_half_width, h), (0, 255, 255), 2)
        cv2.line(frame, (self.cizgi_x, 0), (self.cizgi_x, h), (0, 0, 255), 3)
        cv2.rectangle(frame, (roi_x1, roi_y1), (roi_x2, roi_y2), (255, 255, 0), 1)

        for obj_id, data in self.tracked_objects.items():
            if data["missing"] > 1:
                continue

            cx, cy = int(data["cx"]), int(data["cy"])
            color = (255, 0, 0) if data["counted"] else (0, 255, 0)
            cv2.rectangle(frame, (cx - 10, cy - 10), (cx + 10, cy + 10), color, 2)
            cv2.putText(
                frame,
                f"ID {obj_id}",
                (cx - 18, cy - 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                color,
                1,
            )
            if data["counted"]:
                cv2.putText(
                    frame,
                    "SAYILDI",
                    (cx - 24, cy - 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.52,
                    (255, 0, 0),
                    2,
                )

        mask_bgr = cv2.cvtColor(final_mask, cv2.COLOR_GRAY2BGR)
        frame[roi_y1:roi_y2, roi_x1:roi_x2] = cv2.addWeighted(
            frame[roi_y1:roi_y2, roi_x1:roi_x2], 0.82, mask_bgr, 0.18, 0
        )

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qt_img = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888)
        self.live_view.setPixmap(
            QPixmap.fromImage(qt_img).scaled(
                self.live_view.width(),
                self.live_view.height(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = CubukSayimSistemi()
    win.show()
    sys.exit(app.exec())
