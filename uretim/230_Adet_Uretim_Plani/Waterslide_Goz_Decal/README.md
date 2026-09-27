# Waterslide göz (iris) decal — 230 adet üretim

200 adet sipariş, %15 fire ile **230 figür**. Standart kafa seti (`15_Kafa` + ayrı `16_Sol_Goz` / `17_Sag_Goz`) için.

## Baskıcıya gönderilecekler

| Dosya | Açıklama |
| --- | --- |
| `GOZ_IRIS_DECAL_A4_BASKI.pdf` | **Asıl baskı dosyası.** A4, vektör, CMYK, %100 ölçek |
| `BASKI_SIPARIS_FORMU.pdf` | Kâğıt, adet, renk, ölçü ve uygulama notları |
| `GOZ_IRIS_DECAL_A4_BASKI.svg` | Aynı tabaka, vektör (RGB) |
| `GOZ_IRIS_DECAL_A4_BASKI_1200dpi.png` | Aynı tabaka, 1200 dpi, şeffaf zemin (yalnız decallar, yazı/cetvel yok) |
| `GOZ_DECAL_MASTER_SOL/SAG.*` | Tek decal master dosyaları (PDF/SVG/PNG) |

- **Kâğıt:** şeffaf (clear) waterslide. Beyaz mürekkep gerekmez; parlama noktaları mürekkepsizdir, alttaki beyaz göz boyası görünür.
- **Adet:** 2 A4 tabaka (1 üretim + 1 yedek). Tabakada 276 SOL + 276 SAĞ (230 + %20 uygulama yedeği) ve 20 ölçek test decalı.
- **Şekil:** decallar daire değildir. Her gözün iris kubbesi, montajda göz kapaklarıyla kesilen görünür bölgeye göre kırpılmıştır; SOL ve SAĞ farklıdır.

## Tam hesap (STL v2.0.0)

| | SOL (16_Sol_Goz) | SAĞ (17_Sag_Goz) |
| --- | --- | --- |
| Kubbe tabanı çapı / yüksekliği | Ø5.31 / 1.03 mm | Ø5.18 / 1.01 mm |
| İris çapı, yüzey boyunca (açınım) | Ø6.28 mm | Ø5.73 mm |
| Decal dış ölçüsü | 6.30 × 5.43 mm | 5.67 × 4.72 mm |
| Görünen iris yüzeyi / decal alanı | 22.8 / 23.2 mm² | 20.6 / 20.7 mm² |
| Film gerilmesi (%5–%95) | −%2 … +%3 | −%3 … +%5 |

Yöntem (`scripts/eye_decal_outline.py`):

1. İris kubbesine küre oturtulur (R ≈ 3.8–3.9 mm, ortalama sapma < 0.01 mm).
2. Kubbe tabanındaki içbükey kıvrım kenarlarına küre üzerinde taban dairesi oturtulur. Sol gözde kıvrım iki yaydan oluştuğu için eksen ve açı birlikte bulunur (yarım açı 42.5°). Sağ gözde tek yay vardır; aynı açı sabit tutulup yalnız eksen oturtulur. Medyan sapma iki gözde de ≈1°.
3. Kubbe yüzeyi 0.04 mm'ye inceltilip ARAP ile düzleme açılır. Ters dönen üçgen yoktur.
4. Montajlı kafa, saç ve bere ile 20°'lik bakış konisinden 9 yönde ışın atılır. Göz kapağının altında kalan yüzey decal dışında bırakılır. Decal kenarı kapak altına 0.15 mm taşar.

Tüm sayılar `goz_konturlari.json` dosyasındadır.

## Yeniden üretme

```bash
unzip models/amazon-cocugu-160mm-stl-v2.0.0.zip -d /tmp/stl
python scripts/eye_decal_outline.py /tmp/stl/STL uretim/230_Adet_Uretim_Plani/Waterslide_Goz_Decal/goz_konturlari.json
python scripts/waterslide_eye_decal.py uretim/230_Adet_Uretim_Plani/Waterslide_Goz_Decal uretim/230_Adet_Uretim_Plani/Waterslide_Goz_Decal/onizleme_figur_uzerinde.png
```

## Dikkat

- Fiziksel baskı denenmedi. Üretimden önce tabakadaki %94–%106 test çiftlerini prototipte deneyin. Decal kubbeye oturmazsa veya kenarda taşarsa ölçeği güncelleyin.
- `Alternatif_Kafa` (gözleri kafayla bütün) kullanılırsa göz geometrisi farklıdır; bu decallar o kafa için hesaplanmadı.
- İris rengi referans görsele göre koyu kahvedir (alta doğru açılır). Renk değişirse `IRIS_STOPS` güncellenip dosyalar yeniden üretilir.
