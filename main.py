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
        self.setWindowTitle("Zeynep - Cubuk Sayim Dashboard v31.0 (Tam Koruma)")
        self.setGeometry(50, 50, 1400, 800)
        self.setStyleSheet("background-color: #f4f6f9;")

        self.sayilan_adet = 0
        self.tracked_objects = {}
        self.next_obj_id = 0
        self.cizgi_x = 450
        self.recent_count_events = []
        self.frame_index = 0

        # Çözüm notlarındaki harika takip ayarları (Aynen korundu)
        self.track_timeout_frames = 20 
        self.count_band_half_width = 42
        self.vertical_match_limit = 55
        
        self.min_frames_for_count = 5 
        self.count_cooldown_seconds = 0.6 
        self.warmup_frames = 60 # Başlangıç ısınma süresi

        self.ebat_ayarlari = {
            "8 mm": {
                "kernel": 3,
                "min_a": 10, 
                "max_a": 18000,
                "dist": 120, 
                "limit_w": 22,
                "limit_h": 20,
                "peak_threshold": 85, 
            },
            "10 mm": {
                "kernel": 3,
                "min_a": 20,
                "max_a": 22000,
                "dist": 110,
                "limit_w": 26,
                "limit_h": 24,
                "peak_threshold": 142,
            },
            "12 mm": {
                "kernel": 5,
                "min_a": 25,
                "max_a": 27000,
                "dist": 125,
                "limit_w": 30,
                "limit_h": 28,
                "peak_threshold": 145,
            },
            "14 mm": {
                "kernel": 5,
                "min_a": 30,
                "max_a": 32000,
                "dist": 140,
                "limit_w": 34,
                "limit_h": 32,
                "peak_threshold": 148,
            },
            "16 mm": {
                "kernel": 7,
                "min_a": 35,
                "max_a": 38000,
                "dist": 155,
                "limit_w": 38,
                "limit_h": 36,
                "peak_threshold": 150,
            },
            "20 mm": {
                "kernel": 9,
                "min_a": 40,
                "max_a": 46000,
                "dist": 175,
                "limit_w": 46,
                "limit_h": 40,
                "peak_threshold": 154,
            },
        }
        self.aktif_ayar = self.ebat_ayarlari["8 mm"]

        self.fgbg = cv2.createBackgroundSubtractorMOG2(
            history=500, 
            varThreshold=40, # Gürültü engellemek için eşik yükseltildi
            detectShadows=False,
        )

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

    def set_line_position(self, event):
        # Çizgi değiştiğinde tüm eski takipleri temizle ve ısınma süresi başlat
        self.cizgi_x = int(event.pos().x() * (1280 / self.live_view.width()))
        self.tracked_objects = {}
        self.warmup_frames = self.frame_index + 30 # Çizgi değişince 1 saniye bekle

    def reset_count(self):
        self.sayilan_adet = 0
        self.label_sayac.setText("0")
        self.tracked_objects = {}
        self.recent_count_events = []
        self.label_sayac.setStyleSheet(self.sayac_normal_stil)

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

    def _extract_detections(self, roi, roi_x1, roi_y1, full_fgmask):
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        # ARTIK MOG2 MASKESİNİ BURADA DEĞİL, ANA DÖNGÜDEN ALIYORUZ
        # Bu sayede ROI kayınca maske bozulmuyor.
        roi_fgmask = full_fgmask[roi_y1 : roi_y1 + roi.shape[0], roi_x1 : roi_x1 + roi.shape[1]]
        
        bright_mask = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                          cv2.THRESH_BINARY, 11, 2)
        final_mask = cv2.bitwise_and(roi_fgmask, bright_mask)

        k_boyut = self.aktif_ayar["kernel"]
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_boyut, k_boyut))
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_OPEN, kernel)
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(
            final_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        detections = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (self.aktif_ayar["min_a"] < area < self.aktif_ayar["max_a"]):
                continue

            x_c, y_c, w_c, h_c = cv2.boundingRect(cnt)
            
            # MAKİNE ELEME: Daha sert oran kontrolü
            if w_c > (self.aktif_ayar["limit_w"] * 2.5) or (float(w_c)/max(h_c,1) > 1.2):
                continue

            if w_c < 5 or h_c < 5:
                continue

            hull_area = max(cv2.contourArea(cv2.convexHull(cnt)), 1.0)
            solidity = float(area) / hull_area
            if (float(w_c) / max(h_c, 1)) <= 0.15 or solidity <= 0.28:
                continue

            roi_gray = gray[y_c : y_c + h_c, x_c : x_c + w_c]
            if roi_gray.size == 0:
                continue

            horizontal_profile = np.mean(roi_gray, axis=0)
            horizontal_profile = self._smooth_profile(horizontal_profile)

            peak_threshold = max(
                self.aktif_ayar["peak_threshold"] * 0.7, 
                float(horizontal_profile.mean() + horizontal_profile.std() * 0.05),
            )
            
            min_peak_gap = 4

            peaks = []
            for i in range(1, len(horizontal_profile) - 1):
                center_val = horizontal_profile[i]
                if (
                    center_val >= horizontal_profile[i - 1]
                    and center_val >= horizontal_profile[i + 1]
                    and center_val >= peak_threshold
                ):
                    if not peaks or (i - peaks[-1]) > min_peak_gap:
                        peaks.append(i)
                    elif center_val > horizontal_profile[peaks[-1]]:
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
            else:
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
            "creation_frame": self.frame_index 
        }

    def _update_track(self, data, detection):
        prev_x, prev_y = data["cx"], data["cy"]
        gap = max(1, data["missing"] + 1)
        inst_vx = (detection["cx"] - prev_x) / gap
        inst_vy = (detection["cy"] - prev_y) / gap

        if data["frames_seen"] == 1:
            vx, vy = inst_vx, inst_vy
        else:
            vx = 0.65 * data["vx"] + 0.35 * inst_vx
            vy = 0.65 * data["vy"] + 0.35 * inst_vy

        return {
            "cx": detection["cx"],
            "cy": detection["cy"],
            "start_x": data.get("start_x", prev_x),
            "start_y": data.get("start_y", prev_y),
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
            "creation_frame": data["creation_frame"]
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
                    self.vertical_match_limit, detection["h"] * 0.7, data["h"] * 0.7
                )
                if abs(dx) <= adaptive_x_limit and abs(dy) <= adaptive_y_limit:
                    score = abs(dx) + abs(dy) * 2 + data["missing"] * 10
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

    def _can_register_count(self, track):
        self._prune_count_events()
        for event in self.recent_count_events:
            if abs(event["cy"] - track["cy"]) <= 3:
                return False
        return True

    def _register_count(self, track):
        self.sayilan_adet += 1
        self.label_sayac.setText(str(self.sayilan_adet))
        self.hedef_kontrol()
        self.recent_count_events.append({"time": time.monotonic(), "cy": track["cy"]})

    def _count_if_needed(self):
        # ISINMA VEYA TIKLAMA SONRASI BEKLEME
        if self.frame_index < self.warmup_frames:
            return

        for obj_id, data in self.tracked_objects.items():
            if data["counted"] or data["missing"] > 0:
                continue

            ilk_gorulme_x = data.get("start_x", data["cx"])
            su_anki_x = data["cx"]

            # Açılışta veya tıklama anında oluşan gürültüyü sayma
            yeni_mi = data["creation_frame"] > (self.warmup_frames - 20)

            gelis_yeri_dogru_mu = ilk_gorulme_x < (self.cizgi_x - 40)
            cizgiyi_gecti_mi = su_anki_x > (self.cizgi_x + 10)
            gercek_seyahat_mi = (su_anki_x - ilk_gorulme_x) > 50

            if (
                data["frames_seen"] >= self.min_frames_for_count 
                and yeni_mi
                and gelis_yeri_dogru_mu 
                and cizgiyi_gecti_mi 
                and gercek_seyahat_mi 
                and self._can_register_count(data)
            ):
                data["counted"] = True
                self._register_count(data)

    def main_loop(self):
        ret, frame = self.vs.read()
        if not ret or frame is None:
            return

        self.frame_index += 1
        h, w = frame.shape[:2]

        # ÇÖZÜM: Arka plan çıkarmayı tüm frame üzerinde yapıyoruz (ROI bağımsızlığı)
        full_fgmask = self.fgbg.apply(frame, learningRate=-1)

        roi_y1, roi_y2 = int(h * 0.32), int(h * 0.48)
        roi_x1 = max(0, self.cizgi_x - 250)
        roi_x2 = min(w, self.cizgi_x + 250)
        roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]

        # Analiz fonksiyonuna tam maskeyi gönderiyoruz
        detections, final_mask = self._extract_detections(roi, roi_x1, roi_y1, full_fgmask)
        self._match_tracks(detections)
        self._count_if_needed()

        # Arayüz Çizimleri
        cv2.rectangle(frame, (self.cizgi_x - 42, 0), (self.cizgi_x + 42, h), (0, 255, 255), 1)
        cv2.line(frame, (self.cizgi_x, 0), (self.cizgi_x, h), (0, 0, 255), 2)
        cv2.rectangle(frame, (roi_x1, roi_y1), (roi_x2, roi_y2), (255, 255, 0), 1)

        for obj_id, data in self.tracked_objects.items():
            if data["missing"] > 1:
                continue

            cx, cy = int(data["cx"]), int(data["cy"])
            color = (255, 0, 0) if data["counted"] else (0, 255, 0)
            cv2.rectangle(frame, (cx - 11, cy - 11), (cx + 11, cy + 11), color, 2)
            cv2.putText(
                frame,
                f"ID {obj_id}",
                (cx - 18, cy - 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
            )
            if data["counted"]:
                cv2.putText(
                    frame,
                    "SAYILDI",
                    (cx - 25, cy - 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 0, 0),
                    2,
                )

        mask_bgr = cv2.cvtColor(final_mask, cv2.COLOR_GRAY2BGR)
        frame[roi_y1:roi_y2, roi_x1:roi_x2] = cv2.addWeighted(
            frame[roi_y1:roi_y2, roi_x1:roi_x2], 0.8, mask_bgr, 0.2, 0
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