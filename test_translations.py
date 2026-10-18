"""Coverage guard for the i18n catalogue.

The recurring "it's still in English" bug has one root cause: translate()
falls back to English when a key is missing a language, so an untranslated
string looks identical to a translated one and nobody notices by eye. This
test makes that gap fail loudly instead.

    .venv/bin/python test_translations.py

It checks, and fails on:

  * any key that does not define all of en/ru/tk, or leaves one blank
  * any user-facing string left hardcoded in a template (text nodes and the
    placeholder / aria-label / title / alt attributes), outside the handful of
    deliberate literals below
"""

import glob
import os
import re
import sys

from translations import TRANSLATIONS, LANGUAGES

FAILURES = []
CHECKS = 0


def check(name, ok, detail=""):
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILURES.append("%s%s" % (name, (" — %s" % detail) if detail else ""))


# Strings that are intentionally not translated: the brand, data that is typed
# as-is (a city used as an example), the fixed confirmation phrase the JS and
# the error copy both pin to literally, and a sample email address.
ACCEPTED_LITERALS = {
    "Global", "Trade", "Global Trade", "Ashgabat", "I READ", "you@example.com",
}
# Attribute values that are tokens/MIME, not prose.
ACCEPTED_ATTRS = {"search", "button", "image/*", "page", "true", "false"}

TEXT_RE = re.compile(r">\s*([A-Za-z][^<>{}]*?[A-Za-z.!?])\s*<")
ATTR_RE = re.compile(r'(placeholder|aria-label|title|alt)\s*=\s*"([^"{}]*[A-Za-z]{3}[^"{}]*)"')


def strip_jinja_comments(lines):
    """Yield (lineno, text) with {# .. #} blocks (even multi-line) removed."""
    in_comment = False
    for i, line in enumerate(lines, 1):
        if in_comment:
            if "#}" in line:
                in_comment = False
            continue
        if "{#" in line and "#}" not in line:
            in_comment = True
            continue
        # single-line {# .. #}
        line = re.sub(r"\{#.*?#\}", "", line)
        yield i, line


def has_letters(s, n=3):
    return len(re.findall(r"[A-Za-z]", s)) >= n


def check_flash_coverage():
    """Fail if a flash() in app.py flashes a plain English string that has no
    translation. flash('x') and flash(a if c else b) are translated at render
    time by looking the English up in the fl.* catalogue, so every such literal
    must be present there. flash(ft(...)) (a key) and flash(str(exc)) are
    exempt — the former is already a key, the latter is handled separately."""
    import ast
    fl_english = {e["en"] for k, e in TRANSLATIONS.items() if k.startswith("fl.")}
    src = open("app.py", encoding="utf-8").read()
    tree = ast.parse(src)

    def literals(node):
        """The English string literals a flash() argument can flash directly."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, ast.IfExp):  # flash('a' if c else 'b')
            return literals(node.body) + literals(node.orelse)
        return []  # ft(...) call, BinOp %-format, str(exc) — not a plain literal

    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "flash" and node.args):
            for text in literals(node.args[0]):
                check("app.py:%d flash translated" % node.lineno,
                      text in fl_english, text[:60])


def main():
    langs = list(LANGUAGES.keys()) if isinstance(LANGUAGES, dict) else list(LANGUAGES)
    check_flash_coverage()

    # 1. Every key defines every language, non-empty.
    for key, entry in TRANSLATIONS.items():
        for lang in langs:
            val = entry.get(lang)
            check("key %s has %s" % (key, lang), bool(val and str(val).strip()), repr(val))

    # 2. No user-facing hardcoded English left in the templates.
    for path in sorted(glob.glob("templates/**/*.html", recursive=True)):
        lines = open(path, encoding="utf-8").read().split("\n")
        for i, line in strip_jinja_comments(lines):
            for m in TEXT_RE.finditer(line):
                text = m.group(1).strip()
                if text in ACCEPTED_LITERALS or not has_letters(text):
                    continue
                check("%s:%d not hardcoded" % (path, i), False, text[:60])
            for m in ATTR_RE.finditer(line):
                val = m.group(2).strip()
                if (val in ACCEPTED_LITERALS or val.lower() in ACCEPTED_ATTRS
                        or not has_letters(val)):
                    continue
                check("%s:%d %s not hardcoded" % (path, i, m.group(1)), False, val[:60])

    print("=" * 60)
    print("%d checks, %d failures" % (CHECKS, len(FAILURES)))
    if FAILURES:
        for name in FAILURES:
            print("  FAILED: %s" % name)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
