#!/usr/bin/env python3
"""GitHub Yönetim Paneli - GUI (for idris enes yiğit)

repo-manager.sh betiğinin grafik arayüzlü sürümü.
Gereksinimler: python3-tk, git, gh (GitHub CLI, 'gh auth login' yapılmış olmalı)
Çalıştırma:    python3 repo_manager_gui.py
"""
import fnmatch
import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext
except ImportError:
    sys.exit("tkinter bulunamadı. Kurulum: sudo apt install python3-tk")

HOME = str(Path.home())
SENSITIVE = (".env", "*.pem", "*.key", "*id_rsa*", "credentials*", "secrets*")
COMMON_DIRS = ("node_modules", "__pycache__", ".venv", "dist", "build", ".idea", ".vscode")
REPO_RE = re.compile(r"^[A-Za-z0-9._-]+$")
BIG = 100 * 1024 * 1024
ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


# Koyu tema paleti
BG = "#1e1e1e"        # ana arka plan
BG2 = "#252526"       # sekme / oluk
BG3 = "#2d2d30"       # giriş alanları, düğmeler
FG = "#d4d4d4"        # yazı
MUTED = "#8b8b8b"     # soluk yazı
ACCENT = "#0e639c"    # vurgu (mavi)
ACCENT_H = "#1177bb"  # vurgu üzerine gelince
BORDER = "#3c3c3c"

CONFIG_FILE = Path.home() / ".gh_panel_config"
CONFIG_DEFAULTS = {
    "KAYITLI_GIT_NAME": "",
    "KAYITLI_GIT_EMAIL": "",
    "VARSAYILAN_DIR": "",
    "VARSAYILAN_VISIBILITY": "1",  # 1: Public, 2: Private
}


def load_config():
    """repo-manager.sh ile ortak ~/.gh_panel_config dosyasını okur (kod çalıştırmadan)."""
    cfg = dict(CONFIG_DEFAULTS)
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
        if key not in cfg:
            continue
        try:
            parts = shlex.split(val)
        except ValueError:
            continue
        cfg[key] = parts[0] if parts else ""
    return cfg


def save_config(cfg):
    lines = ["# GitHub Yönetim Paneli Kayıtlı Ayarları"]
    lines += [f"{k}={shlex.quote(str(cfg.get(k, '')))}" for k in CONFIG_DEFAULTS]
    CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


class Abort(Exception):
    """İşlemi kullanıcıya mesaj vererek durdurur."""


def clean(p):
    return os.path.expanduser(p.strip().strip("'\""))


def dangerous(p):
    bad = {os.path.realpath(x) for x in (
        HOME, f"{HOME}/Downloads", f"{HOME}/Masaüstü", f"{HOME}/Desktop",
        "/", "/tmp", "/var", "/usr", "/etc")}
    return os.path.realpath(p) in bad


def walk_files(root, maxdepth, skip):
    """find -maxdepth benzeri dosya gezgini. skip: 'hidden' (gizli klasörler) veya 'git'."""
    root = Path(root)
    for dp, dn, fn in os.walk(root):
        depth = len(Path(dp).relative_to(root).parts)
        dn[:] = [d for d in dn if (not d.startswith(".") if skip == "hidden" else d != ".git")]
        if depth >= maxdepth - 1:
            dn[:] = []
        for f in fn:
            yield Path(dp) / f


def fsize(p):
    try:
        return p.stat().st_size
    except OSError:
        return 0


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("GitHub Yönetim Paneli — for idris enes yiğit")
        self.root.geometry("880x760")
        self.root.minsize(780, 620)
        self.apply_theme()
        self.cfg = load_config()
        self.q = queue.Queue()
        self.busy = False
        self.dry_run = False
        self.base_status = "Başlatılıyor…"
        self.repo_boxes = []
        self.dry_var = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value=self.base_status)
        self.build()
        self.root.after(50, self.pump)
        self.start(self.t_startup)

    # ---------------------------------------------------------------- tema
    def apply_theme(self):
        r = self.root
        r.configure(bg=BG)
        # Klasik Tk bileşenleri ve diyaloglar (simpledialog, messagebox, açılır liste)
        r.option_add("*Background", BG)
        r.option_add("*Foreground", FG)
        r.option_add("*Text.background", BG3)
        r.option_add("*Text.foreground", FG)
        r.option_add("*Entry.background", BG3)
        r.option_add("*Entry.foreground", FG)
        r.option_add("*Button.background", BG3)
        r.option_add("*Button.foreground", FG)
        r.option_add("*Button.activeBackground", ACCENT_H)
        r.option_add("*Button.activeForeground", "#ffffff")
        r.option_add("*selectBackground", ACCENT)
        r.option_add("*selectForeground", "#ffffff")
        r.option_add("*TCombobox*Listbox.background", BG3)
        r.option_add("*TCombobox*Listbox.foreground", FG)
        r.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        r.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

        st = ttk.Style(r)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure(".", background=BG, foreground=FG, fieldbackground=BG3, bordercolor=BORDER,
                     lightcolor=BG, darkcolor=BG, troughcolor=BG2, focuscolor=ACCENT,
                     insertcolor=FG, selectbackground=ACCENT, selectforeground="#ffffff")
        st.configure("TFrame", background=BG)
        st.configure("TLabel", background=BG, foreground=FG)

        st.configure("TButton", background=BG3, foreground=FG, bordercolor=BORDER,
                     lightcolor=BG3, darkcolor=BG3, padding=(10, 5), relief="flat")
        st.map("TButton",
               background=[("pressed", ACCENT), ("active", ACCENT_H), ("disabled", BG2)],
               foreground=[("active", "#ffffff"), ("disabled", MUTED)],
               lightcolor=[("active", ACCENT_H), ("pressed", ACCENT)],
               darkcolor=[("active", ACCENT_H), ("pressed", ACCENT)])

        st.configure("TCheckbutton", background=BG, foreground=FG,
                     indicatorbackground=BG3, indicatorforeground="#ffffff",
                     upperbordercolor=BORDER, lowerbordercolor=BORDER)
        st.map("TCheckbutton",
               background=[("active", BG)],
               foreground=[("active", "#ffffff")],
               indicatorbackground=[("selected", ACCENT), ("pressed", ACCENT_H)])

        st.configure("TEntry", fieldbackground=BG3, foreground=FG, insertcolor=FG,
                     bordercolor=BORDER, lightcolor=BG3, darkcolor=BG3, padding=4)
        st.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
               darkcolor=[("focus", ACCENT)])

        st.configure("TCombobox", fieldbackground=BG3, background=BG3, foreground=FG,
                     arrowcolor=FG, bordercolor=BORDER, lightcolor=BG3, darkcolor=BG3,
                     insertcolor=FG, padding=4)
        st.map("TCombobox",
               fieldbackground=[("readonly", BG3), ("disabled", BG2)],
               background=[("active", BG3), ("pressed", BG3)],
               foreground=[("readonly", FG)],
               selectbackground=[("readonly", BG3)],
               selectforeground=[("readonly", FG)],
               bordercolor=[("focus", ACCENT)])

        st.configure("TNotebook", background=BG, bordercolor=BORDER, lightcolor=BG, darkcolor=BG,
                     tabmargins=(0, 4, 0, 0))
        st.configure("TNotebook.Tab", background=BG2, foreground=MUTED, padding=(14, 6),
                     bordercolor=BORDER, lightcolor=BG2, darkcolor=BG2)
        st.map("TNotebook.Tab",
               background=[("selected", BG3), ("active", BG3)],
               foreground=[("selected", "#ffffff"), ("active", FG)],
               lightcolor=[("selected", ACCENT)], darkcolor=[("selected", BG3)])

        st.configure("TProgressbar", background=ACCENT, troughcolor=BG2, bordercolor=BORDER,
                     lightcolor=ACCENT, darkcolor=ACCENT)
        for sb in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            st.configure(sb, background=BG3, troughcolor=BG2, bordercolor=BG2, arrowcolor=FG,
                         lightcolor=BG3, darkcolor=BG3)
            st.map(sb, background=[("active", BORDER)])

    # ------------------------------------------------------------------ UI
    def build(self):
        top = ttk.Frame(self.root, padding=(10, 8))
        top.pack(fill="x")
        ttk.Label(top, text="GitHub Yönetim Paneli", font=("TkDefaultFont", 14, "bold")).pack(side="left")
        ttk.Button(top, text="Repoları yenile", command=lambda: self.start(self.t_refresh)).pack(side="right")
        ttk.Checkbutton(top, text="Kuru çalıştırma (dry-run)", variable=self.dry_var).pack(side="right", padx=12)

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="x", padx=10)
        self.tab_new()
        self.tab_update()
        self.tab_clone()
        self.tab_issue()
        self.tab_pr()
        self.tab_gist()
        self.tab_settings()

        bar = ttk.Frame(self.root, padding=(10, 6))
        bar.pack(fill="x")
        ttk.Label(bar, textvariable=self.status).pack(side="left")
        self.pb = ttk.Progressbar(bar, mode="indeterminate", length=120)
        self.pb.pack(side="right")
        ttk.Button(bar, text="Logu temizle", command=self.clear_log).pack(side="right", padx=8)

        self.out = scrolledtext.ScrolledText(self.root, height=14, state="disabled", wrap="word",
                                             bg="#141414", fg=FG, insertbackground=FG,
                                             relief="flat", highlightthickness=1,
                                             highlightbackground=BORDER, highlightcolor=BORDER,
                                             font=("monospace", 10))
        self.out.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        for tag, col in (("cmd", "#6cb6ff"), ("ok", "#7ee787"), ("warn", "#e3b341"),
                         ("err", "#ff7b72"), ("info", "#79c0ff")):
            self.out.tag_config(tag, foreground=col)

    def tab(self, title):
        f = ttk.Frame(self.nb, padding=12)
        f.columnconfigure(1, weight=1)
        self.nb.add(f, text=title)
        return f

    def field(self, parent, r, label, var, **kw):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=(0, 8), pady=4)
        e = ttk.Entry(parent, textvariable=var, **kw)
        e.grid(row=r, column=1, sticky="ew", pady=4)
        return e

    def path_field(self, parent, r, label, var, folder=True, file=False):
        self.field(parent, r, label, var)
        bar = ttk.Frame(parent)
        bar.grid(row=r, column=2, padx=(6, 0))
        if folder:
            ttk.Button(bar, text="Klasör…", command=lambda: var.set(filedialog.askdirectory() or var.get())).pack(side="left")
        if file:
            ttk.Button(bar, text="Dosya…", command=lambda: var.set(filedialog.askopenfilename() or var.get())).pack(side="left", padx=(4, 0))

    def repo_field(self, parent, r, label="Repo"):
        var = tk.StringVar()
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=(0, 8), pady=4)
        cb = ttk.Combobox(parent, textvariable=var)
        cb.grid(row=r, column=1, sticky="ew", pady=4)
        self.repo_boxes.append(cb)
        return var

    def body_field(self, parent, r, label):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="nw", padx=(0, 8), pady=4)
        t = tk.Text(parent, height=4, wrap="word", bg=BG3, fg=FG, insertbackground=FG,
                    selectbackground=ACCENT, selectforeground="#ffffff", relief="flat",
                    highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
                    padx=6, pady=4)
        t.grid(row=r, column=1, sticky="ew", pady=4)
        return t

    def default_dir(self):
        d = self.cfg.get("VARSAYILAN_DIR", "")
        return d if d and os.path.isdir(d) else ""

    def tab_new(self):
        f = self.tab("Yeni Repo")
        d, name, owner = tk.StringVar(value=self.default_dir()), tk.StringVar(), tk.StringVar()
        desc, msg = tk.StringVar(), tk.StringVar(value="İlk commit")
        priv = tk.BooleanVar(value=self.cfg.get("VARSAYILAN_VISIBILITY") == "2")
        readme = tk.BooleanVar(value=True)
        self.path_field(f, 0, "Proje klasörü", d)
        self.field(f, 1, "Repo adı", name)
        self.field(f, 2, "Organizasyon (ops.)", owner)
        self.field(f, 3, "Açıklama (ops.)", desc)
        self.field(f, 4, "Commit mesajı", msg)
        ttk.Checkbutton(f, text="Gizli (private) repo", variable=priv).grid(row=5, column=1, sticky="w")
        ttk.Checkbutton(f, text="README.md yoksa oluştur", variable=readme).grid(row=6, column=1, sticky="w")
        ttk.Button(f, text="Oluştur ve Yükle", command=lambda: self.start(
            self.t_new, d.get(), name.get().strip(), owner.get().strip(), priv.get(),
            desc.get().strip(), readme.get(), msg.get().strip())).grid(row=7, column=1, sticky="e", pady=8)

    def tab_update(self):
        f = self.tab("Repoyu Güncelle")
        repo = self.repo_field(f, 0)
        p, msg = tk.StringVar(value=self.default_dir()), tk.StringVar(value="Güncelleme")
        self.path_field(f, 1, "Klasör / dosya", p, folder=True, file=True)
        self.field(f, 2, "Commit mesajı", msg)
        ttk.Button(f, text="Commit & Push", command=lambda: self.start(
            self.t_update, repo.get().strip(), p.get(), msg.get().strip())).grid(row=3, column=1, sticky="e", pady=8)

    def tab_clone(self):
        f = self.tab("Klonla")
        repo, d = tk.StringVar(), tk.StringVar(value=self.default_dir())
        self.field(f, 0, "Repo (kullanıcı/repo veya URL)", repo)
        self.path_field(f, 1, "Hedef klasör", d)
        ttk.Button(f, text="Klonla", command=lambda: self.start(
            self.t_clone, repo.get().strip(), d.get())).grid(row=2, column=1, sticky="e", pady=8)

    def tab_issue(self):
        f = self.tab("Issue")
        repo, title = self.repo_field(f, 0), tk.StringVar()
        self.field(f, 1, "Başlık", title)
        body = self.body_field(f, 2, "Açıklama")
        bar = ttk.Frame(f)
        bar.grid(row=3, column=1, sticky="e", pady=8)
        ttk.Button(bar, text="Açık issue'ları listele", command=lambda: self.start(
            self.t_gh_list, "issue", repo.get().strip())).pack(side="left", padx=4)
        ttk.Button(bar, text="Yeni issue oluştur", command=lambda: self.start(
            self.t_issue_new, repo.get().strip(), title.get().strip(), body.get("1.0", "end").strip())).pack(side="left")

    def tab_pr(self):
        f = self.tab("Pull Request")
        repo, d, title = self.repo_field(f, 0), tk.StringVar(value=self.default_dir()), tk.StringVar()
        self.path_field(f, 1, "Yerel git klasörü", d)
        self.field(f, 2, "Başlık (boşsa --fill)", title)
        body = self.body_field(f, 3, "Açıklama")
        bar = ttk.Frame(f)
        bar.grid(row=4, column=1, sticky="e", pady=8)
        ttk.Button(bar, text="Açık PR'ları listele", command=lambda: self.start(
            self.t_gh_list, "pr", repo.get().strip())).pack(side="left", padx=4)
        ttk.Button(bar, text="Yeni PR oluştur", command=lambda: self.start(
            self.t_pr_new, repo.get().strip(), d.get(), title.get().strip(),
            body.get("1.0", "end").strip())).pack(side="left")

    def tab_gist(self):
        f = self.tab("Gist")
        p, desc, pub = tk.StringVar(), tk.StringVar(), tk.BooleanVar()
        self.path_field(f, 0, "Dosya", p, folder=False, file=True)
        self.field(f, 1, "Açıklama", desc)
        ttk.Checkbutton(f, text="Herkese açık (public)", variable=pub).grid(row=2, column=1, sticky="w")
        ttk.Button(f, text="Gist oluştur", command=lambda: self.start(
            self.t_gist, p.get(), desc.get().strip(), pub.get())).grid(row=3, column=1, sticky="e", pady=8)

    def tab_settings(self):
        f = self.tab("Ayarlar")
        name = tk.StringVar(value=self.cfg["KAYITLI_GIT_NAME"])
        email = tk.StringVar(value=self.cfg["KAYITLI_GIT_EMAIL"])
        d = tk.StringVar(value=self.cfg["VARSAYILAN_DIR"])
        vis = tk.StringVar(value="Private" if self.cfg["VARSAYILAN_VISIBILITY"] == "2" else "Public")
        self.field(f, 0, "Git kullanıcı adı", name)
        self.field(f, 1, "Git e-posta", email)
        self.path_field(f, 2, "Varsayılan klasör", d)
        ttk.Label(f, text="Varsayılan görünürlük").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(f, textvariable=vis, values=("Public", "Private"), state="readonly").grid(
            row=3, column=1, sticky="ew", pady=4)
        ttk.Label(f, text="Ortak ayar dosyası: ~/.gh_panel_config (repo-manager.sh ile paylaşılır)",
                  foreground=MUTED).grid(row=4, column=1, sticky="w")

        def save():
            self.cfg.update(KAYITLI_GIT_NAME=name.get().strip(), KAYITLI_GIT_EMAIL=email.get().strip(),
                            VARSAYILAN_DIR=clean(d.get()),
                            VARSAYILAN_VISIBILITY="2" if vis.get() == "Private" else "1")
            try:
                save_config(self.cfg)
            except OSError as e:
                messagebox.showerror("Kaydedilemedi", str(e))
                return
            self.log(f"✓ Ayarlar '{CONFIG_FILE}' dosyasına kaydedildi.", "ok")
            messagebox.showinfo("Ayarlar", "Ayarlar kaydedildi.\nYeni değerler sonraki işlemlerde kullanılır.")

        def reset():
            if not messagebox.askyesno("Sıfırla", "Kayıtlı ayarlar dosyası silinsin mi?"):
                return
            try:
                CONFIG_FILE.unlink()
            except FileNotFoundError:
                pass
            self.cfg = dict(CONFIG_DEFAULTS)
            name.set("")
            email.set("")
            d.set("")
            vis.set("Public")
            self.log("Ayarlar sıfırlandı.", "ok")

        bar = ttk.Frame(f)
        bar.grid(row=5, column=1, sticky="e", pady=8)
        ttk.Button(bar, text="Sıfırla", command=reset).pack(side="left", padx=4)
        ttk.Button(bar, text="Kaydet", command=save).pack(side="left")

    # ------------------------------------------------- thread <-> UI köprüsü
    def pump(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "log":
                    self.out.config(state="normal")
                    self.out.insert("end", item[1] + "\n", item[2] or ())
                    self.out.see("end")
                    self.out.config(state="disabled")
                else:
                    _, fn, args, ev, box = item
                    try:
                        box["v"] = fn(*args)
                    except Exception as e:  # noqa: BLE001
                        box["e"] = e
                    if ev:
                        ev.set()
        except queue.Empty:
            pass
        self.root.after(50, self.pump)

    def log(self, text, tag=""):
        self.q.put(("log", text, tag))

    def post(self, fn, *args):
        self.q.put(("call", fn, args, None, {}))

    def ui(self, fn, *args):
        ev, box = threading.Event(), {}
        self.q.put(("call", fn, args, ev, box))
        ev.wait()
        if "e" in box:
            raise box["e"]
        return box.get("v")

    def clear_log(self):
        self.out.config(state="normal")
        self.out.delete("1.0", "end")
        self.out.config(state="disabled")

    def start(self, fn, *args):
        if self.busy:
            messagebox.showinfo("Meşgul", "Devam eden bir işlem var, bitmesini bekleyin.")
            return
        self.busy = True
        self.dry_run = self.dry_var.get()
        self.pb.start(12)
        self.status.set("Çalışıyor…")

        def work():
            try:
                fn(*args)
            except Abort as e:
                if str(e):
                    self.log(str(e), "warn")
            except Exception as e:  # noqa: BLE001
                self.log(f"Beklenmeyen hata: {e}", "err")
            finally:
                self.post(self.done)

        threading.Thread(target=work, daemon=True).start()

    def done(self):
        self.busy = False
        self.pb.stop()
        self.status.set(self.base_status)

    # ------------------------------------------------------------ diyaloglar
    def yesno(self, title, msg, default="no"):
        return self.ui(lambda: messagebox.askyesno(title, msg, default=default, parent=self.root))

    def choice(self, title, msg, buttons):
        """Düğme dizinini döndürür; pencere kapatılırsa son düğme (İptal) sayılır."""
        def show():
            top = tk.Toplevel(self.root, bg=BG)
            top.title(title)
            top.transient(self.root)
            top.geometry(f"+{self.root.winfo_rootx() + 90}+{self.root.winfo_rooty() + 90}")
            ttk.Label(top, text=msg, wraplength=520, justify="left").pack(padx=18, pady=14)
            res = {"v": len(buttons) - 1}
            bar = ttk.Frame(top)
            bar.pack(pady=(0, 14))

            def pick(i):
                res["v"] = i
                top.destroy()

            for i, b in enumerate(buttons):
                ttk.Button(bar, text=b, command=lambda i=i: pick(i)).pack(side="left", padx=5)
            top.wait_visibility()
            top.grab_set()
            self.root.wait_window(top)
            return res["v"]
        return self.ui(show)

    def ask(self, title, prompt):
        return self.ui(lambda: simpledialog.askstring(title, prompt, parent=self.root))

    # ------------------------------------------------------ komut çalıştırma
    def run(self, args, cwd=None, check=True, mutate=True):
        shown = shlex.join(args)
        if mutate and self.dry_run:
            self.log(f"[DRY-RUN] {shown}", "warn")
            return 0
        if cwd and not os.path.isdir(cwd):
            raise Abort(f"Dizin bulunamadı: {cwd}")
        self.log("$ " + shown, "cmd")
        p = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, errors="replace", env=ENV)
        for line in p.stdout:
            self.log(line.rstrip())
        rc = p.wait()
        if check and rc != 0:
            raise Abort(f"[HATA] Komut başarısız (kod {rc}): {shown}")
        return rc

    def capture(self, args, cwd=None):
        if cwd and not os.path.isdir(cwd):
            return 1, ""
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, errors="replace", env=ENV)
        return r.returncode, r.stdout.strip()

    def git(self, *a, cwd, **kw):
        return self.run(["git", *a], cwd=cwd, **kw)

    def write(self, path, text, append=False):
        if self.dry_run:
            self.log(f"[DRY-RUN] Dosya yazılacak: {path}", "warn")
            return
        pre = ""
        if append and path.exists() and path.stat().st_size and not path.read_text(errors="ignore").endswith("\n"):
            pre = "\n"
        with open(path, "a" if append else "w", encoding="utf-8") as fh:
            fh.write(pre + text)

    # --------------------------------------------------- güvenlik kontrolleri
    def init_safety(self, d):
        if dangerous(d):
            raise Abort(f"Hata: '{d}' sistem/kullanıcı kök dizinidir. 'git init' yapılamaz!")
        if not os.path.isdir(os.path.join(d, ".git")):
            rc, top = self.capture(["git", "rev-parse", "--show-toplevel"], d)
            if top and os.path.realpath(top) != os.path.realpath(d):
                if not self.yesno("Üst dizinde Git deposu var",
                                  f"Üst dizinde Git deposu mevcut:\n{top}\n\nYine de bu alt dizinde yeni bir Git deposu başlatılsın mı?"):
                    raise Abort("İşlem iptal edildi.")

    def sensitive_check(self, cwd, is_public):
        found = [str(p.relative_to(cwd)) for p in walk_files(cwd, 4, "hidden")
                 if any(fnmatch.fnmatch(p.name, pat) for pat in SENSITIVE)]
        if not found:
            return
        self.log("UYARI: Hassas dosyalar tespit edildi: " + ", ".join(found), "err")
        msg = ("DİKKAT: Public repoya hassas dosya yüklemek CİDDİ GÜVENLİK RİSKİDİR!\n\n" if is_public else "")
        msg += "Bulunan dosyalar:\n" + "\n".join("  • " + f for f in found)
        if self.choice("Hassas dosyalar tespit edildi", msg, [".gitignore'a ekle ve devam et", "İptal"]) != 0:
            raise Abort("İşlem iptal edildi (hassas dosyalar).")
        gi = Path(cwd) / ".gitignore"
        have = set(gi.read_text(errors="ignore").splitlines()) if gi.exists() else set()
        for f in found:
            if f not in have:
                self.write(gi, f + "\n", append=True)
                self.log(f"'{f}' .gitignore dosyasına eklendi.", "ok")

    def gitignore_and_large(self, cwd):
        gi = Path(cwd) / ".gitignore"
        if not gi.exists():
            dirs = [d for d in COMMON_DIRS if (Path(cwd) / d).is_dir()]
            if dirs and self.yesno("Temel .gitignore",
                                   "Şu klasörler var ama .gitignore yok:\n" + ", ".join(dirs) +
                                   "\n\nTemel bir .gitignore oluşturulsun mu?", "yes"):
                self.write(gi, "".join(f"{d}/\n" for d in dirs) + ".DS_Store\n")
                self.log(".gitignore oluşturuldu.", "ok")
        big = [p for p in walk_files(cwd, 5, "git") if fsize(p) > BIG]
        if big:
            lst = "\n".join(f"  • {p.relative_to(cwd)} ({fsize(p) // 1048576} MB)" for p in big)
            if not self.yesno("100 MB üstü dosya", f"GitHub sınırı 100 MB'dır:\n{lst}\n\nDevam etmek istiyor musunuz?"):
                raise Abort("İşlem iptal edildi (büyük dosya).")

    def confirm_summary(self, path, repo, branch, msg, cwd):
        st = ""
        if os.path.isdir(os.path.join(cwd, ".git")):
            _, st = self.capture(["git", "status", "--short"], cwd)
        self.log(f"— İŞLEM ÖZETİ —\nYol: {path}\nRepo: {repo}\nDal: {branch}\nMesaj: {msg}\n{st}", "info")
        short = "\n".join(st.splitlines()[:20]) + ("\n…" if len(st.splitlines()) > 20 else "")
        text = (f"Yol: {path}\nHedef repo: {repo}\nDal: {branch}\nMesaj: {msg}\n\n"
                f"Değişiklikler:\n{short or '(yok / henüz başlatılmadı)'}\n\nDevam edilsin mi?")
        if not self.yesno("İşlem Özeti", text):
            raise Abort("İşlem iptal edildi.")

    # --------------------------------------------------------- git işlemleri
    def ensure_git_user(self, cwd):
        for key, label, ck in (("user.name", "Git kullanıcı adınız", "KAYITLI_GIT_NAME"),
                               ("user.email", "Git e-posta adresiniz", "KAYITLI_GIT_EMAIL")):
            _, val = self.capture(["git", "config", key], cwd)
            if val:
                continue
            saved = self.cfg.get(ck, "")
            if saved:
                self.git("config", "--local", key, saved, cwd=cwd)
                continue
            v = self.ask("Git ayarı", f"'{key}' tanımlı değil.\n{label} (bir defalık kayıt):")
            if v and v.strip():
                v = v.strip()
                self.git("config", "--global", key, v, cwd=cwd)
                self.cfg[ck] = v
                if not self.dry_run:
                    try:
                        save_config(self.cfg)
                    except OSError as e:
                        self.log(f"Ayar dosyası yazılamadı: {e}", "warn")

    def commit(self, cwd, target, msg):
        self.ensure_git_user(cwd)
        self.git("add", target, cwd=cwd)
        if not self.dry_run:
            rc, _ = self.capture(["git", "diff", "--cached", "--quiet"], cwd)
            if rc == 0:
                self.log("Commit edilecek değişiklik yok.", "warn")
                return
        self.git("commit", "-m", msg, cwd=cwd)
        self.log("✓ Commit oluşturuldu.", "ok")

    def set_origin(self, cwd, url):
        _, remotes = self.capture(["git", "remote"], cwd)
        if "origin" in remotes.split():
            _, cur = self.capture(["git", "remote", "get-url", "origin"], cwd)
            if cur and cur != url:
                if not self.yesno("origin farklı", f"Mevcut 'origin' farklı bir adrese bağlı:\n\nEski: {cur}\nYeni: {url}\n\n'origin' güncellensin mi?", "yes"):
                    raise Abort("İşlem iptal edildi (origin).")
                self.git("remote", "set-url", "origin", url, cwd=cwd)
        else:
            self.git("remote", "add", "origin", url, cwd=cwd)

    def push(self, cwd, branch):
        self.log("Uzak sunucu kontrol ediliyor…", "info")
        if self.dry_run:
            self.log(f"[DRY-RUN] git push -u origin {branch}", "warn")
            return
        self.capture(["git", "fetch", "origin", branch], cwd)
        if self.run(["git", "push", "-u", "origin", branch], cwd, check=False) == 0:
            self.log("✓ Başarıyla yüklendi!", "ok")
            return
        i = self.choice("Push başarısız", "Push başarısız oldu (çakışma olabilir). Ne yapılsın?",
                        ["Rebase yap", "Merge yap", "İptal"])
        if i == 0:
            if self.run(["git", "pull", "origin", branch, "--rebase"], cwd, check=False) == 0:
                self.run(["git", "push", "-u", "origin", branch], cwd)
                self.log("✓ Rebase sonrası başarıyla yüklendi!", "ok")
            else:
                self.log("Rebase çakışması! İptal ediliyor…", "err")
                self.run(["git", "rebase", "--abort"], cwd, check=False)
        elif i == 1:
            if self.run(["git", "pull", "origin", branch], cwd, check=False) == 0:
                self.run(["git", "push", "-u", "origin", branch], cwd)
                self.log("✓ Merge sonrası başarıyla yüklendi!", "ok")
            else:
                self.log("Merge çakışması! Lütfen elle çözün.", "err")
        else:
            self.log("İptal edildi.", "warn")

    # ---------------------------------------------------------------- görevler
    def t_startup(self):
        miss = [c for c in ("git", "gh") if not shutil.which(c)]
        if miss:
            self.base_status = "Eksik bağımlılık: " + ", ".join(miss)
            self.post(messagebox.showerror, "Bağımlılık eksik", f"Yüklü değil: {', '.join(miss)}")
            raise Abort("Hata: " + self.base_status)
        if self.capture(["gh", "auth", "status"])[0] != 0:
            self.base_status = "gh oturumu kapalı"
            self.post(messagebox.showerror, "Oturum yok", "Terminalde 'gh auth login' çalıştırın, sonra paneli yeniden açın.")
            raise Abort("Hata: 'gh' oturumu açık değil. 'gh auth login' yapın.")
        if not self.dry_run:
            self.capture(["gh", "auth", "setup-git"])
        self.base_status = "Hazır — GitHub oturumu açık"
        self.log("✓ git ve gh hazır, oturum açık.", "ok")
        self.t_refresh()

    def t_refresh(self):
        self.log("Repolarınız yükleniyor…", "info")
        _, out = self.capture(["gh", "repo", "list", "--limit", "100", "--json", "nameWithOwner",
                               "-q", ".[].nameWithOwner"])
        repos = [x for x in out.splitlines() if x]
        self.post(self.set_repos, repos)
        self.log(f"{len(repos)} repo yüklendi." if repos else "Erişilebilir repo bulunamadı.", "info" if repos else "warn")

    def set_repos(self, repos):
        for cb in self.repo_boxes:
            cb["values"] = repos

    def t_new(self, d, name, owner, private, desc, readme, msg):
        d = clean(d)
        if not os.path.isdir(d):
            raise Abort("Dizin bulunamadı.")
        d = os.path.abspath(d)
        self.init_safety(d)
        if not REPO_RE.match(name or ""):
            raise Abort("Hata: Repo adı boş olamaz; yalnızca harf, rakam, nokta, alt çizgi ve tire içerebilir.")
        spec = f"{owner}/{name}" if owner else name
        if self.capture(["gh", "repo", "view", spec])[0] == 0:
            self.log(f"Uyarı: '{spec}' zaten mevcut! Güncelleme moduna geçiliyor…", "warn")
            return self.t_update(spec, d, msg or "Güncelleme")
        self.sensitive_check(d, not private)
        self.gitignore_and_large(d)
        rd = Path(d) / "README.md"
        if readme and not rd.exists():
            self.write(rd, f"# {name}\n")
            self.log("README.md oluşturuldu.", "ok")
        msg = msg or "İlk commit"
        self.confirm_summary(d, spec, "main", msg, d)
        if not os.path.isdir(os.path.join(d, ".git")):
            self.git("init", cwd=d)
        self.git("branch", "-M", "main", cwd=d)
        self.commit(d, ".", msg)
        cmd = ["gh", "repo", "create", spec, "--private" if private else "--public", "--source=.", "--remote=origin"]
        if desc:
            cmd += ["--description", desc]
        self.log("GitHub'da repo oluşturuluyor…", "info")
        self.run(cmd, cwd=d)
        self.push(d, "main")

    def t_update(self, repo, path, msg):
        if not repo:
            raise Abort("Önce bir repo seçin veya yazın.")
        path = clean(path)
        if not path or not os.path.exists(path):
            raise Abort("Klasör/dosya bulunamadı.")
        path = os.path.abspath(path)
        name, add = repo.split("/")[-1], "."
        if os.path.isfile(path):
            dd, fn = os.path.split(path)
            add = fn
            if dangerous(dd):
                wd = os.path.join(dd, name)
                self.log(f"Seçilen dosya korumalı dizinde ({dd}). '{wd}' klasörü oluşturulup dosya içine alınıyor…", "warn")
                if not self.dry_run:
                    os.makedirs(wd, exist_ok=True)
                    shutil.copy2(path, os.path.join(wd, fn))
            else:
                wd = dd
        else:
            wd = path
        self.init_safety(wd)

        rc, out = self.capture(["gh", "repo", "view", repo, "--json", "defaultBranchRef,url,sshUrl,isPrivate"])
        if rc != 0:
            raise Abort(f"Repo bulunamadı veya erişilemiyor: {repo}")
        info = json.loads(out)
        branch = (info.get("defaultBranchRef") or {}).get("name") or "main"
        url = info.get("url") or f"https://github.com/{repo}.git"
        _, cur = self.capture(["git", "remote", "get-url", "origin"], wd)
        if cur.startswith("git@"):
            url = info.get("sshUrl") or f"git@github.com:{repo}.git"
        is_public = not info.get("isPrivate", False)

        self.sensitive_check(wd, is_public)
        self.gitignore_and_large(wd)
        msg = msg or "Güncelleme"
        self.confirm_summary(wd, repo, branch, msg, wd)
        if not os.path.isdir(os.path.join(wd, ".git")):
            self.git("init", cwd=wd)
            self.git("branch", "-M", branch, cwd=wd)
        self.set_origin(wd, url)
        self.commit(wd, add, msg)
        self.push(wd, branch)

    def t_clone(self, repo, d):
        d = clean(d)
        if not repo:
            raise Abort("Klonlanacak repoyu yazın.")
        if not os.path.isdir(d):
            raise Abort("Hedef klasör bulunamadı.")
        self.log("Klonlanıyor…", "info")
        self.run(["gh", "repo", "clone", repo], cwd=d)
        self.log("✓ İşlem tamamlandı.", "ok")

    def t_gh_list(self, kind, repo):
        if not repo:
            raise Abort("Önce bir repo seçin veya yazın.")
        self.run(["gh", kind, "list", "--repo", repo], mutate=False, check=False)

    def t_issue_new(self, repo, title, body):
        if not repo or not title:
            raise Abort("Repo ve başlık gerekli.")
        self.run(["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body])

    def t_pr_new(self, repo, d, title, body):
        d = clean(d)
        if not repo or not os.path.isdir(d):
            raise Abort("Repo ve geçerli bir yerel git klasörü gerekli.")
        cmd = ["gh", "pr", "create", "--repo", repo]
        cmd += ["--title", title, "--body", body] if title else ["--fill"]
        self.run(cmd, cwd=d)

    def t_gist(self, path, desc, public):
        path = clean(path)
        if not os.path.isfile(path):
            raise Abort("Geçerli bir dosya seçilmedi.")
        cmd = ["gh", "gist", "create", path]
        if desc:
            cmd += ["-d", desc]
        if public:
            cmd.append("--public")
        self.log("Gist oluşturuluyor…", "info")
        self.run(cmd)

    def mainloop(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().mainloop()
