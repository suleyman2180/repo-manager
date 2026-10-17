# 🚀 repo-manager (GitHub Yönetim Paneli)

[![Lisans: MIT](https://img.shields.io/badge/Lisans-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Bash](https://img.shields.io/badge/Bash-4.0+-4EAA25.svg?logo=gnu-bash&logoColor=white)](https://www.gnu.org/software/bash/)
[![GUI](https://img.shields.io/badge/Aray%C3%BCz-Tkinter%20(Koyu%20Tema)-0e639c.svg)]()
[![Testler](https://img.shields.io/badge/Testler-9%20Ge%C3%A7ti-brightgreen.svg)]()

**repo-manager**, GitHub CLI (`gh`) ve Git operasyonlarını hem **modern bir masaüstü grafik arayüzü (GUI)** hem de **gelişmiş bir terminal aracı (CLI)** ile zahmetsizce yönetmenizi sağlayan hepsi-bir-arada bir geliştirici aracıdır.

---

## ✨ Öne Çıkan Özellikler

- **Çift Modlu Çalışma:** İster şık ve modern koyu temalı masaüstü arayüzünü (`repo_manager_gui.py`), isterseniz terminal dostu zengin bash betiğini (`repo-manager.sh`) kullanın.
- **🛡️ Dahili Güvenlik Kalkanı:**
  - `dangerous()` filtresi: Sistem kök dizinlerinin (`/`, `~`, `/Desktop`, `/tmp` vb.) yanlışlıkla repo olarak yüklenmesini engeller.
  - Hassas Dosya Taraması: `.env`, `.pem`, `*.key`, `credentials`, `secrets` gibi dosyaları push öncesi tespit edip uyarır.
  - 100MB Büyük Dosya Koruması: GitHub'ın reddedeceği devasa dosyaları önceden yakalar.
- **📜 Akıllı Lisans Sihirbazı (Yeni):**
  - Yeni repo oluşturulurken dizinde lisans dosyası yoksa otomatik olarak devreye girer.
  - **MIT**, **Apache 2.0** veya **GNU GPL v3** lisanslarından birini seçtirerek yazar adı ve güncel yıl ile projeye `LICENSE` dosyası oluşturur.
- **⚡ Asenkron ve Donmayan Arayüz:** Arka planda `threading` ve `Queue` kuyruk mimarisi sayesinde uzun süren git işlemlerinde bile pencere donmaz.
- **Kuru Çalıştırma (`--dry-run`):** Gerçek commit ve push yapmadan önce işlemlerin simülasyonunu izleme imkanı.
- **Masaüstü Entegrasyonu:** Linux, macOS ve Windows sistemlerine özel tek tıkla masaüstü başlatıcıları oluşturur.

---

## 🛠️ Sistem Gereksinimleri

- **Python 3.8+** (ve `python3-tk`)
- **Git**
- **GitHub CLI (`gh`)** (`gh auth login` ile GitHub hesabınıza giriş yapılmış olmalıdır)

---

## 📦 Kurulum

Proje dizininde tek bir komutla etkileşimli kurulum sihirbazını çalıştırabilirsiniz:

```bash
python3 kurulum.py
```

### Kurulum Seçenekleri:
```bash
python3 kurulum.py            # Etkileşimli kurulum (bağımlılıkları ve ayarları sorar)
python3 kurulum.py -y         # Tüm sorulara otomatik 'Evet' yanıtı verir
python3 kurulum.py --no-deps  # Bağımlılık denetimini atlar
python3 kurulum.py --kaldir   # Oluşturulan masaüstü kısayollarını kaldırır
```

Kurulum tamamlandığında masaüstünüzde **GitHub Manager** (GUI) ve **GitHub Manager (Terminal)** kısayolları hazır olacaktır.

---

## 🖥️ Kullanım Rehberi

### 1. Grafik Arayüzü (GUI) Başlatma
```bash
python3 repo_manager_gui.py
```
Sekmeler:
- **Yeni Repo:** Yerel bir dizinden GitHub'da public/private repo oluşturur, README ve Lisans ekler.
- **Repoyu Güncelle:** Seçilen yerel klasör veya dosyadaki değişiklikleri `main` dalına commit ve push eder.
- **Klonla:** GitHub repolarını veya URL'lerini yerel diske indirir.
- **Issue:** Repolardaki issue'ları listeler veya yeni hata kaydı açar.
- **Pull Request:** Açık PR'ları listeler veya yerel daldan yeni PR oluşturur.
- **Gist:** Dosyalarınızdan hızlıca gizli veya genel Gist üretir.
- **Ayarlar:** Varsayılan Git adı, e-posta, varsayılan proje dizini ve görünürlük ayarları (`~/.gh_panel_config`).

### 2. Terminal (CLI) Başlatma
```bash
./repo-manager.sh
```
Parametreli hızlı çalıştırma:
```bash
./repo-manager.sh --repo "kullanici/projem" --dir "~/projeler/projem" --msg "Yeni özellik"
./repo-manager.sh --dry-run   # Test modunda çalıştır
```

---

## 🧪 Testlerin Çalıştırılması

Proje çekirdek modülleri, güvenlik mekanizmaları ve lisans şablonları için birim testleri içerir:

```bash
python3 -m unittest discover -s tests -v
```

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında açık kaynak olarak lisanslanmıştır.
