"""repo-manager Lisans Yönetimi Modülü

Bu modül, yeni GitHub repoları oluşturulurken projede lisans dosyası
bulunmadığında kullanılabilecek popüler açık kaynak lisans şablonlarını
(MIT, Apache 2.0, GNU GPL v3) ve yardımcı fonksiyonları içerir.
"""
import datetime
from pathlib import Path

LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "LICENCE.md", "LICENCE.txt")

TEMPLATES = {
    "MIT": """MIT License

Copyright (c) {year} {author}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
""",
    "Apache-2.0": """                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   Copyright {year} {author}

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
""",
    "GPL-3.0": """                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Copyright (C) {year} {author}

 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.

                            Preamble

  The GNU General Public License is a free, copyleft license for
software and other kinds of works.
  This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

  This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
}


def has_license(directory: str | Path) -> bool:
    """Belirtilen dizinde herhangi bir lisans dosyası olup olmadığını denetler."""
    path = Path(directory)
    if not path.is_dir():
        return False
    return any((path / name).exists() for name in LICENSE_NAMES)


def get_license_text(license_type: str, author: str = "") -> str:
    """Seçilen lisans türü için şablonu üretir (yıl ve yazar bilgisi eklenerek)."""
    tmpl = TEMPLATES.get(license_type)
    if not tmpl:
        return ""
    year = datetime.datetime.now().year
    clean_author = (author or "").strip() or "Project Contributors"
    return tmpl.format(year=year, author=clean_author)


def write_license(directory: str | Path, license_type: str, author: str = "") -> Path | None:
    """Belirtilen dizine LICENSE dosyası oluşturur ve yazar."""
    text = get_license_text(license_type, author)
    if not text:
        return None
    target = Path(directory) / "LICENSE"
    target.write_text(text, encoding="utf-8")
    return target
