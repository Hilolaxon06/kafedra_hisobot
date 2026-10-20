"""
Tarjima satrlarini yig'ish va .po/.mo fayllarini yig'ish — GNU gettext'siz.

Django'ning makemessages/compilemessages buyruqlari GNU gettext
(xgettext/msgfmt) ni talab qiladi, Windows'da u odatda o'rnatilmagan.
Bu skript xuddi shu ishni toza Python'da bajaradi (qo'shimcha paketsiz):

    python scripts/i18n.py            # locale/{uz,ru,en}/LC_MESSAGES/django.po ni yangilash
    python scripts/i18n.py --compile  # + django.mo ni yig'ish

Satrlar qayerdan olinadi:
- shablonlar: {% translate "..." %}, {% blocktranslate [trimmed] %}...{% endblocktranslate %},
  filtr argumentlari _("...");
- Python: _("..."), gettext(...), gettext_lazy(...), pgettext yo'q.

Kodda msgid — sayt interfeysida o'zbekcha, modellarda (verbose_name,
choices) — ruscha. Shuning uchun HAR UCHALA katalogda har bir satr uchun
tarjima to'liq bo'lishi kerak: aks holda Django bo'sh tarjima o'rniga
LANGUAGE_CODE (o'zbek) katalogidagi matnni qo'yadi.
Mavjud tarjimalar saqlanadi, yangi satrlar bo'sh qo'shiladi va skript
ularni ro'yxat qilib chiqaradi.
"""

import ast
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ("uz", "ru", "en")
SOURCES = [ROOT / "apps", ROOT / "templates", ROOT / "config"]
SKIP_DIRS = {"migrations", "__pycache__", ".idea", "admin"}  # admin shablonlarida — Django o'z matnlari
GETTEXT_NAMES = {"_", "_g", "gettext", "gettext_lazy", "gettext_noop"}

TRANSLATE_RE = re.compile(r"""\{%\s*(?:translate|trans)\s+(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')""")
BLOCK_RE = re.compile(r"\{%\s*blocktrans(?:late)?\b(.*?)%\}(.*?)\{%\s*endblocktrans(?:late)?\s*%\}", re.S)
FILTER_ARG_RE = re.compile(r"""_\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')\s*\)""")
VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def po_path(lang):
    return ROOT / "locale" / lang / "LC_MESSAGES" / "django.po"


# ---------------------------------------------------------------- extraction

def _iter_files(suffix):
    for base in SOURCES:
        for path in base.rglob(f"*{suffix}"):
            if not SKIP_DIRS.intersection(path.parts):
                yield path


def from_template(path):
    text = path.read_text(encoding="utf-8")
    for m in TRANSLATE_RE.finditer(text):
        raw = m.group(1) if m.group(1) is not None else m.group(2)
        yield raw.replace('\\"', '"').replace("\\'", "'")
    for m in BLOCK_RE.finditer(text):
        options, body = m.group(1), m.group(2)
        body = VAR_RE.sub(lambda v: f"%({v.group(1)})s", body.replace("%", "%%"))
        if "trimmed" in options.split():
            body = re.sub(r"\s*\n\s*", " ", body.strip())
        yield body
    for m in FILTER_ARG_RE.finditer(text):
        yield m.group(1) if m.group(1) is not None else m.group(2)


def from_python(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and node.args):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        arg = node.args[0]
        if name in GETTEXT_NAMES and isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            yield arg.value


def extract():
    found = {}
    for path in sorted(_iter_files(".html")):
        for msgid in from_template(path):
            found.setdefault(msgid, set()).add(str(path.relative_to(ROOT)).replace("\\", "/"))
    for path in sorted(_iter_files(".py")):
        for msgid in from_python(path):
            found.setdefault(msgid, set()).add(str(path.relative_to(ROOT)).replace("\\", "/"))
    found.pop("", None)
    return found


# ---------------------------------------------------------------- .po read/write

def _unquote(line):
    return ast.literal_eval(line)


def read_po(path):
    """{msgid: msgstr} — faqat shu skript yozgan oddiy .po (plural/kontekstsiz)."""
    entries = {}
    if not path.exists():
        return entries
    key, current, msgid, msgstr = None, None, None, None
    for line in path.read_text(encoding="utf-8").splitlines() + [""]:
        line = line.strip()
        if line.startswith("msgid "):
            if msgid is not None:
                entries[msgid] = msgstr or ""
            msgid, msgstr, key = _unquote(line[6:]), None, "id"
        elif line.startswith("msgstr "):
            msgstr, key = _unquote(line[7:]), "str"
        elif line.startswith('"'):
            if key == "id":
                msgid += _unquote(line)
            elif key == "str":
                msgstr += _unquote(line)
        elif not line and msgid is not None:
            entries[msgid] = msgstr or ""
            msgid, msgstr, key = None, None, None
    entries.pop("", None)
    return entries


def _quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t") + '"'


HEADER = (
    "Content-Type: text/plain; charset=UTF-8\n"
    "Content-Transfer-Encoding: 8bit\n"
    "Language: {lang}\n"
    "Plural-Forms: nplurals=2; plural=(n != 1);\n"
)


def write_po(path, lang, found, translations):
    out = ["# Kafedra hisoboti — interfeys tarjimasi. scripts/i18n.py yaratadi.",
           'msgid ""', "msgstr " + _quote(HEADER.format(lang=lang)), ""]
    for msgid in sorted(found, key=lambda s: (sorted(found[s])[0], s)):
        out.append("#: " + " ".join(sorted(found[msgid])))
        if "%(" in msgid:
            out.append("#, python-format")
        out.append("msgid " + _quote(msgid))
        out.append("msgstr " + _quote(translations.get(msgid, "")))
        out.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")


# ---------------------------------------------------------------- .mo

def write_mo(path, lang, translations):
    items = {"": HEADER.format(lang=lang)}
    items.update({k: v for k, v in translations.items() if v})
    keys = sorted(items)
    ids = [k.encode("utf-8") for k in keys]
    strs = [items[k].encode("utf-8") for k in keys]
    n = len(keys)
    ids_start = 7 * 4 + 16 * n
    ids_blob, strs_blob, ids_table, strs_table = b"", b"", [], []
    for s in ids:
        ids_table.append((len(s), ids_start + len(ids_blob)))
        ids_blob += s + b"\0"
    strs_start = ids_start + len(ids_blob)
    for s in strs:
        strs_table.append((len(s), strs_start + len(strs_blob)))
        strs_blob += s + b"\0"
    data = struct.pack("<7I", 0x950412DE, 0, n, 7 * 4, 7 * 4 + 8 * n, 0, 0)
    data += b"".join(struct.pack("<2I", *e) for e in ids_table)
    data += b"".join(struct.pack("<2I", *e) for e in strs_table)
    path.write_bytes(data + ids_blob + strs_blob)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    found = extract()
    missing_total = 0
    for lang in LANGUAGES:
        path = po_path(lang)
        translations = read_po(path)
        write_po(path, lang, found, translations)
        missing = [m for m in found if not translations.get(m)]
        missing_total += len(missing)
        print(f"{lang}: {len(found)} ta satr, tarjimasiz: {len(missing)}")
        for m in missing[:20]:
            print("   -", m[:90])
        if "--compile" in sys.argv:
            write_mo(path.with_suffix(".mo"), lang, {k: v for k, v in translations.items() if k in found})
    if "--compile" in sys.argv:
        print("django.mo yig'ildi.")
    return 1 if missing_total and "--strict" in sys.argv else 0


if __name__ == "__main__":
    sys.exit(main())
