#!/usr/bin/env python3
"""GitHub Yönetim Paneli

Yaptıkları:
  1. Bağımlılıkları kontrol eder (tkinter, git, gh) ve eksikse kurmayı önerir.
  2. 'gh auth login' yapılmış mı bakar, gerekirse başlatır.
  3. Masaüstüne kısayol oluşturur:
       - GitHub Manager (GUI)       -> repo_manager_gui.py
       - GitHub Manager (Terminal)  -> repo-manager.sh   (Linux/macOS)

Kullanım:
  python3 kurulum.py            # etkileşimli kurulum
  python3 kurulum.py -y         # sorulara otomatik "evet"
  python3 kurulum.py --no-deps  # bağımlılık kontrolünü atla
  python3 kurulum.py --kaldir   # oluşturulan kısayolları sil

Kurulum ayrıca git adı/e-postası, varsayılan klasör ve repo görünürlüğünü sorar
(~/.gh_panel_config), bitince yıldız (star) isteyip proje sayfasını tarayıcıda açar.
"""
import base64
import os
import platform
import shlex
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

try:  # Windows konsolunda Türkçe karakterler
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

BASE = Path(__file__).resolve().parent
GUI = BASE / "repo_manager_gui.py"
CLI = BASE / "repo-manager.sh"
APP_GUI = "GitHub Manager"
APP_CLI = "GitHub Manager (Terminal)"
OS = platform.system()
AUTO_YES = "-y" in sys.argv or "--yes" in sys.argv
REPO = "suleyman2180/repo-manager"
REPO_URL = f"https://github.com/{REPO}"
CONFIG_FILE = Path.home() / ".gh_panel_config"
CONFIG_KEYS = ("KAYITLI_GIT_NAME", "KAYITLI_GIT_EMAIL", "VARSAYILAN_DIR", "VARSAYILAN_VISIBILITY")


# ----------------------------------------------------------------- yardımcılar
def ok(msg):
    print(f"[BAŞARILI] {msg}")


def warn(msg):
    print(f"[UYARI]   {msg}")


def err(msg):
    print(f"[HATA]    {msg}")


def info(msg):
    print(f"[BİLGİ]   {msg}")


def ask_yes(question, default=True):
    if AUTO_YES:
        return True
    suffix = "[E/h]" if default else "[e/H]"
    try:
        ans = input(f"{question} {suffix}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not ans:
        return default
    return ans in ("e", "evet", "y", "yes")


def run(cmd, **kw):
    return subprocess.run(cmd, **kw)


def out_of(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        return r.returncode, r.stdout.strip()
    except OSError:
        return 1, ""


# ------------------------------------------------------------ bağımlılık kontrolü
def have_tk():
    r = subprocess.run([sys.executable, "-c", "import tkinter"], capture_output=True)
    return r.returncode == 0


def pkg_install_hint(what):
    hints = {
        "Linux": {"tk": "sudo apt install python3-tk", "git": "sudo apt install git",
                  "gh": "sudo apt install gh   (veya https://cli.github.com)"},
        "Darwin": {"tk": "brew install python-tk", "git": "brew install git", "gh": "brew install gh"},
        "Windows": {"tk": "Python'u 'tcl/tk and IDLE' seçeneğiyle yeniden kurun (python.org)",
                    "git": "winget install --id Git.Git", "gh": "winget install --id GitHub.cli"},
    }
    return hints.get(OS, {}).get(what, "")


def try_install(what):
    """Eksik paketi işletim sistemine göre kurmayı dener."""
    cmd = None
    if OS == "Linux" and shutil.which("apt-get"):
        pkg = {"tk": "python3-tk", "git": "git", "gh": "gh"}[what]
        cmd = ["sudo", "apt-get", "install", "-y", pkg]
    elif OS == "Darwin" and shutil.which("brew"):
        pkg = {"tk": "python-tk", "git": "git", "gh": "gh"}[what]
        cmd = ["brew", "install", pkg]
    elif OS == "Windows" and shutil.which("winget") and what in ("git", "gh"):
        pkg = {"git": "Git.Git", "gh": "GitHub.cli"}[what]
        cmd = ["winget", "install", "--id", pkg, "-e"]
    if not cmd:
        return False
    info("Çalıştırılıyor: " + " ".join(cmd))
    try:
        return run(cmd).returncode == 0
    except OSError:
        return False


def check_deps():
    print("\n--- Bağımlılık kontrolü ---")
    names = {"tk": "tkinter (python3-tk)", "git": "git", "gh": "gh (GitHub CLI)"}

    def is_missing(m):
        return not have_tk() if m == "tk" else not shutil.which(m)

    missing = [m for m in ("tk", "git", "gh") if is_missing(m)]
    for m in list(missing):
        warn(f"Eksik: {names[m]}")
        if ask_yes(f"{names[m]} kurulsun mu?"):
            try_install(m)
        if is_missing(m):
            warn(f"{names[m]} kurulamadı. Elle kurulum: {pkg_install_hint(m)}")
        else:
            ok(f"{names[m]} hazır.")
            missing.remove(m)
    if not missing:
        ok("tkinter, git ve gh hazır.")

    if shutil.which("gh"):
        if out_of(["gh", "auth", "status"])[0] != 0:
            warn("GitHub CLI oturumu açık değil.")
            if ask_yes("Şimdi 'gh auth login' başlatılsın mı?"):
                run(["gh", "auth", "login"])
            if out_of(["gh", "auth", "status"])[0] != 0:
                warn("Oturum açılmadı. Paneli kullanmadan önce 'gh auth login' çalıştırın.")
            else:
                ok("GitHub oturumu açık.")
        else:
            ok("GitHub oturumu açık.")
    return missing


# ---------------------------------------------------------------- masaüstü yolu
def desktop_dir():
    home = Path.home()
    if OS == "Windows":
        rc, out = out_of(["powershell", "-NoProfile", "-Command",
                          "[Environment]::GetFolderPath('Desktop')"])
        if rc == 0 and out:
            return Path(out)
        return home / "Desktop"
    if OS == "Linux" and shutil.which("xdg-user-dir"):
        rc, out = out_of(["xdg-user-dir", "DESKTOP"])
        if rc == 0 and out and Path(out) != home and Path(out).is_dir():
            return Path(out)
    for name in ("Desktop", "Masaüstü"):  # Türkçe sistemlerde klasör adı "Masaüstü"
        if (home / name).is_dir():
            return home / name
    d = home / "Desktop"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ------------------------------------------------------------------------ Linux
def de_arg(s):
    """.desktop Exec= için argüman tırnaklama (freedesktop belirtimi)."""
    out = ""
    for ch in str(s):
        if ch == "\\":
            out += "\\\\\\\\"
        elif ch in '"`$':
            out += "\\" + ch
        elif ch == "%":
            out += "%%"
        else:
            out += ch
    return f'"{out}"'


def linux_entry(name, comment, args, terminal):
    exec_line = " ".join(de_arg(a) for a in args)
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Version=1.0\n"
        f"Name={name}\n"
        f"Comment={comment}\n"
        f"Exec={exec_line}\n"
        f"Path={BASE}\n"
        f"Terminal={'true' if terminal else 'false'}\n"
        f"Icon={'utilities-terminal' if terminal else 'applications-development'}\n"
        "Categories=Development;\n"
    )


def linux_shortcuts(desktop):
    made = []
    apps = Path.home() / ".local" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    items = [(APP_GUI, "GitHub Yönetim Paneli (arayüz)", [sys.executable, str(GUI)], False)]
    if CLI.exists():
        items.append((APP_CLI, "GitHub Yönetim Paneli (terminal)", ["bash", str(CLI)], True))
    for name, comment, args, term in items:
        content = linux_entry(name, comment, args, term)
        for folder in (desktop, apps):
            path = folder / f"{name}.desktop"
            path.write_text(content, encoding="utf-8")
            path.chmod(0o755)
            if folder == desktop and shutil.which("gio"):  # GNOME: "güvenilir" işaretle
                subprocess.run(["gio", "set", str(path), "metadata::trusted", "true"],
                               capture_output=True)
            made.append(path)
        ok(f"Linux kısayolu (.desktop) oluşturuldu: {desktop / (name + '.desktop')}")
    return made


# ---------------------------------------------------------------------- Windows
def windows_shortcuts(desktop):
    made = []
    pyw = Path(sys.executable).with_name("pythonw.exe")
    target = pyw if pyw.exists() else Path(sys.executable)
    lnk = desktop / f"{APP_GUI}.lnk"

    def q(s):
        return "'" + str(s).replace("'", "''") + "'"

    ps = (
        "$s=(New-Object -COM WScript.Shell).CreateShortcut(" + q(lnk) + "); "
        "$s.TargetPath=" + q(target) + "; "
        "$s.Arguments=" + q('"' + str(GUI) + '"') + "; "
        "$s.WorkingDirectory=" + q(BASE) + "; "
        "$s.Description='GitHub Yönetim Paneli'; $s.Save()"
    )
    enc = base64.b64encode(ps.encode("utf-16-le")).decode()
    run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc], check=True)
    ok(f"Windows kısayolu (.lnk) oluşturuldu: {lnk}")
    made.append(lnk)
    if CLI.exists():
        info("Terminal sürümü (repo-manager.sh) Windows'ta Git Bash veya WSL ile elle çalıştırılır.")
    return made


# ------------------------------------------------------------------------ macOS
def mac_shortcuts(desktop):
    made = []
    items = [(APP_GUI, f"exec {shlex.quote(sys.executable)} {shlex.quote(str(GUI))}")]
    if CLI.exists():
        items.append((APP_CLI, f"exec bash {shlex.quote(str(CLI))}"))
    for name, cmd in items:
        path = desktop / f"{name}.command"
        path.write_text(f"#!/bin/bash\ncd {shlex.quote(str(BASE))}\n{cmd}\n", encoding="utf-8")
        path.chmod(0o755)
        ok(f"macOS kısayolu (.command) oluşturuldu: {path}")
        made.append(path)
    return made


# ------------------------------------------------------------------ ayarlar
def load_config():
    """~/.gh_panel_config dosyasını (repo-manager.sh / GUI ile ortak) kod çalıştırmadan okur."""
    cfg = {"KAYITLI_GIT_NAME": "", "KAYITLI_GIT_EMAIL": "", "VARSAYILAN_DIR": "",
           "VARSAYILAN_VISIBILITY": "1"}
    try:
        text = CONFIG_FILE.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return cfg
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if key in cfg:
            try:
                parts = shlex.split(val)
                cfg[key] = parts[0] if parts else ""
            except ValueError:
                pass
    return cfg


def save_config(cfg):
    lines = ["# GitHub Yönetim Paneli Kayıtlı Ayarları"]
    lines += [f"{k}={shlex.quote(str(cfg.get(k, '')))}" for k in CONFIG_KEYS]
    CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ask_text(question, default=""):
    try:
        shown = f" [{default}]" if default else ""
        ans = input(f"{question}{shown}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return ans or default


def ask_settings():
    """Panelin ihtiyaç duyduğu bilgileri kurulumda sorar ve kaydeder."""
    print("\n--- Panel ayarları ---")
    cfg = load_config()
    git_name = out_of(["git", "config", "--global", "user.name"])[1] if shutil.which("git") else ""
    git_mail = out_of(["git", "config", "--global", "user.email"])[1] if shutil.which("git") else ""
    cfg["KAYITLI_GIT_NAME"] = cfg["KAYITLI_GIT_NAME"] or git_name
    cfg["KAYITLI_GIT_EMAIL"] = cfg["KAYITLI_GIT_EMAIL"] or git_mail

    if AUTO_YES:
        info("-y modu: sorular atlandı, mevcut/varsayılan ayarlar kullanılıyor.")
    else:
        info("Boş bırakıp Enter'a basarsanız köşeli parantezdeki değer kullanılır.")
        cfg["KAYITLI_GIT_NAME"] = ask_text("Git kullanıcı adınız", cfg["KAYITLI_GIT_NAME"])
        cfg["KAYITLI_GIT_EMAIL"] = ask_text("Git e-posta adresiniz", cfg["KAYITLI_GIT_EMAIL"])
        while True:
            d = ask_text("Varsayılan proje klasörü (boş = her seferinde sor)", cfg["VARSAYILAN_DIR"])
            d = os.path.expanduser(d)
            if not d or Path(d).is_dir():
                cfg["VARSAYILAN_DIR"] = d
                break
            if ask_yes(f"'{d}' bulunamadı. Oluşturulsun mu?"):
                try:
                    Path(d).mkdir(parents=True, exist_ok=True)
                    cfg["VARSAYILAN_DIR"] = d
                    break
                except OSError as e:
                    warn(f"Klasör oluşturulamadı: {e}")
        while True:
            v = ask_text("Yeni repolar varsayılan olarak (1: public, 2: private)",
                         cfg["VARSAYILAN_VISIBILITY"] or "1")
            if v in ("1", "2"):
                cfg["VARSAYILAN_VISIBILITY"] = v
                break
            warn("Lütfen 1 veya 2 girin.")

    try:
        save_config(cfg)
        ok(f"Ayarlar kaydedildi: {CONFIG_FILE}")
    except OSError as e:
        warn(f"Ayarlar kaydedilemedi: {e}")


# --------------------------------------------------------- star + tarayıcı
def ask_star_and_open():
    print("\n--- Proje sayfası ---")
    # Kullanıcı adına sessizce star verilmez: -y modunda sorulmaz.
    if not AUTO_YES and shutil.which("gh") and out_of(["gh", "auth", "status"])[0] == 0:
        if ask_yes(f"Projeyi beğendiysen GitHub'da ⭐ yıldızlamak ister misin? ({REPO})"):
            rc, _ = out_of(["gh", "api", "-X", "PUT", f"user/starred/{REPO}"])
            if rc == 0:
                ok("Teşekkürler, yıldız verildi! ⭐")
            else:
                warn("Yıldız verilemedi; sayfadan elle verebilirsiniz.")
    elif not AUTO_YES:
        info("Yıldız vermek için sayfada 'Star' düğmesine tıklayabilirsiniz.")
    info(f"Açılıyor: {REPO_URL}")
    try:
        if not webbrowser.open(REPO_URL):
            warn(f"Tarayıcı açılamadı. Adres: {REPO_URL}")
    except Exception:  # noqa: BLE001
        warn(f"Tarayıcı açılamadı. Adres: {REPO_URL}")


# --------------------------------------------------------------------- ana akış
def remove_shortcuts():
    print("\n--- Kısayollar siliniyor ---")
    desktop = desktop_dir()
    n = 0
    for name in (APP_GUI, APP_CLI):
        for ext in (".desktop", ".lnk", ".command"):
            for folder in (desktop, Path.home() / ".local" / "share" / "applications"):
                c = folder / f"{name}{ext}"
                if c.exists():
                    c.unlink()
                    ok(f"Silindi: {c}")
                    n += 1
    if not n:
        info("Silinecek kısayol bulunamadı.")


def kurulum():
    print("=" * 60)
    print(" Merhaba Kuruluma hoş geldin.")
    print(" Sistem tespit ediliyor ve masaüstü kısayolu oluşturuluyor...")
    print("=" * 60)
    print(f" Sistem: {OS} | Python: {sys.version.split()[0]} | Klasör: {BASE}\n")

    if "--kaldir" in sys.argv:
        remove_shortcuts()
        return 0

    if not GUI.exists():
        err(f"'{GUI.name}' bulunamadı. kurulum.py ile aynı klasörde olmalı.")
        return 1
    if OS != "Windows" and CLI.exists():
        CLI.chmod(CLI.stat().st_mode | 0o111)  # çalıştırılabilir yap

    if "--no-deps" not in sys.argv:
        check_deps()

    ask_settings()

    print("\n--- Kısayol oluşturma ---")
    try:
        desktop = desktop_dir()
        if OS == "Windows":
            windows_shortcuts(desktop)
        elif OS == "Darwin":
            mac_shortcuts(desktop)
        elif OS == "Linux":
            linux_shortcuts(desktop)
        else:
            err(f"Desteklenmeyen işletim sistemi: {OS}")
            return 1
    except Exception as e:  # noqa: BLE001
        err(f"Kısayol oluşturulurken bir sorun oluştu: {e}")
        return 1

    print("\nKurulum tamamlandı. Masaüstündeki 'GitHub Manager' kısayoluna çift tıklayın.")
    if OS == "Linux":
        info("Kısayol simgesi uyarı verirse: sağ tık -> 'Başlatmaya İzin Ver' (Allow Launching).")

    ask_star_and_open()
    return 0


if __name__ == "__main__":
    sys.exit(kurulum())
