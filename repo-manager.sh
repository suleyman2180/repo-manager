#!/usr/bin/env bash
set -Eeuo pipefail

# -----------------------------------------------------------------------------
# Konfigürasyon Dosyası Yolu ve Varsayılanlar
# -----------------------------------------------------------------------------
CONFIG_FILE="$HOME/.gh_panel_config"

KAYITLI_GIT_NAME=""
KAYITLI_GIT_EMAIL=""
VARSAYILAN_DIR=""
VARSAYILAN_VISIBILITY="1" # 1: Public, 2: Private

konfigurasyon_yukle() {
  if [[ -f "$CONFIG_FILE" ]]; then
    # Dosyadaki değişkenleri içe aktar
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
  fi
}

# Değeri tek tırnak içine güvenle alır (GUI sürümüyle ortak dosya biçimi)
tek_tirnakla() {
  local s="${1:-}"
  s="${s//\'/\'\\\'\'}"
  printf "'%s'" "$s"
}

konfigurasyon_kaydet() {
  {
    echo "# GitHub Yönetim Paneli Kayıtlı Ayarları"
    echo "KAYITLI_GIT_NAME=$(tek_tirnakla "${KAYITLI_GIT_NAME:-}")"
    echo "KAYITLI_GIT_EMAIL=$(tek_tirnakla "${KAYITLI_GIT_EMAIL:-}")"
    echo "VARSAYILAN_DIR=$(tek_tirnakla "${VARSAYILAN_DIR:-}")"
    echo "VARSAYILAN_VISIBILITY=$(tek_tirnakla "${VARSAYILAN_VISIBILITY:-1}")"
  } > "$CONFIG_FILE"
  echo -e "${GREEN}✓ Ayarlar '$CONFIG_FILE' dosyasına kaydedildi.${NC}"
}

# -----------------------------------------------------------------------------
# Geçici dosya ve dizin temizliği (Trap EXIT)
# -----------------------------------------------------------------------------
TMP_DIR=""
temizlik() {
  if [[ -n "${TMP_DIR:-}" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
  if [[ -n "${INPUTRC_DOSYASI:-}" && -f "$INPUTRC_DOSYASI" ]]; then
    rm -f "$INPUTRC_DOSYASI"
  fi
  if [[ -n "${STTY_ESKI:-}" ]]; then
    stty "$STTY_ESKI" 2>/dev/null || true
  fi
}
trap temizlik EXIT

# -----------------------------------------------------------------------------
# Hata yakalama fonksiyonu (Trap ERR)
# -----------------------------------------------------------------------------
hata_yakala() {
  local exit_code="${1:-1}"
  local line_no="${2:-0}"
  if [[ "$exit_code" == "99" || "$exit_code" == "130" ]]; then
    return 0
  fi
  echo -e "\n${RED:-}[HATA]${NC:-} $line_no. satırda bir komut başarısız oldu (Çıkış Kodu: $exit_code)." >&2
}
trap 'hata_yakala $? $LINENO' ERR

# -----------------------------------------------------------------------------
# Renk Tanımlamaları
# -----------------------------------------------------------------------------
if [[ -t 1 ]]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BLUE='\033[0;34m'
  CYAN='\033[0;36m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  RED=''
  GREEN=''
  YELLOW=''
  BLUE=''
  CYAN=''
  BOLD=''
  NC=''
fi

# -----------------------------------------------------------------------------
# Küresel Değişkenler
# -----------------------------------------------------------------------------
DRY_RUN=0
AUTO_YES=0
OPT_REPO=""
OPT_MSG=""
OPT_PRIVATE=0
OPT_DIR=""
SECILEN_GLOBAL_REPO=""

# -----------------------------------------------------------------------------
# Terminal Kontrolü: Ctrl+C paneli KAPATMAZ, Ctrl+S paneli kapatır
#  - Ctrl+C: çalışan işlemi/soruyu iptal eder, ana menüye döner.
#  - Ctrl+S: her yerde (soru sırasında bile) panelden çıkar.
# -----------------------------------------------------------------------------
ANA_PID=$$
KAPAT_ISARETI="__PANEL_KAPAT__"
STTY_ESKI=""
INPUTRC_DOSYASI=""
SIGINT_ALINDI=0

terminal_hazirla() {
  [[ -t 0 && -t 1 ]] || return 0
  STTY_ESKI=$(stty -g 2>/dev/null || true)
  stty -ixon 2>/dev/null || true        # Ctrl+S terminali dondurmasın
  INPUTRC_DOSYASI=$(mktemp "${TMPDIR:-/tmp}/ghpanel_inputrc.XXXXXX")
  {
    if [[ -f /etc/inputrc ]]; then echo '$include /etc/inputrc'; fi
    if [[ -f "${INPUTRC:-$HOME/.inputrc}" ]]; then echo "\$include ${INPUTRC:-$HOME/.inputrc}"; fi
    printf '"\\C-s": "\\C-a\\C-k%s\\C-m"\n' "$KAPAT_ISARETI"
  } > "$INPUTRC_DOSYASI"
  export INPUTRC="$INPUTRC_DOSYASI"
  trap 'SIGINT_ALINDI=1' INT            # Ctrl+C betiği sonlandırmasın
}

cikis_istegi() {
  echo -e "\n${GREEN}Güle güle! (for idris enes yiğit)${NC}" >&2
  if [[ "$BASHPID" == "$ANA_PID" ]]; then
    exit 0
  fi
  exit 99   # alt kabuktan ana döngüye "çık" sinyali
}

# 'read' sarmalayıcı: Ctrl+C -> işlemi iptal et, Ctrl+S -> çık.
read() {
  local args=("$@") vars=() i=0 n=$#
  while (( i < n )); do
    case "${args[i]}" in
      -p|-d|-n|-N|-t|-u|-i|-a) i=$((i+2)); continue ;;
      -*) ;;
      *) vars+=("${args[i]}") ;;
    esac
    i=$((i+1))
  done

  local extra=()
  if [[ -n "$INPUTRC_DOSYASI" && -t 0 ]]; then extra=(-e); fi

  local rc=0
  builtin read "${extra[@]}" "$@" || rc=$?

  if (( rc > 128 )); then              # Ctrl+C ile kesildi
    if (( ${#vars[@]} > 0 )); then
      local v
      for v in "${vars[@]}"; do printf -v "$v" ''; done
    fi
    echo >&2
    if [[ "$BASHPID" != "$ANA_PID" ]]; then
      exit 130                          # çalışan işlem iptal -> menüye dön
    fi
    echo -e "${YELLOW}[Ctrl+C] Panel kapatılmaz. Çıkmak için Ctrl+S veya 0/q.${NC}" >&2
    return 0
  fi
  if (( rc != 0 )); then return "$rc"; fi

  if (( ${#vars[@]} > 0 )); then
    local first="${vars[0]}"
    if [[ "${!first:-}" == "$KAPAT_ISARETI" ]]; then cikis_istegi; fi
  fi
  return 0
}

# -----------------------------------------------------------------------------
# Yardım Mesajı
# -----------------------------------------------------------------------------
kullanim() {
  cat << EOF
Kullanım: $(basename "$0") [SEÇENEKLER]

GitHub Yönetim Paneli - (for idris enes yiğit)
Git ve GitHub CLI (gh) komutlarını yönetmenizi sağlayan araç.

Seçenekler:
  -n          Kuru çalıştırma (dry-run): Değişiklik yapmadan adımları yazdırır.
  -r REPO     Hedef repo adı veya 'kullanici/repo' (ör: my-repo veya org/my-repo).
  -m MESAJ    Commit mesajı.
  -p          Yeni repoyu gizli (private) olarak ayarla (Varsayılan: public).
  -d DİZİN    İşlem yapılacak dizin veya dosya yolu.
  -y          Onay sorularını otomatik geç (Hassas dosya uyarısı hariç).
  -h          Bu yardım mesajını göster.

Hiçbir argüman verilmezse etkileşimli panel açılır.
EOF
  exit 0
}

# -----------------------------------------------------------------------------
# Argüman Ayrıştırma (getopts)
# -----------------------------------------------------------------------------
while getopts "nr:m:pd:yh" opt; do
  case "$opt" in
    n) DRY_RUN=1 ;;
    r) OPT_REPO="${OPTARG:-}" ;;
    m) OPT_MSG="${OPTARG:-}" ;;
    p) OPT_PRIVATE=1 ;;
    d) OPT_DIR="${OPTARG:-}" ;;
    y) AUTO_YES=1 ;;
    h) kullanim ;;
    *) kullanim ;;
  esac
done
shift $((OPTIND -1))

# -----------------------------------------------------------------------------
# Yardımcı Komut Çalıştırıcı (Dry-Run)
# -----------------------------------------------------------------------------
calistir() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo -e "${YELLOW}[DRY-RUN] Komut:${NC} $*"
  else
    "$@"
  fi
}

# -----------------------------------------------------------------------------
# Bağımlılık ve Yetki Kontrolü
# -----------------------------------------------------------------------------
kontrol_et_bagimliliklar() {
  if ! command -v git &>/dev/null; then
    echo -e "${RED}Hata: 'git' yüklü değil.${NC}" >&2
    exit 1
  fi
  if ! command -v gh &>/dev/null; then
    echo -e "${RED}Hata: 'gh' (GitHub CLI) yüklü değil.${NC}" >&2
    exit 1
  fi
  if ! gh auth status &>/dev/null; then
    echo -e "${RED}Hata: 'gh' CLI oturumu açık değil. Lütfen 'gh auth login' yapın.${NC}" >&2
    exit 1
  fi
  if [[ "$DRY_RUN" -eq 0 ]]; then
    gh auth setup-git &>/dev/null || true
  fi
}

# -----------------------------------------------------------------------------
# Zenity Kullanılabilirlik
# -----------------------------------------------------------------------------
zenity_kullanilabilir_mi() {
  if command -v zenity &>/dev/null && [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
    return 0
  fi
  return 1
}

# -----------------------------------------------------------------------------
# Dosya / Klasör Seçim Diyaloğu
# -----------------------------------------------------------------------------
secim_yap() {
  local mod="${1:-directory}"
  local baslik="${2:-Seçim Yapın}"
  local secilen_yol=""

  if zenity_kullanilabilir_mi; then
    if [[ "$mod" == "directory" ]]; then
      secilen_yol=$(zenity --file-selection --directory --title="$baslik" 2>/dev/null || true)
    else
      secilen_yol=$(zenity --file-selection --title="$baslik" 2>/dev/null || true)
    fi
  fi

  if [[ -z "$secilen_yol" ]]; then
    echo -e "\n${BLUE}[SEÇİM] $baslik${NC}" >&2
    if [[ -n "$VARSAYILAN_DIR" && -d "$VARSAYILAN_DIR" ]]; then
      echo -e "${CYAN}Kayıtlı Varsayılan Dizin: $VARSAYILAN_DIR${NC}" >&2
    fi
    if [[ "$mod" == "file" ]]; then
      echo -e "${CYAN}Tavsiye: Dosyayı sürükleyip terminale bırakabilirsiniz.${NC}" >&2
    fi
    read -r -e -p "Lütfen tam yolu girin (Boş bırakırsanız varsayılan kullanılır): " secilen_yol
    if [[ -z "$secilen_yol" && -n "$VARSAYILAN_DIR" ]]; then
      secilen_yol="$VARSAYILAN_DIR"
    fi
  fi

  secilen_yol="${secilen_yol//\'/}"
  secilen_yol="${secilen_yol//\"/}"
  secilen_yol="${secilen_yol/#\~/$HOME}"

  echo "$secilen_yol"
}

# -----------------------------------------------------------------------------
# Onay Alma
# -----------------------------------------------------------------------------
onay_al() {
  local mesaj="${1:-Devam edilsin mi?}"
  local varsayilan="${2:-H}"

  if [[ "$AUTO_YES" -eq 1 ]]; then return 0; fi

  local p_prompt="[e/H]"
  [[ "$varsayilan" == "E" ]] && p_prompt="[E/h]"

  read -r -p "$mesaj $p_prompt: " cevap
  cevap=$(echo "${cevap:-}" | tr '[:upper:]' '[:lower:]')

  if [[ -z "$cevap" ]]; then
    [[ "$varsayilan" == "E" ]] && return 0 || return 1
  fi

  [[ "$cevap" == "e" || "$cevap" == "evet" ]] && return 0 || return 1
}

# -----------------------------------------------------------------------------
# Git Kullanıcı Bilgisi (Kayıt Mekanizması Entegre Edildi)
# -----------------------------------------------------------------------------
git_kullanici_kontrol() {
  local user_name
  local user_email
  user_name=$(git config user.name 2>/dev/null || echo "")
  user_email=$(git config user.email 2>/dev/null || echo "")

  if [[ -z "$user_name" ]]; then
    if [[ -n "$KAYITLI_GIT_NAME" ]]; then
      user_name="$KAYITLI_GIT_NAME"
      calistir git config --local user.name "$user_name"
    else
      echo -e "${YELLOW}Git 'user.name' tanımlı değil.${NC}"
      read -r -p "Git kullanıcı adınızı girin (bir defalık kayıt): " user_name
      if [[ -n "$user_name" ]]; then
        KAYITLI_GIT_NAME="$user_name"
        calistir git config --global user.name "$user_name"
        konfigurasyon_kaydet
      fi
    fi
  fi

  if [[ -z "$user_email" ]]; then
    if [[ -n "$KAYITLI_GIT_EMAIL" ]]; then
      user_email="$KAYITLI_GIT_EMAIL"
      calistir git config --local user.email "$user_email"
    else
      echo -e "${YELLOW}Git 'user.email' tanımlı değil.${NC}"
      read -r -p "Git e-posta adresinizi girin (bir defalık kayıt): " user_email
      if [[ -n "$user_email" ]]; then
        KAYITLI_GIT_EMAIL="$user_email"
        calistir git config --global user.email "$user_email"
        konfigurasyon_kaydet
      fi
    fi
  fi
}

# -----------------------------------------------------------------------------
# Tehlikeli Dizin ve Git Root Kontrolü
# -----------------------------------------------------------------------------
tehlikeli_dizin_mi() {
  local hedef_dir="${1:-}"
  local abs_dir
  abs_dir=$(cd "$hedef_dir" 2>/dev/null && pwd -P || echo "$hedef_dir")
  local tehlikeliler=("$HOME" "$HOME/Downloads" "$HOME/Masaüstü" "$HOME/Desktop" "/" "/tmp" "/var" "/usr" "/etc")
  for t in "${tehlikeliler[@]}"; do
    [[ "$abs_dir" == "$t" ]] && return 0
  done
  return 1
}

git_init_guvenlik_kontrolu() {
  local hedef_dizin="${1:-}"
  if tehlikeli_dizin_mi "$hedef_dizin"; then
    echo -e "${RED}Hata: '$hedef_dizin' sistem/kullanıcı kök dizinidir. 'git init' yapılamaz!${NC}" >&2
    return 1
  fi
  if [[ ! -d "$hedef_dizin/.git" ]]; then
    local root_check
    root_check=$(cd "$hedef_dizin" && git rev-parse --show-toplevel 2>/dev/null || echo "")
    if [[ -n "$root_check" && "$root_check" != "$hedef_dizin" ]]; then
      echo -e "${YELLOW}Uyarı: Üst dizinde Git deposu mevcut: $root_check${NC}"
      if ! onay_al "Yine de bu alt dizinde yeni bir Git deposu başlatılsın mı?" "H"; then
        return 1
      fi
    fi
  fi
  return 0
}

# -----------------------------------------------------------------------------
# Hassas Dosya Taraması
# -----------------------------------------------------------------------------
hassas_dosya_tara() {
  local is_public="${1:-1}"
  local bulunanlar=()
  while IFS= read -r -d '' dosya; do
    bulunanlar+=("$dosya")
  done < <(find . -maxdepth 4 \( -name ".env" -o -name "*.pem" -o -name "*.key" -o -name "*id_rsa*" -o -name "credentials*" -o -name "secrets*" \) -not -path '*/.*/*' -print0 2>/dev/null || true)

  if [[ ${#bulunanlar[@]} -gt 0 ]]; then
    echo -e "\n${RED}================ UYARI: HASSAS DOSYALAR TESPİT EDİLDİ ================${NC}"
    [[ "$is_public" -eq 1 ]] && echo -e "${RED}${BOLD}DİKKAT: Public repoya hassas dosya yüklemek CİDDİ GÜVENLİK RİSKİDİR!${NC}"
    echo -e "${YELLOW}Bulunan dosyalar:${NC}"
    for f in "${bulunanlar[@]}"; do echo -e "  - $f"; done
    echo "1) Dosyaları .gitignore'a ekle ve devam et"
    echo "2) İşlemi İPTAL ET"
    read -r -p "Seçiminiz (1/2) [Varsayılan: 2]: " secim
    secim="${secim:-2}"
    if [[ "$secim" == "1" ]]; then
      for f in "${bulunanlar[@]}"; do
        local temiz_f="${f#./}"
        if ! grep -qxF "$temiz_f" .gitignore 2>/dev/null; then
          echo "$temiz_f" >> .gitignore
          echo -e "${GREEN}'$temiz_f' .gitignore dosyasına eklendi.${NC}"
        fi
      done
    else
      echo -e "${RED}İşlem iptal edildi.${NC}"
      return 1
    fi
  fi
  return 0
}

# -----------------------------------------------------------------------------
# .gitignore ve Büyük Dosya Kontrolü
# -----------------------------------------------------------------------------
gitignore_ve_buyuk_dosya_kontrol() {
  if [[ ! -f ".gitignore" ]]; then
    local yaygin_klasorler=()
    for d in node_modules __pycache__ .venv dist build .idea .vscode; do
      [[ -d "$d" ]] && yaygin_klasorler+=("$d")
    done
    if [[ ${#yaygin_klasorler[@]} -gt 0 ]]; then
      echo -e "${YELLOW}Şu klasörler tespit edildi ancak .gitignore yok:${NC} ${yaygin_klasorler[*]}"
      if onay_al "Temel bir .gitignore oluşturulsun mu?" "E"; then
        for k in "${yaygin_klasorler[@]}"; do echo "$k/" >> .gitignore; done
        echo ".DS_Store" >> .gitignore
        echo -e "${GREEN}.gitignore oluşturuldu.${NC}"
      fi
    fi
  fi

  local buyuk_dosyalar=()
  while IFS= read -r -d '' b_dosya; do
    buyuk_dosyalar+=("$b_dosya")
  done < <(find . -maxdepth 5 -type f -size +100M -not -path '*/.git/*' -print0 2>/dev/null || true)

  if [[ ${#buyuk_dosyalar[@]} -gt 0 ]]; then
    echo -e "\n${RED}================ UYARI: 100 MB ÜSTÜ DOSYA TESPİT EDİLDİ ================${NC}"
    for bf in "${buyuk_dosyalar[@]}"; do
      local sz
      sz=$(du -h "$bf" | cut -f1)
      echo -e "  - $bf ($sz)"
    done
    if ! onay_al "GitHub sınırı 100MB'dır. Devam etmek istiyor musunuz?" "H"; then
      return 1
    fi
  fi
  return 0
}

# -----------------------------------------------------------------------------
# Repo Adı Doğrulama
# -----------------------------------------------------------------------------
repo_adi_dogrula() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    echo -e "${RED}Hata: Repo adı boş olamaz.${NC}" >&2; return 1
  fi
  if [[ ! "$name" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo -e "${RED}Hata: Repo adı yalnızca harf, rakam, nokta, alt çizgi ve tire içerebilir.${NC}" >&2; return 1
  fi
  return 0
}

# -----------------------------------------------------------------------------
# Remote Origin Çakışma
# -----------------------------------------------------------------------------
remote_origin_ayarla() {
  local hedef_url="${1:-}"
  if git remote | grep -q "^origin$"; then
    local mevcut_url
    mevcut_url=$(git remote get-url origin 2>/dev/null || echo "")
    if [[ -n "$mevcut_url" && "$mevcut_url" != "$hedef_url" ]]; then
      echo -e "${YELLOW}Mevcut 'origin' farklı bir adrese bağlı:${NC} \nEski: $mevcut_url \nYeni: $hedef_url"
      if onay_al "'origin' güncellensin mi?" "E"; then
        calistir git remote set-url origin "$hedef_url"
      else
        return 1
      fi
    fi
  else
    calistir git remote add origin "$hedef_url"
  fi
  return 0
}

# -----------------------------------------------------------------------------
# Commit, Push, Özet
# -----------------------------------------------------------------------------
ozet_goster() {
  local yol="${1:-}"
  local repo="${2:-}"
  local dal="${3:-}"
  local msg="${4:-}"
  echo -e "\n${BLUE}================ İŞLEM ÖZETİ ================${NC}"
  echo -e "  ${BOLD}Yol/Dizin:${NC} $yol\n  ${BOLD}Hedef Repo:${NC} $repo\n  ${BOLD}Hedef Dal:${NC}  $dal\n  ${BOLD}Mesaj:${NC}      $msg"
  echo -e "${BOLD}Değişiklikler:${NC}"
  git status --short || true
  echo -e "${BLUE}============================================${NC}\n"
}

commit_olustur() {
  local add_target="${1:-.}"
  local commit_msg="${2:-Güncelleme}"
  git_kullanici_kontrol
  calistir git add "$add_target"
  if git diff --cached --quiet; then
    echo -e "${YELLOW}Commit edilecek değişiklik yok.${NC}"
    return 0
  fi
  calistir git commit -m "$commit_msg"
  echo -e "${GREEN}✓ Commit başarıyla oluşturuldu.${NC}"
}

push_et() {
  local target_branch="${1:-main}"
  echo -e "${BLUE}Uzak sunucu kontrol ediliyor...${NC}"
  calistir git fetch origin "$target_branch" &>/dev/null || true

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo -e "${YELLOW}[DRY-RUN] 'git push -u origin $target_branch' çalıştırılacak.${NC}"
    return 0
  fi

  if git push -u origin "$target_branch"; then
    echo -e "${GREEN}✓ Başarıyla yüklendi!${NC}"
  else
    echo -e "\n${YELLOW}Push başarısız oldu (Çakışma olabilir).${NC}"
    echo "1) Rebase yap  2) Merge yap  3) İptal et"
    read -r -p "Seçim (1/2/3): " push_secim
    case "${push_secim:-3}" in
      1)
        if git pull origin "$target_branch" --rebase; then
          git push -u origin "$target_branch"
          echo -e "${GREEN}✓ Rebase sonrası başarıyla yüklendi!${NC}"
        else
          echo -e "${RED}Rebase çakışması! İptal ediliyor...${NC}"
          git rebase --abort || true
        fi ;;
      2)
        if git pull origin "$target_branch"; then
          git push -u origin "$target_branch"
        else
          echo -e "${RED}Merge çakışması! Lütfen elle çözün.${NC}"
        fi ;;
      *) echo -e "${YELLOW}İptal edildi.${NC}" ;;
    esac
  fi
}

# -----------------------------------------------------------------------------
# Kullanıcıdan Repo Seçme
# -----------------------------------------------------------------------------
kullanici_repo_sec() {
  SECILEN_GLOBAL_REPO=""
  echo -e "${CYAN}Repolarınız yükleniyor...${NC}" >&2
  local repo_list=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && repo_list+=("$line")
  done < <(gh repo list --limit 100 --json nameWithOwner -q '.[].nameWithOwner' 2>/dev/null || true)

  if [[ ${#repo_list[@]} -eq 0 ]]; then
    echo -e "${RED}Erişilebilir repo bulunamadı.${NC}" >&2
    return 1
  fi

  local i=1 r sec
  for r in "${repo_list[@]}"; do
    printf '%3d) %s\n' "$i" "$r" >&2
    i=$((i+1))
  done
  printf '%3d) İptal\n' "$i" >&2

  while true; do
    read -r -p "İşlem yapılacak repoyu seçin (sayı girin): " sec
    if [[ "$sec" =~ ^[0-9]+$ ]] && (( 10#$sec >= 1 && 10#$sec <= i )); then
      if (( 10#$sec == i )); then
        echo -e "${YELLOW}İptal edildi.${NC}" >&2
        return 0
      fi
      SECILEN_GLOBAL_REPO="${repo_list[$((10#$sec - 1))]}"
      return 0
    fi
    echo -e "${RED}Geçersiz seçim.${NC}" >&2
  done
}

# -----------------------------------------------------------------------------
# Modül 1: Yeni Repo (Kayıtlı Görünürlük Tercihi Kullanılıyor)
# -----------------------------------------------------------------------------
yeni_repo_olustur() {
  local target_path="$OPT_DIR"
  [[ -z "$target_path" ]] && target_path=$(secim_yap "directory" "Proje Dizinini Seçin")
  [[ -z "$target_path" ]] && return 0

  if [[ ! -d "$target_path" ]]; then echo -e "${RED}Dizin bulunamadı.${NC}"; return 0; fi
  cd "$target_path" || { echo -e "${RED}Dizine geçilemedi.${NC}"; return 0; }

  git_init_guvenlik_kontrolu "$target_path" || return 0

  local repo_name="$OPT_REPO"
  while [[ -z "$repo_name" ]]; do
    read -r -p "Yeni Repo Adı: " repo_name
    repo_adi_dogrula "$repo_name" || repo_name=""
  done

  local owner=""
  if [[ "$AUTO_YES" -eq 0 && -z "$OPT_REPO" ]]; then
    echo -e "\n1) Kişisel hesabım\n2) Bir Organizasyon"
    read -r -p "Seçiminiz (1/2): " owner_choice
    [[ "${owner_choice:-1}" == "2" ]] && read -r -p "Organizasyon adı: " owner
  fi
  local full_repo_spec="${owner:+$owner/}$repo_name"

  if gh repo view "$full_repo_spec" &>/dev/null; then
    echo -e "${YELLOW}Uyarı: '$full_repo_spec' zaten mevcut! Güncelleme moduna geçiliyor...${NC}"
    OPT_REPO="$full_repo_spec"
    mevcut_repo_guncelle
    return 0
  fi

  local vis_flag="--public"; local is_public=1
  if [[ "$OPT_PRIVATE" -eq 1 ]]; then 
    vis_flag="--private"; is_public=0
  elif [[ "$AUTO_YES" -eq 0 ]]; then
    # Kayıtlı varsayılan görünürlük varsa o kullanılır
    local def_vis="${VARSAYILAN_VISIBILITY:-1}"
    read -r -p "Görünürlük (1: public, 2: private) [Varsayılan: $def_vis]: " vis_choice
    vis_choice="${vis_choice:-$def_vis}"
    [[ "$vis_choice" == "2" ]] && { vis_flag="--private"; is_public=0; }
  fi

  local desc=""; local add_readme=0
  if [[ "$AUTO_YES" -eq 0 && "$DRY_RUN" -eq 0 ]]; then
    read -r -p "Açıklama (Opsiyonel): " desc
    [[ ! -f "README.md" ]] && onay_al "README.md oluşturulsun mu?" "E" && add_readme=1
  fi

  hassas_dosya_tara "$is_public" || return 0
  gitignore_ve_buyuk_dosya_kontrol || return 0

  if [[ "$add_readme" -eq 1 ]]; then
    echo "# $repo_name" > README.md
    echo -e "${GREEN}README.md oluşturuldu.${NC}"
  fi

  local commit_msg="${OPT_MSG:-"İlk commit"}"
  ozet_goster "$target_path" "$full_repo_spec" "main" "$commit_msg"
  onay_al "Devam edilsin mi?" "H" || return 0

  [[ ! -d ".git" ]] && calistir git init
  calistir git branch -M main
  commit_olustur "." "$commit_msg"

  local create_cmd=(gh repo create "$full_repo_spec" "$vis_flag" --source=. --remote=origin)
  [[ -n "$desc" ]] && create_cmd+=(--description "$desc")

  echo -e "${BLUE}GitHub'da repo oluşturuluyor...${NC}"
  calistir "${create_cmd[@]}"
  push_et "main"
}

# -----------------------------------------------------------------------------
# Modül 2: Mevcut Repo Güncelleme
# -----------------------------------------------------------------------------
mevcut_repo_guncelle() {
  local full_repo="$OPT_REPO"
  if [[ -z "$full_repo" ]]; then
    kullanici_repo_sec
    full_repo="$SECILEN_GLOBAL_REPO"
    [[ -z "$full_repo" ]] && return 0
  fi

  local sadece_repo_adi="${full_repo##*/}"

  local target_path="$OPT_DIR"; local working_dir=""; local add_target="."
  if [[ -z "$target_path" ]]; then
    echo -e "\n1) Tüm klasör  2) Belirli bir dosya"
    read -r -p "Seçim (1/2) [Vars: 1]: " h_tipi
    h_tipi="${h_tipi:-1}"
    if [[ "$h_tipi" == "2" ]]; then
      target_path=$(secim_yap "file" "Eklenecek / Güncellenecek Dosyayı Seçin")
      [[ -z "$target_path" ]] && return 0

      local dosya_dizini; dosya_dizini=$(dirname "$target_path")
      local dosya_adi; dosya_adi=$(basename "$target_path")

      if tehlikeli_dizin_mi "$dosya_dizini"; then
        working_dir="$dosya_dizini/$sadece_repo_adi"
        echo -e "${YELLOW}Seçilen dosya korumalı dizinde ($dosya_dizini).${NC}"
        echo -e "${CYAN}Otomatik olarak '$working_dir' klasörü oluşturulup dosya içine alınıyor...${NC}"
        mkdir -p "$working_dir"
        cp "$target_path" "$working_dir/$dosya_adi"
        add_target="$dosya_adi"
      else
        working_dir="$dosya_dizini"
        add_target="$dosya_adi"
      fi
    else
      target_path=$(secim_yap "directory" "Proje Klasörünü Seçin")
      [[ -z "$target_path" ]] && return 0
      working_dir="$target_path"
    fi
  else
    if [[ -f "$target_path" ]]; then 
      local dosya_dizini; dosya_dizini=$(dirname "$target_path")
      local dosya_adi; dosya_adi=$(basename "$target_path")
      if tehlikeli_dizin_mi "$dosya_dizini"; then
        working_dir="$dosya_dizini/$sadece_repo_adi"
        mkdir -p "$working_dir"
        cp "$target_path" "$working_dir/$dosya_adi"
        add_target="$dosya_adi"
      else
        working_dir="$dosya_dizini"
        add_target="$dosya_adi"
      fi
    else 
      working_dir="$target_path"
    fi
  fi

  cd "$working_dir" || { echo -e "${RED}Dizine geçilemedi.${NC}"; return 0; }
  git_init_guvenlik_kontrolu "$working_dir" || return 0

  local target_branch
  target_branch=$(gh repo view "$full_repo" --json defaultBranchRef -q .defaultBranchRef.name 2>/dev/null || echo "main")
  [[ -z "$target_branch" ]] && target_branch=$(git branch --show-current 2>/dev/null || echo "main")

  local remote_url
  remote_url=$(gh repo view "$full_repo" --json url -q .url 2>/dev/null || echo "https://github.com/$full_repo.git")
  if git remote get-url origin 2>/dev/null | grep -q "^git@"; then
    remote_url=$(gh repo view "$full_repo" --json sshUrl -q .sshUrl 2>/dev/null || echo "git@github.com:$full_repo.git")
  fi

  local is_private; is_private=$(gh repo view "$full_repo" --json isPrivate -q .isPrivate 2>/dev/null || echo "false")
  local is_public=1; [[ "$is_private" == "true" ]] && is_public=0

  hassas_dosya_tara "$is_public" || return 0
  gitignore_ve_buyuk_dosya_kontrol || return 0

  local commit_msg="${OPT_MSG:-"Güncelleme"}"
  ozet_goster "$working_dir" "$full_repo" "$target_branch" "$commit_msg"
  onay_al "Devam edilsin mi?" "H" || return 0

  [[ ! -d ".git" ]] && { calistir git init; calistir git branch -M "$target_branch"; }
  remote_origin_ayarla "$remote_url" || return 0
  commit_olustur "$add_target" "$commit_msg"
  push_et "$target_branch"
}

# -----------------------------------------------------------------------------
# Modül 3: Repo Klonla
# -----------------------------------------------------------------------------
repo_klonla() {
  echo -e "\n${CYAN}--- Repo Klonla ---${NC}"
  read -r -p "Klonlanacak Repo (Kullanici/Repo veya URL): " klon_repo
  [[ -z "$klon_repo" ]] && return 0
  local h_dizin
  h_dizin=$(secim_yap "directory" "Klonlanacak Hedef Dizini Seçin")
  [[ -z "$h_dizin" ]] && return 0
  cd "$h_dizin" || { echo -e "${RED}Dizine geçilemedi.${NC}"; return 0; }
  echo -e "${BLUE}Klonlanıyor...${NC}"
  calistir gh repo clone "$klon_repo" || true
  echo -e "${GREEN}İşlem tamamlandı.${NC}"
}

# -----------------------------------------------------------------------------
# Modül 4: Issue Yönetimi
# -----------------------------------------------------------------------------
issue_yonetimi() {
  echo -e "\n${CYAN}--- Issue Yönetimi ---${NC}"
  kullanici_repo_sec
  [[ -z "$SECILEN_GLOBAL_REPO" ]] && return 0

  echo "1) Açık Issue'ları Listele"
  echo "2) Yeni Issue Oluştur"
  read -r -p "Seçiminiz (1/2): " i_secim
  case "${i_secim:-1}" in
    1) calistir gh issue list --repo "$SECILEN_GLOBAL_REPO" || true ;;
    2) calistir gh issue create --repo "$SECILEN_GLOBAL_REPO" || true ;;
    *) echo -e "${RED}Geçersiz seçim.${NC}" ;;
  esac
}

# -----------------------------------------------------------------------------
# Modül 5: Pull Request Yönetimi
# -----------------------------------------------------------------------------
pr_yonetimi() {
  echo -e "\n${CYAN}--- Pull Request Yönetimi ---${NC}"
  kullanici_repo_sec
  [[ -z "$SECILEN_GLOBAL_REPO" ]] && return 0

  echo "1) Açık PR'ları Listele"
  echo "2) Yeni PR Oluştur (Bulunduğunuz dizindeki repodan)"
  read -r -p "Seçiminiz (1/2): " pr_secim
  case "${pr_secim:-1}" in
    1) calistir gh pr list --repo "$SECILEN_GLOBAL_REPO" || true ;;
    2) 
       echo -e "${YELLOW}Not: Çalışma dizininiz ilgili git deposu olmalıdır.${NC}"
       calistir gh pr create --repo "$SECILEN_GLOBAL_REPO" || true 
       ;;
    *) echo -e "${RED}Geçersiz seçim.${NC}" ;;
  esac
}

# -----------------------------------------------------------------------------
# Modül 6: Gist Oluşturma
# -----------------------------------------------------------------------------
gist_olustur() {
  echo -e "\n${CYAN}--- Gist Oluştur ---${NC}"
  local g_dosya
  g_dosya=$(secim_yap "file" "Gist İçin Dosya Seçin")
  [[ -z "$g_dosya" || ! -f "$g_dosya" ]] && { echo -e "${RED}Geçerli bir dosya seçilmedi.${NC}"; return 0; }
  
  local desc; read -r -p "Gist Açıklaması: " desc
  echo -e "${BLUE}Gist oluşturuluyor...${NC}"
  if [[ -n "$desc" ]]; then
    calistir gh gist create "$g_dosya" -d "$desc" || true
  else
    calistir gh gist create "$g_dosya" || true
  fi
}

# -----------------------------------------------------------------------------
# Modül 7: Ayarları Yönet (Yeni Eklendi)
# -----------------------------------------------------------------------------
ayarlari_yonet() {
  echo -e "\n${CYAN}=== Kayıtlı Ayarlar ve Tercihler ===${NC}"
  echo -e "1) Git Kullanıcı Adı  : ${KAYITLI_GIT_NAME:-'(Tanımlanmamış)'}"
  echo -e "2) Git E-posta        : ${KAYITLI_GIT_EMAIL:-'(Tanımlanmamış)'}"
  echo -e "3) Varsayılan Dizin   : ${VARSAYILAN_DIR:-'(Tanımlanmamış)'}"
  echo -e "4) Varsayılan Görünürlük: $( [[ "$VARSAYILAN_VISIBILITY" == "2" ]] && echo "Private" || echo "Public" )"
  echo -e "--------------------------------------------------------"
  echo "1) Ayarları Düzenle / Güncelle"
  echo "2) Tüm Kayıtlı Ayarları Sıfırla (Dosyayı Sil)"
  echo "0) Geri Dön"
  read -r -p "Seçiminiz: " a_secim

  case "${a_secim:-0}" in
    1)
      read -r -p "Git Kullanıcı Adı [Mevcut: $KAYITLI_GIT_NAME]: " new_name
      [[ -n "$new_name" ]] && KAYITLI_GIT_NAME="$new_name"
      
      read -r -p "Git E-posta Adresi [Mevcut: $KAYITLI_GIT_EMAIL]: " new_email
      [[ -n "$new_email" ]] && KAYITLI_GIT_EMAIL="$new_email"

      read -r -p "Varsayılan Dizin Yolu [Mevcut: $VARSAYILAN_DIR]: " new_dir
      [[ -n "$new_dir" ]] && VARSAYILAN_DIR="$new_dir"

      read -r -p "Varsayılan Repo Görünürlüğü (1: Public, 2: Private) [Mevcut: $VARSAYILAN_VISIBILITY]: " new_vis
      [[ -n "$new_vis" ]] && VARSAYILAN_VISIBILITY="$new_vis"

      konfigurasyon_kaydet
      ;;
    2)
      if onay_al "Kayıtlı konfigürasyon dosyası silinsin mi?" "H"; then
        rm -f "$CONFIG_FILE"
        KAYITLI_GIT_NAME=""
        KAYITLI_GIT_EMAIL=""
        VARSAYILAN_DIR=""
        VARSAYILAN_VISIBILITY="1"
        echo -e "${GREEN}Ayarlar sıfırlandı.${NC}"
      fi
      ;;
    *) return 0 ;;
  esac
}

# -----------------------------------------------------------------------------
# Ana Menü Paneli (Etkileşimli Döngü)
# -----------------------------------------------------------------------------
# Bir menü eylemini alt kabukta çalıştırır: Ctrl+C yalnızca o eylemi iptal eder,
# hata olursa panel kapanmaz, Ctrl+S (kod 99) paneli kapatır.
eylem_calistir() {
  local rc=0
  trap - ERR
  set +e
  ( set -e; "$@" )
  rc=$?
  set -e
  trap 'hata_yakala $? $LINENO' ERR

  if [[ "$rc" -eq 99 ]]; then
    exit 0
  fi
  if [[ "$rc" -eq 130 || "$rc" -eq 2 ]]; then
    echo -e "\n${YELLOW}İşlem iptal edildi (Ctrl+C). Ana menüye dönülüyor.${NC}"
  fi

  # Alt kabukta değişen ayarlar dosyadan yeniden okunur
  KAYITLI_GIT_NAME=""
  KAYITLI_GIT_EMAIL=""
  VARSAYILAN_DIR=""
  VARSAYILAN_VISIBILITY="1"
  konfigurasyon_yukle
  return 0
}

panel_menu() {
  terminal_hazirla
  local secim=""
  while true; do
    echo -e "\n${BLUE}${BOLD}=== GitHub Yönetim Paneli (for idris enes yiğit) ===${NC}"
    echo -e "1) Yeni Repo Oluştur ve Yükle"
    echo -e "2) Mevcut Repoyu Güncelle (Commit & Push)"
    echo -e "3) Repo Klonla"
    echo -e "4) Issue (Sorun) Yönetimi"
    echo -e "5) Pull Request (PR) Yönetimi"
    echo -e "6) Gist Oluştur"
    echo -e "7) Ayarları Yönet (Kayıtlı Bilgileri Güncelle/Sil)"
    echo -e "0) Çıkış   ${CYAN}(Ctrl+S: her yerden çıkış | Ctrl+C: işlemi iptal)${NC}"
    echo -e "--------------------------------------------------------"
    secim=""
    read -r -p "Seçiminiz: " secim

    case "${secim:-}" in
      "") continue ;;
      1) eylem_calistir yeni_repo_olustur ;;
      2) eylem_calistir mevcut_repo_guncelle ;;
      3) eylem_calistir repo_klonla ;;
      4) eylem_calistir issue_yonetimi ;;
      5) eylem_calistir pr_yonetimi ;;
      6) eylem_calistir gist_olustur ;;
      7) eylem_calistir ayarlari_yonet ;;
      0|q|Q) cikis_istegi ;;
      *) echo -e "${RED}Geçersiz seçim, lütfen tekrar deneyin.${NC}" ;;
    esac
  done
}

# -----------------------------------------------------------------------------
# Başlangıç (Main)
# -----------------------------------------------------------------------------
main() {
  konfigurasyon_yukle
  kontrol_et_bagimliliklar

  if [[ -n "$OPT_REPO" && -n "$OPT_DIR" ]]; then
    if gh repo view "$OPT_REPO" &>/dev/null; then mevcut_repo_guncelle; else yeni_repo_olustur; fi
    exit 0
  fi

  panel_menu
}

main "$@"
