# hakedis

Kalıp planından (**DWG / DXF / PDF**) **eleman bazlı kırık ölçü metrajı** üreten
açık kaynak sistem. Üç boyutlu model kurmaya gerek yoktur; doğrudan çizimin
kendisinden okur.

Her ölçü, denetlenebilir parçalar zinciri olarak tutulur — çıktı yalnızca bir
toplam değil, o toplamın **nereden geldiğini gösteren kırık ölçü cetvelidir**.

```
S01    Kolon betonu 0.30/0.60          0.513 m3   A=0.1800 m2 x H=2.85 m
P1     Perde betonu t=0.25             2.494 m3   L=3.500 x t=0.25 x H=2.85
        1. parça: (2.63, 1.63) -> (4.50, 1.63) = 1.875 m
        2. parça: (2.63, 1.63) -> (2.63, 3.25) = 1.625 m
K101   Kiriş betonu 0.25/0.50          0.998 m3   b=0.25 x (h-t)=0.35 x L=11.400
        Brüt eksen boyu 12.300 m, mesnet düşümü 0.900 m
        1. açıklık: (0.15, 0.00) -> (5.85, 0.00) = 5.700 m
        2. açıklık: (6.15, 0.00) -> (11.85, 0.00) = 5.700 m
```

## Ne yapar

| Eleman | Tespit | Hesaplanan |
|---|---|---|
| **Kolon** | Kapalı kesit → en küçük dönmüş dikdörtgen (dönük kolonlarda da doğru) | Beton `A×H`, kalıp `çevre×H` − saplanan kiriş yüzleri |
| **Perde** | Karşılıklı yüz eşlemesiyle **orta eksen**; L/T/U perdelerde köşe kırılımı bulunur | Beton `L×t×H`, kalıp `2×L×H` + baş kalıpları |
| **Kiriş** | Kapalı poligon *veya* iki paralel çizgi; **mesnetlerde kırılıp net açıklıklara** bölünür | Beton `b×(h−t)×L`, kalıp alt + 2 yan |
| **Döşeme** | Köşe koordinatlarından Gauss alanı, boşluklar düşülür | Beton `A×t`, tabla kalıbı − (kiriş+kolon+perde ayak izi **birleşimi**) |
| **Merdiven** | Plan izdüşümü kapalı alanı | Beton `A×k×t`, kalıp `A×k` — `k` rıht/basamaktan veya doğrudan |

İsteğe bağlı (yapılandırmadan açılır) ek kurallar:

- **Yaklaşık demir (donatı):** `donati.aktif` ile her elemanın beton satırı
  yanına `kg` satırı eklenir; katsayılar ofis ortalamanızdan (`kg/m³`).
- **Guseli/dişli ve mantar (kirişsiz) döşeme:** `doseme.tip` ile beton hacmine
  özel kural uygulanır; çıktıya elle kontrol uyarısı düşer.
- **Merdiven eğim katsayısı:** `merdiven.riht/basamak` verilirse
  `k = √(1+(rıht/basamak)²)` uygulanır.

Kritik iki nokta doğru kurgulanmıştır:

- **Net açıklık:** kiriş boyu aks-aks değil, mesnet yüzünden mesnet yüzüne ölçülür.
- **Çifte düşüm yok:** döşeme kalıbından düşülen kiriş ve kolon ayak izleri
  *birleşim* alanı olarak hesaplanır, kesişimleri iki kez düşülmez.

## Kurulum

```bash
git clone <bu-depo> && cd hakedis
pip install -e .           # komut satırı arayüzü
pip install -e ".[web]"    # gerekirse görsel arayüz (web + masaüstü)
hakedis dogrula            # bağımlılıkları kontrol et
```

Görsel arayüz için FastAPI/uvicorn/pywebview kurulur; bunlar yalnızca
`hakedis web` ve `hakedis masaustu` komutlarında gerekir.

DXF ve PDF için ek bir şey gerekmez. **DWG** okumak için bir dönüştürücü lazım:

```bash
sudo apt install libredwg-tools     # GNU LibreDWG (GPLv3, açık kaynak) — önerilen
brew install libredwg               # macOS
```

Kurulu değilse `hakedis` bunu açıkça söyler; çizimi CAD'den `DXF R2013` olarak
kaydetmek de her zaman çalışan bir yoldur.

Kullanılan bileşenlerin tamamı açık kaynak ve ücretsizdir:
[ezdxf](https://ezdxf.mozman.at/) (MIT), [shapely](https://shapely.readthedocs.io/) (BSD),
[pdfplumber](https://github.com/jsvine/pdfplumber) (MIT), openpyxl (MIT), numpy (BSD),
[GNU LibreDWG](https://www.gnu.org/software/libredwg/) (GPLv3, harici süreç olarak çağrılır).

## Kullanım

```bash
# 1. Denemek için örnek plan üret
hakedis ornek deneme.dxf
hakedis metraj deneme.dxf

# 2. Kendi çiziminizle: önce katmanları görün
hakedis katmanlar plan.dwg

# 3. Ofis ayarlarınızı oluşturup katman adlarınızı girin
hakedis config-yaz --cikti ofis.yml

# 4. Metrajı çıkarın
hakedis metraj plan.dwg --config ofis.yml \
    --kat "3. Normal Kat" --kat-yuksekligi 3.20 --doseme-kalinligi 0.15

# 5. Çok katlı / çok paftalı iş için
hakedis toplu gir.dxf kat1.dxf kat2.dxf \
    --kat-adlari "Giriş Kat" "1. Normal Kat" "2. Normal Kat"
hakedis toplu plan.pdf --paftalar "1:Giriş,2:1.Kat,3:2.Kat" --config ofis.yml
```

## Görsel arayüz (web + masaüstü)

Sistemin iki yüzü aynı tek sayfa arayüzünü paylaşır; ikisi de yerel bir
sunucu başlatır (`127.0.0.1`), çiziminiz makinenizden çıkmaz ve internet
bağlantısı gerekmez:

```bash
hakedis web                 # varsayılan tarayıcıda açar
hakedis masaustu            # yerli masaüstü penceresi (webview)
```

Arayüzün bölümleri:

- **Metraj:** dosyayı sürükleyip bırakın; kat adı/yüksekliği, donatı,
  döşeme tipi, merdiven eğimi seçin. Özet kartları, kırık ölçü cetveli,
  **kontrol paftası** (SVG) ve uyarılar tek ekranda; Excel/JSON/SVG indirilir.
- **Toplu metraj:** kat dosyalarını tek tek ekleyin; kat özeti tablosu ve
  ortak cetvel.
- **PDF incele:** paftadaki renk/kalınlık dökümü ve hazır `renk_esleme`
  YAML şablonu.
- **Ayarlar:** hızlı form veya gelişmiş YAML editörü — `config-yaz` ile
  aynı yapılandırma, arayüzden yönetilir.

Masaüstü penceresi için macOS'ta `pywebview` (WKWebView), Windows'ta
WebView2, Linux'ta WebKitGTK kullanılır; `pywebview` kurulu değilse
`hakedis masaustu` arayüzü otomatik olarak tarayıcıda açar.

## Çıktılar

- `plan.metraj.xlsx` — Özet / Metraj Cetveli / **Kırık Ölçü** / Elemanlar / Uyarılar
- `plan.metraj.kontrol.svg` — **kontrol paftası**
- `--json` ile makine okunur çıktı (başka sisteme aktarım için)
- `toplu` için `plan.toplu.xlsx` — **Kat Ozeti** / Metraj Cetveli / Kırık Ölçü / Elemanlar / Uyarılar

### Kontrol paftası

Otomatik metrajda en büyük risk, yanlış tespit edilen bir elemanın fark
edilmeden cetvele girmesidir. SVG kontrol paftası sistemin çizimi **nasıl
anladığını** gösterir: her eleman tipine göre boyanır, adı ve kesiti yazılır,
perde/kiriş orta eksenleri kırılım noktalarıyla üstüne çizilir.

Teslim etmeden önce üç şeyi doğrulayın:

1. Her kolon/perde/kiriş boyanmış mı — atlanan var mı?
2. Renkler doğru mu — kolon perde sayılmış mı?
3. Kesikli eksen çizgileri elemanın ortasından geçiyor mu?

Düşük güvenle tespit edilen elemanlar adının yanında `!` ile, otomatik
adlandırılanlar `*` ile işaretlenir; hepsi "Uyarılar" sayfasına da düşer.

## Yapılandırma

`hakedis config-yaz` ile üretilen YAML'da düzenlemeniz gerekenler:

```yaml
birim: cm                      # DXF'te $INSUNITS varsa o kullanılır

kat:
  kat_yuksekligi: 3.00
  doseme_kalinligi: 0.15

katmanlar:                     # KENDİ katman adlarınızı buraya (regex)
  kolon:  ['^KOLON', '^S-KOL']
  perde:  ['^PERDE']
  kiris:  ['^KIRIS', '^KİRİŞ']
  doseme: ['^DOSEME', '^DÖŞEME']
  yoksay: ['^AKS', '^ÖLÇÜ', '^DONATI']

metraj:                        # ofis pratiğinize göre açıp kapatın
  kiris_betonu_doseme_dusumu: true
  doseme_kalibindan_mesnet_dus: true

doseme:                        # özel döşeme tipleri (yaklaşık kurallar)
  tip: normal                  # normal | guseli | mantar
  guseli_hacim_katsayisi: 1.35
  mantar_kolon_ustu_artisi: 0.05
  mantar_kolon_baslik_alani: 1.00

merdiven:                      # eğim katsayısı: k = √(1+(rıht/basamak)²)
  riht: 0.175
  basamak: 0.28
  kalinlik: 0.14

donati:                        # YAKLAŞIK demir metrajı (beton m3 başına kg)
  aktif: false
  katsayilar:
    kolon: 110
    perde: 90
    kiris: 120
    doseme: 95
    merdiven: 70

pozlar:                        # kendi birim fiyat pozlarınız
  kolon_beton: "16.058/1-K"
  demir: "18.001"
```

Etiket okuma `K101 25/50`, `S01 30x60`, `P1 25`, `TD=15`, `K-12 (30/70)`
biçimlerini tanır; `0.25/0.50` gibi metre cinsinden yazılmış kesitleri de
ayırt eder. Kendi biçiminiz farklıysa `etiket.desenler` altına regex ekleyin.

## PDF'ten metraj

PDF'te katman yoktur, bu yüzden iki şeyi dışarıdan vermeniz gerekir:

```bash
hakedis pdf-incele plan.pdf        # paftadaki renkleri ve sayfa boyutunu gör
```

Çıkan renkleri `ofis.yml` içinde eşleyin:

```yaml
pdf:
  renk_esleme:
    "#ff0000": kolon
    "#0000ff": kiris
    "#808080": doseme
```

Ölçek için pafta ölçeğini verebilirsiniz, ama **iki nokta kalibrasyonu daha
güvenilirdir** (pafta ölçekli basılmamış olabilir). Boyunu bildiğiniz bir aks
aralığını PDF puntosu cinsinden ölçüp:

```bash
hakedis metraj plan.pdf --config ofis.yml --kalibre 340.5:6.00
```

Yalnızca **vektörel** PDF'ler okunabilir. Taranmış (görüntü) paftada çizgi
verisi yoktur; sistem bu durumda sessizce yanlış sonuç üretmek yerine açık
hata verir.

## Sınırlar

Bilerek yapılmayanlar — metraja güvenebilmeniz için açıkça yazılmıştır:

- **Donatı metrajı yoktur.** Sistem beton/demir planından donatı çizimini
  okumaz. `donati.aktif` ile beton hacmi üzerinden **katsayı esaslı yaklaşık**
  demir (kg) üretilebilir; bu değer kontrol paftası değil, ön büyüklük
  hesabıdır.
- **Merdiven** plan izdüşümünden hesaplanır; eğim katsayısı rıht/basamaktan
  uygulanır ama tüm plan alanına (sahanlıklar dahil) uygulandığı için
  yaklaşıktır, düşük güvenle işaretlenir.
- **Guseli/dişli döşeme** ve **kirişsiz döşeme (mantar)** için katsayı esaslı
  yaklaşık kurallar vardır; gerçek diş/guse geometrisi okunmaz, elle kontrol
  gerekir.
- **Eğrisel elemanlar** için özel kural yoktur; bunlar yaklaşık çıkar.
- Tek pafta tek çalışmada işlenir. Çok katlı iş için `toplu` komutu (çoklu
  dosya veya çok sayfalı PDF) her katı `--kat-adlari` / `--paftalar` ile
  adlandırıp ortak Excel ve JSON üretir.

Sistem çıktısı **kontrol edilmiş metraj değil, kontrol edilecek metrajdır.**
Kontrol paftasını ve Uyarılar sayfasını okumadan hakedişe girmeyin.

## Test

```bash
pip install -e ".[test]"
pytest -q          # 106 test: geometri, etiket, uçtan uca DXF/PDF, yeni özellikler + web API
```

Uçtan uca testlerdeki beklenen değerler elle hesaplanmıştır, böylece metraj
formüllerinin sessizce değişmesi engellenir.

## Lisans

MIT. (LibreDWG harici bir süreç olarak çağrılır; kendi GPLv3 lisansına tabidir.)
