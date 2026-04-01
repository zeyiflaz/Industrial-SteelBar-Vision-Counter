# Cubuk Sayim Sorunu ve Cozum Notlari

Bu dosya, projedeki normal akis hizinda gorulen yanlis sayim problemini ve yapilan
duzeltmeleri teknik olarak aciklamak icin hazirlandi.

## 1. Eski sorunun kaynagi neydi?

Projede cubuk tespiti genel olarak dogru yone gidiyordu, ancak sayim mantigi uc
kritik noktada kiriliyordu:

1. Takip sadece anlik `x` yakinligina bakiyordu.
   Normal hizda bir cubuk iki kare arasinda cizgiye cok yakin konumdan daha ileri
   bir konuma sicrarsa, ayni obje olarak eslesmeyebiliyordu.

2. Sayim tek karelik cizgi kesisimine bagliydi.
   Eski kodda bir cubugun sayilmasi icin ayni track'in `prev_x` ve `cx` degerleriyle
   kirmizi sayim cizgisini tam o karede kesmesi gerekiyordu. Kare atlama, motion blur
   veya anlik maske bozulmasi olursa sayim kaciyordu.

3. Kayip objeler cok uzun sure tutuluyordu.
   Eski mantikta kaybolan track'ler cok uzun sure bellekten dusurulmedigi icin,
   daha sonra gelen yeni bir cubuk bazen eski bir track ile yanlis eslesebiliyordu.
   Bu da hem eksik sayim hem cift sayim riski olusturuyordu.

## 2. Biz neyi degistirdik?

## 2.1 Takibi hiz toleransli hale getirdik

Yeni surumde obje sadece mevcut `x` konumuna gore degil, onceki karelerden gelen
hareket hizina gore tahmin edilerek eslestiriliyor.

Bu sayede:

- Normal akista kareler arasinda daha fazla yer degistiren cubuklar ayni ID ile
  tutulabiliyor.
- Tek bir frame'de goruntu zayiflasa bile obje takibi hemen kopmuyor.

## 2.2 Sayimi tek-cizgi yerine sayim bandi mantigina gecirdik

Sayim artik sadece "bu karede tam cizgiyi kesti mi?" sorusuna bagli degil.

Yeni mantik sunlara birlikte bakiyor:

- Cubuk yeterince hareket etti mi?
- Track iki tarafta da goruldu mu?
- Kirmizi cizgiyi kesti mi veya sayim bandinin iki tarafina da uzandi mi?

Bu yaklasim, normal hizda kare atlama olsa bile sayimi daha dayanikli hale getiriyor.

## 2.3 Stale track'leri kisalttik

Kayip objeler artik kisa bir sure sonra takipten dusuruluyor.

Boylece:

- Yeni cubuklarin eski ID'lere yanlis baglanma riski azaltiyor.
- Sistem uzun sure biriken hayalet track'lerle kirlenmiyor.

## 2.4 Cift sayimi ayri bir debounce mantigiyla koruduk

Eski "uzun hafiza" davranisi dogrudan track uzerinden kuruluydu.
Yeni surumde cift sayimi engellemek icin, track'i yapay olarak uzun sure saklamak
yerine kisa sureli bir sayim olayi hafizasi kullaniliyor.

Bu daha guvenli, cunku:

- Takip ve sayim korumasi birbirine karismiyor.
- Takip motoru sadece goruntudeki gercek objelerle ilgileniyor.

## 3. Neden hemen YOLO'ya gecmedik?

Bu asamada mevcut problem, once algoritmanin takip ve sayim tarafindaki zayifligindan
kaynaklandigi icin once `cv2` tabanli yapinin toparlanmasi daha dogruydu.

Yapilan degisikliklerden sonra:

- Eski mantik referans videoda belirgin undercount yapiyordu.
- Yeni mantik ayni referans uzerinde gercek artis miktarina cok daha yakin sonuc verdi.

Bu yuzden su anda ilk denenmesi gereken yol, yeni `cv2` mantigini canli akista test
etmektir.

## 4. Canli ortamda nasil test edilmeli?

Asagidaki kontroller ayni ebat icin en az 3 farkli akista yapilmalidir:

1. Dusuk hiz testi
   Sistem daha once dogru sayiyorsa, yeni surum burada da bozulmamalidir.

2. Normal hiz testi
   Asil hedef burasidir. Gercek adet elle sayilarak uygulama sayaci ile karsilastirilmalidir.

3. Kisa dur-kalk testi
   Bant anlik yavaslayip tekrar hizlandiginda cift sayim veya eksik sayim oluyor mu
   kontrol edilmelidir.

4. Farkli ebat testi
   `8 mm`, `10 mm`, `12 mm` gibi secimlerde maske davranisi fark edebilir.

## 5. Test sirasinda nelere bakilmali?

- Kirmizi sayim cizgisi cubuklarin rahat secilebildigi bolgede olmali.
- ROI icinde cubuklar yeterince parlak ve ayiklanabilir olmali.
- Ayni cubuk birden fazla kez "SAYILDI" etiketine dusuyorsa cift sayim vardir.
- Cubuklar cizgiyi gectigi halde sayilmiyorsa, ebat ayari veya cizgi konumu yeniden
  ayarlanmalidir.

## 6. Hangi durumda YOLO dusunulmeli?

Asagidaki durumlarda YOLO tabanli tespit daha uygun olabilir:

- Arka plan cikariyor ama cubuklarin gorunum kosullari cok sik degisiyorsa
- Parlaklik, duman, yansima veya kirli lens nedeniyle threshold tabanli maske cok
  kararsizsa
- Ayni sahnede cubuk disi benzer parlak nesneler coksa

Ancak once bu surum canli kamera akisinda test edilmelidir. Eger sorun esas olarak
tespit kalitesinden geliyorsa, o zaman YOLO'ya gecis ikinci adim olarak planlanabilir.

## 7. Ozet

Bu PR ile asil olarak su sey cozuldu:

- Sayim artik dusuk FPS hissine veya tek karelik cizgi kesisimine bu kadar bagimli degil.
- Takip, hizli akista daha dayanikli.
- Eski hayalet track'lerin yeni cubuklarla karismasi engellendi.

Beklenen sonuc, normal akis hizinda daha dogru ve daha stabil cubuk sayimidir.
