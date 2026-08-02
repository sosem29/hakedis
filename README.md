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

Kritik iki nokta doğru kurgulanmıştır:

- **Net açıklık:** kiriş boyu aks-aks değil, mesnet yüzünden mesnet yüzüne ölçülür.
- **Çifte düşüm yok:** döşeme kalıbından düşülen kiriş ve kolon ayak izleri
  *birleşim* alanı olarak hesaplanır, kesişimleri iki kez düşülmez.

## Kurulum

```bash
git clone <bu-depo> && cd hakedis
pip install -e .
hakedis dogrula          # bağımlılıkları kontrol et
```

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
```

Çıktılar:

- `plan.metraj.xlsx` — Özet / Metraj Cetveli / **Kırık Ölçü** / Elemanlar / Uyarılar
- `plan.metraj.kontrol.svg` — **kontrol paftası**
- `--json` ile makine okunur çıktı (başka sisteme aktarım için)

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

pozlar:                        # kendi birim fiyat pozlarınız
  kolon_beton: "16.058/1-K"
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

- **Donatı metrajı yoktur.** Sistem kalıp planındaki beton ve kalıp
  miktarlarını çıkarır; demir metrajı kapsam dışıdır.
- **Merdiven** plan izdüşümünden hesaplanır, eğim katsayısı uygulanmaz;
  çıktıda düşük güvenle işaretlenir ve elle kontrol gerektirir.
- **Guseli/dişli döşeme, kirişsiz döşeme (mantar), eğrisel elemanlar** için
  özel kural yoktur; bunlar yaklaşık çıkar.
- Tek kat, tek pafta işlenir. Çok katlı iş için her katı ayrı çalıştırıp
  `--kat` ile adlandırın.

Sistem çıktısı **kontrol edilmiş metraj değil, kontrol edilecek metrajdır.**
Kontrol paftasını ve Uyarılar sayfasını okumadan hakedişe girmeyin.

## Test

```bash
pip install -e ".[test]"
pytest -q          # 77 test: geometri, etiket, uçtan uca DXF ve PDF
```

Uçtan uca testlerdeki beklenen değerler elle hesaplanmıştır, böylece metraj
formüllerinin sessizce değişmesi engellenir.

## Lisans

MIT. (LibreDWG harici bir süreç olarak çağrılır; kendi GPLv3 lisansına tabidir.)
