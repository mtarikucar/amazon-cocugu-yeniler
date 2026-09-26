# Amazon Çocuğu Yeniler — v2.0.0

Kaide dahil **160 mm**, pim–yuva montajlı **20 parçalı** güncel STL seti. Gözleri kafayla bütün olan alternatif kafa aynı ZIP'e eklenmiştir.

**[Tüm STL'leri tek ZIP indir](models/amazon-cocugu-160mm-stl-v2.0.0.zip)** · [GitHub sürümü](https://github.com/mtarikucar/amazon-cocugu-yeniler/releases/tag/v2.0.0) · [Montaj kılavuzu](docs/v2.0.0/MONTAJ.md)

![160 mm modelin güncel görünümü](docs/v2.0.0/images/front.png)

## ZIP içeriği

- `STL/`: 20 parçalı ana figür seti.
- `Alternatif_Kafa/`: gözleri ayrılmamış, tek parça kafa. `15_Kafa`, `16_Sol_Goz` ve `17_Sag_Goz` yerine kullanılır; bu seçenekle figür **18 parçadan** oluşur.
- `Gecme_Testi/`: 4 isteğe bağlı tolerans testi STL'si.
- Türkçe kullanım açıklaması ve SHA256 dosya doğrulama listesi.

Toplam **21 model STL'si + 4 test STL'si** bulunur. Alternatif kafayla standart kafa/gözleri aynı figürde birlikte kullanmayın.

## Bu sürümde

Pelerin hasarı onarıldı; saç, bere, kafa ve kıyafet sınırları elle düzeltilen model üzerinden korundu. Zırh elbiseden ayrı, iki el ve iki göz bağımsız parçalardır. Kalkan gövdesi, metal çember ve arma ayrı hazırlanmıştır. Montaj yolları ve pim–yuva bağlantıları düzenlenmiştir. Kaşlar ve kirpikler kafanın üzerinde kalır. Desen kabartıları bu montaj sürümünde korunmuştur.

STL'ler mm cinsindedir ve ortak montaj konumlarında, desteksiz verilir. Dilimleyicide her baskı parçasını uygun yönde yerleştirip destekleyin; ölçeği %100 tutun.

## Doğrulama

20 ana STL'nin tamamı tekrar içe aktarılarak tek kapalı bileşen, tutarlı yüz yönü ve sıfır alanlı üçgen bulunmaması açısından kontrol edildi. 190 parça çifti ve belirtilen montaj sırasındaki 73 hareketli/sabit çift toplam 10.893 konumda denetlendi; 0,001 mm³ sayısal eşik üzerinde çakışma bulunmadı. Alternatif kafa ayrıca kapalı tek parça ve mevcut saç/bere/boyun bağlantılarıyla uyumlu olarak kontrol edildi.

[Kontrol özeti](reports/v2.0.0/Ozet.json) · [STL kontrolleri](reports/v2.0.0/STL_Dogrulama.json) · [Alternatif kafa kontrolü](reports/v2.0.0/butun-gozlu-kafa.json)

Fiziksel baskı denenmedi. 200 adet üretimden önce kendi reçine ve kürleme ayarlarınızla geçme kuponlarını ve bir tam prototipi deneyin. Pim ve yuvaları boya/astar birikmesinden koruyun.

## Önceki sürüm

Eski 150 mm / 17 parçalı model dosyaları arşiv olarak korunur. [Önceki modelin açıklaması](docs/onceki-150mm-surum.md). Eski parçalarla bu 160 mm setin parçalarını karıştırmayın; güncel indirme yukarıdaki v2.0.0 ZIP'idir.
