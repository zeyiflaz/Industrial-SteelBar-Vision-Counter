import sys, cv2, threading, time, urllib.parse, os
import numpy as np
from dotenv import load_dotenv # Ortam değişkenlerini (.env) yüklemek için güvenlik kütüphanesi
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, 
                             QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLineEdit)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap, QFont

# ==============================================================================
# 1. GÜVENLİK VE BAĞLANTI AYARLARI
# ==============================================================================
# GitHub gibi açık platformlarda şifre sızıntısını önlemek için veriler .env dosyasından çekilir.
load_dotenv() 

USER = os.getenv("CAMERA_USER")
PASS = os.getenv("CAMERA_PASS")
IP_ADDR = os.getenv("CAMERA_IP")

# Eğer .env dosyası eksikse sistemi durdurarak güvenliği sağla.
if not USER or not PASS or not IP_ADDR:
    print("❌ HATA: .env dosyası bulunamadı veya içindeki bilgiler eksik!")
    sys.exit()

# Şifre içindeki özel karakterleri (örn: !) URL formatına uygun hale getirir.
safe_pass = urllib.parse.quote(PASS)
URL = f"rtsp://{USER}:{safe_pass}@{IP_ADDR}/axis-media/media.amp?resolution=1280x720"

# ==============================================================================
# 2. ASENKRON KAMERA YAYINI (THREADING)
# ==============================================================================
class CameraStream:
    """
    Görüntü işleme ve arayüzün (UI) donmasını engellemek için kameradan gelen 
    görüntüleri arka planda ayrı bir iş parçacığı (Thread) olarak okur.
    """
    def __init__(self, url):
        self.cap = cv2.VideoCapture(url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Gecikmeyi (lag) önlemek için arabelleği 1'e indir
        self.started = False
        self.read_lock = threading.Lock() # Veri çakışmasını önleyen kilit mekanizması
        self.ret, self.frame = False, None

    def start(self):
        if not self.cap.isOpened(): return False
        self.started = True
        threading.Thread(target=self.update, args=(), daemon=True).start()
        return True

    def update(self):
        while self.started:
            ret, frame = self.cap.read()
            if ret:
                with self.read_lock: 
                    self.ret, self.frame = ret, frame
            else: 
                time.sleep(0.01)

    def read(self):
        with self.read_lock:
            return self.ret, self.frame.copy() if self.frame is not None else None

# ==============================================================================
# 3. ANA ARAYÜZ VE GÖRÜNTÜ İŞLEME MOTORU (MAIN APP)
# ==============================================================================
class CubukSayimSistemi(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Zeynep - Çubuk Sayım Dashboard v28.27 (Referanslı Analiz)")
        self.setGeometry(50, 50, 1400, 800)
        self.setStyleSheet("background-color: #f4f6f9;")
        
        # --- TAKİP (TRACKING) VE SAYIM DEĞİŞKENLERİ ---
        self.sayilan_adet = 0
        self.tracked_objects = {}  # Çubuklara atanan kimliklerin tutulduğu sözlük
        self.next_obj_id = 0       # Sisteme giren yeni çubuğa verilecek ID
        self.cizgi_x = 450         # Sayım çizgisinin merkez X koordinatı
        
        # 🚀 FİL HAFIZASI: Bant durduğunda çubukları tam 15 dakika unutmaz!
        self.fil_hafizasi = 30000
        
        # --- DİNAMİK EBAT PARAMETRELERİ (KOMPLE LİSTE) ---
        # limit_w: Analiz başlatmak için minimum genişlik eşiği
        # dist: İki farklı çubuğu ayırmak için gereken minimum takip mesafesi
        self.ebat_ayarlari = {
            "8 mm":  {"kernel": 3, "min_a": 15, "max_a": 20000, "dist": 110, "limit_w": 25, "limit_h": 25},
            "10 mm": {"kernel": 3, "min_a": 20, "max_a": 25000, "dist": 120, "limit_w": 30, "limit_h": 30},
            "12 mm": {"kernel": 5, "min_a": 25, "max_a": 30000, "dist": 130, "limit_w": 35, "limit_h": 35},
            "14 mm": {"kernel": 5, "min_a": 30, "max_a": 35000, "dist": 140, "limit_w": 40, "limit_h": 40},
            "16 mm": {"kernel": 7, "min_a": 35, "max_a": 40000, "dist": 150, "limit_w": 45, "limit_h": 45},
            "20 mm": {"kernel": 9, "min_a": 40, "max_a": 50000, "dist": 170, "limit_w": 55, "limit_h": 55} 
        }
        self.aktif_ayar = self.ebat_ayarlari["10 mm"] # Varsayılan açılış ayarı
        
        # Görüntü motoru: Hareket ve Arka Plan Çıkarıcı
        self.fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=False)

        self.init_ui()
        self.vs = CameraStream(URL); self.vs.start()
        
        # QTimer: 30ms döngü (~33 FPS)
        self.timer = QTimer(); self.timer.timeout.connect(self.main_loop); self.timer.start(30)

    # --- KULLANICI ARAYÜZÜ (UI) TASARIMI ---
    def init_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # SOL PANEL: KONTROLLER
        left_panel = QVBoxLayout()
        left_panel.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        label_style = "font-weight: bold; font-size: 16px; color: #2c3e50; margin-bottom: 5px;"
        input_style = "background-color: white; border: 2px solid #bdc3c7; border-radius: 5px; padding: 10px; font-size: 18px; color: black;"

        # Ebat Seçimi
        self.lbl_ebat = QLabel("Ebat Seç")
        self.lbl_ebat.setStyleSheet(label_style)
        self.combo_ebat = QComboBox()
        self.combo_ebat.addItems(["8 mm", "10 mm", "12 mm", "14 mm", "16 mm", "20 mm"])
        self.combo_ebat.setStyleSheet(input_style)
        self.combo_ebat.setCurrentText("10 mm") 
        self.combo_ebat.currentTextChanged.connect(self.ebat_degistir) 
        left_panel.addWidget(self.lbl_ebat); left_panel.addWidget(self.combo_ebat)
        
        self.lbl_ebat_uyari = QLabel("⚠️ DİKKAT: Yanlış ebat seçimi sayımı bozar!")
        self.lbl_ebat_uyari.setStyleSheet("color: #e74c3c; font-size: 13px; font-weight: bold; margin-top: -5px;")
        left_panel.addWidget(self.lbl_ebat_uyari)
        
        left_panel.addSpacing(20)

        # Hedef Girişi
        self.lbl_hedef = QLabel("Hedef (Adet)")
        self.lbl_hedef.setStyleSheet(label_style)
        self.input_hedef = QLineEdit()
        self.input_hedef.setPlaceholderText("Örn: 500")
        self.input_hedef.setStyleSheet(input_style)
        self.input_hedef.textChanged.connect(self.hedef_kontrol) 
        left_panel.addWidget(self.lbl_hedef); left_panel.addWidget(self.input_hedef)
        left_panel.addSpacing(40)

        # Sayılan Göstergesi
        self.lbl_sayilan_baslik = QLabel("SAYILAN")
        self.lbl_sayilan_baslik.setStyleSheet(label_style)
        
        self.label_sayac = QLabel("0")
        self.sayac_normal_stil = "background-color: #27ae60; border: 3px solid #2ecc71; border-radius: 10px; padding: 20px; font-size: 70px; font-weight: bold; color: white;"
        self.sayac_hedef_stil = "background-color: #f1c40f; border: 4px solid #f39c12; border-radius: 10px; padding: 20px; font-size: 70px; font-weight: bold; color: #2c3e50;"
        self.label_sayac.setStyleSheet(self.sayac_normal_stil)
        self.label_sayac.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        left_panel.addWidget(self.lbl_sayilan_baslik); left_panel.addWidget(self.label_sayac)
        left_panel.addSpacing(40)

        # Sıfırlama Butonu
        btn_reset = QPushButton("🔄 SIFIRLA")
        btn_reset.clicked.connect(self.reset_count)
        btn_reset.setStyleSheet("padding: 15px; background-color: #e74c3c; color: white; font-weight: bold; font-size: 18px; border-radius: 5px;")
        left_panel.addWidget(btn_reset)

        # SAĞ PANEL: CANLI GÖRÜNTÜ
        self.live_view = QLabel()
        self.live_view.setMinimumSize(960, 540) 
        self.live_view.setStyleSheet("border: 5px solid #34495e; background-color: black;")
        self.live_view.mousePressEvent = self.set_line_position 

        main_layout.addLayout(left_panel, stretch=1)
        main_layout.addWidget(self.live_view, stretch=4)

    # --- ARAYÜZ FONKSİYONLARI ---
    def ebat_degistir(self, secilen_ebat):
        self.aktif_ayar = self.ebat_ayarlari[secilen_ebat] 

    def set_line_position(self, event):
        self.cizgi_x = int(event.pos().x() * (1280 / self.live_view.width()))

    def reset_count(self):
        self.sayilan_adet = 0
        self.label_sayac.setText("0")
        self.tracked_objects = {} 
        self.label_sayac.setStyleSheet(self.sayac_normal_stil) 

    def hedef_kontrol(self):
        hedef_metin = self.input_hedef.text()
        if hedef_metin.isdigit():
            hedef_sayi = int(hedef_metin)
            if hedef_sayi > 0 and self.sayilan_adet >= hedef_sayi:
                self.label_sayac.setStyleSheet(self.sayac_hedef_stil)
            else:
                self.label_sayac.setStyleSheet(self.sayac_normal_stil)

    # ==============================================================================
    # 4. GÖRÜNTÜ İŞLEME VE SAYIM MOTORU (PIXEL PEAK ANALYSIS)
    # ==============================================================================
    def main_loop(self):
        ret, frame = self.vs.read()
        if not ret or frame is None: return
        h, w = frame.shape[:2]

        # 4.1 ROI (Alan Kesme)
        roi_y1, roi_y2 = int(h*0.48), int(h*0.65)
        roi_x1, roi_x2 = int(w*0.05), int(w*0.90)
        roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]

        # 4.2 GÖRÜNTÜ FİLTRELEME
        fgmask = self.fgbg.apply(roi, learningRate=0.001) 
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, bright_mask = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY) 
        final_mask = cv2.bitwise_and(fgmask, bright_mask) 

        # 4.3 MORFOLOJİK TEMİZLİK
        k_boyut = self.aktif_ayar["kernel"]
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_boyut, k_boyut))
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_OPEN, kernel)
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(final_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        aktif_tespitler = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if self.aktif_ayar["min_a"] < area < self.aktif_ayar["max_a"]: 
                x_c, y_c, w_c, h_c = cv2.boundingRect(cnt)
                solidity = float(area) / max(cv2.contourArea(cv2.convexHull(cnt)), 1)
                
                if (float(w_c)/max(h_c,1)) > 0.15 and solidity > 0.35:
                    
                    # 🚀 PIXEL YOĞUNLUK ANALİZİ (Yapışık demirler için kesin çözüm)
                    roi_gray = gray[y_c:y_c+h_c, x_c:x_c+w_c]
                    horizontal_profile = np.mean(roi_gray, axis=0) # Bloğun yatay röntgeni
                    
                    peaks = []
                    # Bloğun içindeki en parlak tepe noktalarını (demir merkezlerini) bulur
                    for i in range(1, len(horizontal_profile)-1):
                        if horizontal_profile[i] > horizontal_profile[i-1] and horizontal_profile[i] > horizontal_profile[i+1]:
                            if horizontal_profile[i] > 160: # Parlaklık eşiği
                                if not peaks or (i - peaks[-1]) > (self.aktif_ayar["limit_w"] * 0.7):
                                    peaks.append(i)
                    
                    if len(peaks) > 1:
                        for peak_x in peaks:
                            aktif_tespitler.append({'cx': x_c + peak_x + roi_x1, 'cy': y_c + h_c // 2 + roi_y1})
                    else:
                        aktif_tespitler.append({'cx': x_c + w_c//2 + roi_x1, 'cy': y_c + h_c//2 + roi_y1})

        # 4.4 KESİN TAKİP SİSTEMİ (Raylı Sistem / Y-Ekseni Kilidi)
        yeni_tracked_objects = {}
        for tespit in aktif_tespitler:
            cx, cy = tespit['cx'], tespit['cy']
            best_id, min_dist = -1, self.aktif_ayar["dist"] 
            
            for obj_id, data in self.tracked_objects.items():
                if abs(cy - data['cy']) > 35: continue # Dikey zıplama ID çalmayı engeller
                
                dist = abs(cx - data['cx']) 
                if dist < min_dist: min_dist = dist; best_id = obj_id
                    
            if best_id != -1:
                yeni_tracked_objects[best_id] = {
                    'cx': cx, 'cy': cy, 'prev_x': self.tracked_objects[best_id]['cx'], 
                    'start_x': self.tracked_objects[best_id]['start_x'], 
                    'counted': self.tracked_objects[best_id]['counted'], 
                    'life': self.tracked_objects[best_id]['life'] + 1, 'missing': 0
                }
                del self.tracked_objects[best_id] 
            else:
                yeni_tracked_objects[self.next_obj_id] = {
                    'cx': cx, 'cy': cy, 'prev_x': cx, 'start_x': cx, 'counted': False, 'life': 1, 'missing': 0
                }
                self.next_obj_id += 1

        # 4.5 HAYALET AVCISI & TEMİZLİK
        for obj_id, data in self.tracked_objects.items():
            if data['cx'] > roi_x2 - 10 or data['cx'] < roi_x1 + 10: continue 
            if data['missing'] < self.fil_hafizasi: 
                data['missing'] += 1; yeni_tracked_objects[obj_id] = data
        self.tracked_objects = yeni_tracked_objects

        # 🚀 4.6 GÖRSEL REFERANS ÇİZGİLERİ (Geri Getirildi!)
        # Operatörün hizalamasını sağlayan tünel çizgileri
        kapi_sol, kapi_sag = self.cizgi_x - 120, self.cizgi_x + 120
        cv2.rectangle(frame, (kapi_sol, 0), (kapi_sag, h), (0, 255, 255), 1) # Sarı tünel referansı
        cv2.line(frame, (self.cizgi_x, 0), (self.cizgi_x, h), (0, 0, 255), 3) # Kırmızı sayım çizgisi

        for obj_id, data in self.tracked_objects.items():
            cx, cy, px = data['cx'], data['cy'], data['prev_x']
            
            # Sayım sadece kırmızı çizgi kılıç gibi kesildiği anda yapılır
            if not data['counted'] and data['life'] > 3:
                if (px <= self.cizgi_x < cx) or (cx < self.cizgi_x <= px):
                    self.sayilan_adet += 1
                    self.label_sayac.setText(str(self.sayilan_adet))
                    data['counted'] = True 
                    cv2.circle(frame, (cx, cy), 40, (0, 0, 255), -1) 
                    self.hedef_kontrol()
                
            if data['counted'] and data['missing'] == 0:
                cv2.putText(frame, "SAYILDI", (cx-20, cy-20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
                cv2.circle(frame, (cx, cy), 6, (255, 0, 0), -1)
            
            if data['missing'] == 0:
                cv2.rectangle(frame, (cx-10, cy-10), (cx+10, cy+10), (0, 255, 0), 2)

        # 4.7 EKRANA YANSITMA
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qt_img = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888)
        self.live_view.setPixmap(QPixmap.fromImage(qt_img).scaled(
            self.live_view.width(), self.live_view.height(), 
            Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))

if __name__ == "__main__":
    app = QApplication(sys.argv); win = CubukSayimSistemi(); win.show(); sys.exit(app.exec())