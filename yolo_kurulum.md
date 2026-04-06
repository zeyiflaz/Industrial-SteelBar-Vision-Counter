# YOLO Kurulum ve Gecis Rehberi

Bu dosya, mevcut `cv2` tabanli cozum yeterli olmazsa YOLO tabanli bir sisteme
gecmek icin izlenecek tam yolu anlatir.

Hedef:

1. Windows ortaminda YOLO'yu sifirdan kurmak
2. Modelin calistigini dogrulamak
3. Gerekirse cubuklar icin ozel veri seti hazirlamak
4. Bu projeyi YOLO ile yeniden duzenlemek

## 1. Ne zaman YOLO'ya gecilmeli?

Asagidaki durumlar varsa YOLO mantikli secenektir:

- Isik degisikligi cok fazla ve klasik threshold tabanli yontem cok oynaksa
- Aparat, ray, govde veya yansimalar cubukla cok kolay karisiyorsa
- Cubuklar birbirine cok yakin ve klasik peak ayirma mantigi yetmiyorsa
- Farkli kamera acilarinda ayni kodu tekrar tekrar kalibre etmek gerekiyorsa

## 2. Windows ortaminda sifirdan kurulum

Bu adimlar PowerShell icin yazildi.

## 2.1 Python surumunu kontrol et

PyTorch resmi sayfasina gore guncel Windows kurulumlari icin Python 3.10 ve uzeri
onerilir.

Kontrol:

```powershell
python --version
```

Eger Python yoksa veya cok eskiyse:

- Python 3.10, 3.11 veya 3.12 kur
- Kurulum sirasinda `Add Python to PATH` secenegini isaretle

## 2.2 Proje klasorunde sanal ortam olustur

```powershell
cd C:\Users\MSI\Desktop\Industrial-SteelBar-Vision-Counter
python -m venv .venv
```

Aktif et:

```powershell
.\.venv\Scripts\Activate.ps1
```

Eger PowerShell policy hatasi alirsan:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 2.3 Pip'i guncelle

```powershell
python -m pip install --upgrade pip
```

## 2.4 PyTorch kur

PyTorch resmi sayfasinda Windows icin kurulum komutu seciliyor.

Kaynak:

- PyTorch Start Locally: https://pytorch.org/get-started/locally/

Iki secenek var:

### Sadece CPU ile kurulum

GPU yoksa veya kurulum basit olsun isteniyorsa:

```powershell
pip install torch torchvision torchaudio
```

### NVIDIA GPU varsa

PyTorch sayfasindan sistemine uygun CUDA komutunu sec.
Ornek bir komut:

```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

Not:
CUDA secimini rastgele yapma.
PyTorch sayfasinda Windows + Pip + Python + uygun CUDA secilerek verilen komut
kullanilmali.

## 2.5 PyTorch kurulumunu dogrula

```powershell
python
```

Acilan Python icinde:

```python
import torch
print(torch.__version__)
print(torch.cuda.is_available())
```

Beklenen:

- Hata vermemeli
- GPU varsa `True` donmesi iyi olur

Cikmak icin:

```python
exit()
```

## 2.6 Ultralytics YOLO paketini kur

Ultralytics resmi dokumanina gore temel kurulum:

- Docs: https://docs.ultralytics.com/

Kurulum:

```powershell
pip install -U ultralytics
```

## 2.7 YOLO kurulumunu dogrula

```powershell
yolo checks
```

Eger `yolo` komutu taninmazsa:

```powershell
python -m ultralytics checks
```

## 2.8 Basit bir model indirip test et

```powershell
python -c "from ultralytics import YOLO; model = YOLO('yolo11n.pt'); print('OK')"
```

Not:
Ultralytics dokumaninda model isimleri zamanla degisebilir.
Guncel hafif detect modeli docs tarafindan hangi adla oneriliyorsa onu kullan.
Bu ornekte `yolo11n.pt` yazildi cunku kucuk ve hizlidir.

## 3. Mevcut proje icin en dogru YOLO stratejisi ne?

Bu proje icin en mantikli YOLO yolu:

1. Cubugun tamamini degil, sayim cizgisine yakin gorunen "cubuk ucu / cubuk baslangici"
   benzeri gorunur bolgeyi detect etmek
2. Sonra bu detection merkezlerini track edip saymak

Sebep:

- Tum cubuk boyunca detect etmek zor olabilir
- Cubuklar uzun ve birbirine paralel oldugu icin kutular birbiriyle cok cakismaya meyilli olabilir
- Sayim acisindan asil lazim olan sey, her cubugu tekil bir nesne olarak cizgiye yakin
  bolgede ayirt edebilmek

## 4. Eger hazir model yeterli degilse veri seti hazirlama

Muhtemelen hazir COCO modeli cubuklari dogrudan dogru saymayacak.
Bu yuzden ozel veri seti gerekir.

## 4.1 Hangi goruntuler etiketlenmeli?

Su senaryolardan kare toplanmali:

- Yavas akis
- Normal hiz
- Cubuklar birbirine yakin
- Cubuklar aralikli
- Isik degisikligi olan sahne
- Aparatin gorundugu anlar
- Bos bant goruntuleri

## 4.2 Neyi etiketlemeli?

Tek sinif yeterli:

```text
bar
```

Ama kutu cizerken su kurala sadik kal:

- Her cubuk icin sayim acisindan gorunen tekil bolgeyi isaretle
- Aparati asla `bar` diye etiketleme
- Bos sahneleri de veri setine koy

## 4.3 Etiketleme araci

Kolay secenekler:

- LabelImg
- CVAT
- Roboflow

Hedef format:

- YOLO detection format

## 4.4 Veri seti klasor yapisi

Repo altinda boyle bir yapi onerilir:

```text
dataset/
  images/
    train/
    val/
  labels/
    train/
    val/
  data.yaml
```

`data.yaml` ornegi:

```yaml
path: dataset
train: images/train
val: images/val

names:
  0: bar
```

## 5. YOLO modeli nasil egitilir?

Sanal ortam aktifken:

```powershell
yolo detect train data=dataset/data.yaml model=yolo11n.pt imgsz=960 epochs=100 batch=8 device=0
```

Aciklama:

- `model=yolo11n.pt`: hafif baslangic modeli
- `imgsz=960`: mevcut sahne icin daha uygun olabilir
- `epochs=100`: baslangic icin makul
- `batch=8`: GPU bellegine gore degisir
- `device=0`: ilk GPU

GPU yoksa:

```powershell
yolo detect train data=dataset/data.yaml model=yolo11n.pt imgsz=960 epochs=100 batch=4 device=cpu
```

Egitim bitince agirliklar genelde su klasorde olur:

```text
runs/detect/train/weights/best.pt
```

## 6. Bu projeyi YOLO ile nasil duzenlemeli?

Mevcut `main.py` dogrudan klasik CV mantigi icin yazilmis.
YOLO gecisinde projeyi asagidaki gibi bolmek daha saglikli olur.

## 6.1 Onerilen yeni dosya yapisi

```text
main.py
yolo_main.py
yolo_counter.py
tracker_utils.py
models/
  best.pt
dataset/
```

## 6.2 `yolo_counter.py` ne yapmali?

Bu dosya su sorumluluklari almali:

- YOLO modelini yuklemek
- Her framede detect calistirmak
- Detection merkezlerini almak
- Basit track mantigi kurmak
- Sayim cizgisini gecenleri saymak

## 6.3 `main.py` ne olmali?

Iki secenek var:

1. `main.py` sadece UI kalsin, secilebilir backend olsun
2. Ayrica `yolo_main.py` acilsin ve YOLO ayrik calissin

Ilk asamada en temiz yol:

- Mevcut `main.py`yi bozmamak
- Ayrica `yolo_main.py` olusturmak

Boylece klasik cozum ve YOLO cozum yan yana test edilebilir.

## 6.4 YOLO ile sayim mantigi nasil olmali?

YOLO detection tek basina sayim degildir.
Su akis gerekir:

1. Kareyi al
2. Model ile detection yap
3. Sadece `bar` sinifini filtrele
4. Her detection icin merkez nokta hesapla
5. Merkezleri track et
6. Track, sayim cizgisinin bir tarafindan diger tarafina gectiginde say

## 6.5 Basit YOLO calistirma ornegi

Asagidaki ornek, mantigi gostermek icindir:

```python
from ultralytics import YOLO
import cv2

model = YOLO("models/best.pt")
cap = cv2.VideoCapture("video.mp4")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame, conf=0.35, verbose=False)

    for box in results[0].boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        x1, y1, x2, y2 = box.xyxy[0].tolist()

        cx = int((x1 + x2) / 2)
        cy = int((y1 + y2) / 2)

        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

    cv2.imshow("YOLO", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
```

Bu sadece detection gosterir.
Bunun ustune track ve line-crossing sayim eklenmelidir.

## 7. YOLO ile track nasil yapilmali?

Uc secenek vardir:

1. Basit centroid tracking
2. ByteTrack
3. BoTSORT

Ilk deneme icin:

- Basit centroid tracking yeterli olabilir

Ama cubuklar cok yakin ve hizli ise:

- ByteTrack daha iyi olabilir

Ultralytics zaten tracking modlari sunabiliyor.
Ancak proje icin en anlasilir yol, once detection + basit track yazmaktir.

## 8. YOLO tabanli projede ayarlanacak ana parametreler

Canli testte su parametrelerle oynanir:

- `conf`
- `imgsz`
- tracking mesafe esigi
- sayim cizgisi konumu
- line-cross cooldown

### `conf`

Baslangic:

```text
0.35
```

Eger yalanci detection coksa:

```text
0.45 - 0.55
```

Eger gercek cubuklari kaciriyorsa:

```text
0.25 - 0.30
```

### `imgsz`

Baslangic:

```text
960
```

Eger ince cubuklar kuculuyorsa:

```text
1280
```

Ama hiz dusuyorsa:

```text
640
```

## 9. Onerilen uygulama plani

Ogrencin su sirayla gitmeli:

1. Once bu repodaki guncel `cv2` cozumunu dene
2. Olmazsa YOLO kurulumunu tamamla
3. Hazir model ile sadece demo test yap
4. Sonra kendi veri setini etiketle
5. `best.pt` egit
6. `yolo_main.py` ile detection + tracking + counting kur
7. Son olarak UI ile birlestir

## 10. Ozet

Eger klasik CV tarafinda:

- isik degisimi
- aparat karismasi
- sikisik cubuklar

hala ciddi sorun cikariyorsa, YOLO daha dogru uzun vadeli yol olur.
Ama YOLO'yu da sadece kurmak yetmez.
Bu proje icin asil kritik kisim:

- dogru veri seti
- dogru etiketleme
- detection ustune saglam tracking kurmak

olacaktir.
