# Steel Bar Counter (Endüstriyel Çubuk Sayım Sistemi)
Bu proje, çelik fabrikalarında üretim bandından geçen nervürlü demirleri gerçek zamanlı olarak saymak için geliştirilmiştir.

### Özellikler:
* **OpenCV & Python** ile görüntü işleme.
* **Pixel Peak Analysis:** Birbirine tamamen yapışık gelen demirleri parlaklık zirvelerine göre ayırt eder.
* **Kinematik Takip:** Yüksek hızlı geçişlerde nesne kaybını önleyen hız toleranslı takip algoritması.
* **Fil Hafızası:** Bant duraklamalarında çift sayımı engelleyen 15 dakikalık takip belleği.
* **PyQt6 Dashboard:** Operatörler için ebat seçimi ve hedef takibi sağlayan kullanıcı arayüzü.