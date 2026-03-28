# Steel Bar Counter

Bu proje, uretim bandindan gecen celik cubuklari gercek zamanli olarak saymak icin
gelistirilmis bir OpenCV + PyQt6 uygulamasidir.

## Guncel Sayim Mantigi

- ROI icinde hareketli ve parlak cubuk adaylari ayiklanir.
- Yapismis cubuklar, yatay parlaklik profili uzerinden peak analizi ile ayrilir.
- Takip, yalnizca anlik `x` yakinligiyla degil, onceki hiz tahminiyle yapilir.
- Sayim, tek bir karede tam cizgi kesismesi beklenmeden; hareket gecmisi ve sayim
  bandi birlikte kullanilarak yapilir.
- Eski/stale track'ler kisa sure sonra silinir, yeni cubuklarla karismalari engellenir.

## Ayrintili Teknik Not

Sorunun kaynagi, yapilan duzeltmeler ve canli ortamda nasil kontrol edilmesi
gerektigi icin [COZUM_NOTLARI.md](COZUM_NOTLARI.md) dosyasina bakabilirsiniz.

## Neden Bu Degisiklik Yapildi?

Eski surum cok dusuk akis hizinda calisiyordu ancak normal hizda su sorunlar ortaya
cikiyordu:

- Obje eslestirme sadece anlik `x` mesafesine baktigi icin hizli gecislerde ID kopuyordu.
- Sayim, cubugun ayni track ile tam o karede kirmizi cizgiyi kesmesine bagliydi.
- Dakikalarca bellekte tutulan kayip track'ler, yeni cubuklara yanlis eslesebiliyordu.

Bu repo icindeki guncel surum, bu uc ana sorunu hedef alir.

## Kurulum

```bash
pip install opencv-python numpy PyQt6 python-dotenv
```

`.env` dosyasi:

```env
CAMERA_USER=kullanici
CAMERA_PASS=sifre
CAMERA_IP=192.168.x.x
```

## Calistirma

```bash
python main.py
```
