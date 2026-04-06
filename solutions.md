# Cozum Rehberi

Bu dosya, projede su anda gordugumuz asil problemi, buna karsi gelistirilen
cozumu ve canli testte istenen sonuc alinmazsa hangi degerlerle oynanmasi
gerektigini anlatir.

## 1. Asil sorun ne?

Projede hata tek bir nedenden cikmiyor. Su anda uc ana problem var:

1. Ortadaki ayirici aparat bazen cubuk gibi algilaniyor.
2. Isik degisimi bazen hareket gibi algilaniyor ve sayac kendi kendine artiyor.
3. Cubuklar hizlandiginda veya birbirine cok yaklastiginda, tek tek cubuklari
   ayirmak zorlasiyor.

Ogrencinin son denemesinde bu sorunlar daha da buyumus, cunku:

- ROI biraz fazla asagi kaymis ve aparat bolgesini daha fazla icine almaya baslamis.
- `adaptiveThreshold + MOG2` birlikte kullanildigi icin parlaklik degisimleri
  yalanci tespit uretmeye baslamis.
- Peak ayarlari fazla gevsetildigi icin tek bir grup, birden fazla sahte cubuk
  olarak bolunebiliyor.

## 2. Gelistirilen yeni cozum ne yapiyor?

Yeni surumde sayim mantigi tekrar sikilastirildi.

### 2.1 ROI yukariya alindi

Analiz bolgesi, ayirici aparat ve alt taraftaki makine govdesinden biraz daha
uzak olacak sekilde ust banda tasindi.

Amac:

- Sabit mekanik parcalari cubuk zannetmemek
- Sayimi cubuklarin daha temiz gorundugu bolgede yapmak

Bu kisim `main.py` icindeki `_get_roi_bounds()` fonksiyonunda bulunur.

## 2.2 Isik degisimini bastirmak icin MOG2 merkezli yapi kaldirildi

Yeni mantik, her kareyi bir onceki kareyle karsilastiriyor.
Ama bunu dogrudan yapmiyor:

- ROI once gri tona cevriliyor
- CLAHE ile kontrast dengeleniyor
- Gaussian blur ile mikro gurultu azaltiliyor
- Kare farki alinmadan once global parlaklik kaymasi medyan ile bastiriliyor

Boylece tum sahne bir anda aydinlansa bile sistem bunu "toplu hareket" gibi
algilamiyor.

Bu kisim `main.py` icindeki `_build_motion_mask()` fonksiyonunda bulunur.

## 2.3 Yalnizca parlak ve yapisal olarak cubuga benzeyen bolgeler tutuluyor

Sadece hareket eden her sey alinmiyor.
Ayrica su filtreler de uygulaniyor:

- parlaklik tabanli maske
- top-hat tabanli ince yapisal detay maskesi
- alt taraftaki makine bolgesini ignore etme

Bu sayede aparat, govde ve asiri genis gurultu lekeleri daha kolay eleniyor.

Bu kisim `main.py` icindeki `_build_structure_mask()` fonksiyonunda bulunur.

## 2.4 Sayim sadece "gercek track" icin yapiliyor

Bir track'in sayilmasi icin:

- ayni yone dogru istikrarli hareket etmesi
- yeterli yatay mesafe katetmesi
- dikeyde fazla ziplamamasi
- sayim cizgisinin iki tarafinda da gorulmesi

gerekir.

Bu sayede aparat gibi sabit ya da yanlis bolunmus yalanci tespitlerin sayaci
arttirma ihtimali azaltilir.

Bu kisim `main.py` icindeki `_count_if_needed()` fonksiyonunda bulunur.

## 3. Ogrencin test ettiginde sonuc iyi degilse hangi degerlerle oynamali?

Asagidaki ayarlari rastgele degil, bu sirayla denemesi daha dogru olur.

## 3.1 Ilk bakilacak yer: ROI

Dosya: `main.py`
Fonksiyon: `_get_roi_bounds()`

Su degerler var:

```python
roi_y1 = int(h * 0.22)
roi_y2 = int(h * 0.41)
roi_x1 = max(0, self.cizgi_x - 260)
roi_x2 = min(w, self.cizgi_x + 210)
```

### Eger aparat yine algilaniyorsa

- `roi_y1` degerini biraz arttir: `0.22 -> 0.24` veya `0.25`
- `roi_y2` degerini biraz azalt: `0.41 -> 0.39`

Bu, ROI'yi biraz daha yukariya tasir.

### Eger cubuklar ROI'ye gec giriyor veya gec cikiyorsa

- `roi_x1` degerindeki `260` sayisini arttir: `260 -> 300`
- `roi_x2` degerindeki `210` sayisini arttir: `210 -> 240`

Bu, yatay analiz alanini genisletir.

## 3.2 Isik degisiminde yalanci sayim varsa

Dosya: `main.py`
Parametreler: `motion_threshold`, `bright_percentile`

Her ebat icin `self.ebat_ayarlari` altinda bulunur.

### Ilk denenmesi gereken

- `motion_threshold` degerini 2-4 puan arttir

Ornek:

- `10 mm` icin `17 -> 20` veya `21`
- `8 mm` icin `16 -> 18` veya `19`

Bu ne yapar:

- Kucuk aydinlanma/kararma dalgalanmalarini hareket saymaz

### Hala aparat veya parlak yansima giriyorsa

- `bright_percentile` degerini 1-3 puan arttir

Ornek:

- `75 -> 77`
- `76 -> 78`

Bu ne yapar:

- Sadece daha parlak tepe noktalarini dikkate alir

Not:
Bu degeri fazla arttirirsa ince cubuklar kaybolabilir.

## 3.3 Cubuklar eksik sayiliyorsa

Once su sirayla dene:

1. `motion_threshold` degerini 1-2 puan azalt
2. `min_a` degerini biraz azalt
3. `dist` degerini biraz arttir

### `min_a`

Bu deger cok yuksek olursa ince cubuklar elenir.

Ornek:

- `10 mm` icin `12 -> 10`
- `8 mm` icin `10 -> 8`

### `dist`

Bu deger track eslestirmede kullanilir.
Cubuk hizli geciyorsa biraz buyutmek gerekebilir.

Ornek:

- `10 mm` icin `90 -> 100` veya `110`
- `8 mm` icin `80 -> 95`

## 3.4 Cubuklar birbirine yakin gecince sayim sapitiyorsa

Dosya: `main.py`
Parametreler: `limit_w`, `peak_threshold`

### Eger iki yakin cubuk tek cubuk gibi kaliyorsa

- `limit_w` degerini biraz dusur

Ornek:

- `10 mm` icin `18 -> 16`
- `8 mm` icin `16 -> 14`

Bu ne yapar:

- Genis blob icindeki pikleri daha kolay ayirir

### Eger tek cubuk birden fazla cubuk gibi bolunuyorsa

- `peak_threshold` degerini arttir

Ornek:

- `160 -> 164`
- `158 -> 162`

Bu ne yapar:

- Zayif parlaklik tepeciklerini cubuk merkezi saymaz

## 3.5 Sayim gec geliyor veya hic gelmiyorsa

Dosya: `main.py`
Parametreler:

- `count_band_half_width`
- `min_horizontal_speed`
- `track_timeout_frames`

### Cizgiyi geciyor ama saymiyorsa

- `count_band_half_width`: `34 -> 30`

Bu, sayim bandini biraz daraltir.

### Hala hareket ettigi halde saymiyorsa

- `min_horizontal_speed`: `1.2 -> 0.9`

Bu, daha yavas ama gercek hareketleri de kabul eder.

### Hizli geciste track kopuyorsa

- `track_timeout_frames`: `10 -> 12` veya `14`

Bu, kisa sureli kayiplarda track'i hemen dusurmez.

## 3.6 Yalanci sayim tekrar oluyorsa

Dosya: `main.py`
Parametreler:

- `count_cooldown_seconds`
- `max_vertical_speed`

### Ayni lane icinde arka arkaya cift sayim oluyorsa

- `count_cooldown_seconds`: `0.85 -> 1.0` veya `1.1`

### Tespitler dikey zipliyorsa ve sahte sayim uretiyorsa

- `max_vertical_speed`: `6.5 -> 5.0`

Bu, dikey oynayan yalanci track'leri daha sert eler.

## 4. En dogru test sirasi ne olmali?

Ogrencin ayarlari su sirayla denemeli:

1. Once ROI'yi duzelt
2. Sonra `motion_threshold` ile isik yalanci tespitlerini bastir
3. Sonra `bright_percentile` ile aparat/yansima yalancilarini azalt
4. Sonra `limit_w` ve `peak_threshold` ile yakin cubuk ayrimini ayarla
5. En son `dist`, `track_timeout_frames`, `min_horizontal_speed` ile takip kalibrasyonu yap

## 5. Hangi durumda bu yol yeterli degildir?

Su durumlarda `cv2` tabanli bu yontem yine zorlanabilir:

- Kamera acisi cok degisken ise
- Fabrika isigi cok sert degisiyorsa
- Cubuklar cok sikisik halde geliyor ve pik analizi yeterli olmuyorsa
- Aparat ve cubuk gorunumu birbirine cok benziyorsa

Bu durumda artik sonraki asama YOLO tabanli tespit olmalidir.
Bu gecis icin `yolo_kurulum.md` dosyasina bakilmalidir.
