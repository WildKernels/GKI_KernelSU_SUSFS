#!/usr/bin/env python3
"""Drop invisible formatting characters from UTF-8 name normalisation.

Why this exists
---------------
A filename containing a zero-width or bidi-control character looks identical to one
without it but compares differently, so a file can be present yet invisible to a
path check - the "zero-width bypass". The blob patch (unicode_bypass_fix_*.patch)
closes it by changing what happens when a decomposition leaf is empty, but that
condition is not specific to invisible characters: the generated utf8data table can
return an empty leaf for visible characters too, emoji in particular. Those then stop
being normalised the same way the dentry was created, lookups miss, and the files
appear to have vanished. That is the emoji regression, and it is why the change was
reverted upstream.

What this does instead
----------------------
Normalisation is left completely alone. The only change is that characters that
render as nothing are consumed and never emitted, so they cannot alter the
normalised name:

    "abc<U+200B>def"  normalises to  "abcdef"

Two names that look the same therefore compare the same, which is the bypass gone.
Everything visible - emoji, CJK, accents, combining marks - takes the stock path
byte for byte, so emoji filenames are untouched.

Which characters
----------------
Only characters with no rendering role. Deliberately excluded:
  U+200C ZWNJ and U+200D ZWJ  - required inside emoji sequences (family, profession)
                                and in Persian/Arabic/Indic orthography
  U+FE00-U+FE0F variation selectors - U+FE0F makes text characters emoji
  U+115F/1160, U+3164, U+FFA0 Hangul fillers - appear in Korean text
  U+17B4/17B5 Khmer, U+180B-180E Mongolian - required by those scripts

Idempotent: re-running is a no-op. Fails loudly if the code it edits has moved.
"""

import re
import sys
from pathlib import Path

MARKER = "utf8_drop_invisible"
TARGET = "fs/unicode/utf8-norm.c"

HELPER = r'''/*
 * Characters that render as nothing: zero-width spaces and joiners' separators,
 * bidi overrides, word joiner, BOM. A name containing one of these looks exactly
 * like the same name without it, which is what a zero-width bypass is made of.
 *
 * Note what is NOT here: U+200C ZWNJ and U+200D ZWJ (they are required inside
 * emoji sequences and in several scripts), U+FE00-U+FE0F (variation selectors -
 * U+FE0F is what turns a text glyph into an emoji), the Hangul fillers and the
 * Khmer/Mongolian variation selectors. Visible characters are never touched.
 */
static inline int %(marker)s(const unsigned char *s)
{
	if (s[0] == 0xC2 && s[1] == 0xAD)		/* U+00AD soft hyphen */
		return 1;
	if (s[0] == 0xE2 && s[1] == 0x80) {
		if (s[2] == 0x8B)			/* U+200B zero width space */
			return 1;
		if (s[2] == 0x8E || s[2] == 0x8F)	/* U+200E LRM, U+200F RLM */
			return 1;
		if (s[2] >= 0xAA && s[2] <= 0xAE)	/* U+202A-U+202E bidi overrides */
			return 1;
	}
	if (s[0] == 0xE2 && s[1] == 0x81 && s[2] >= 0xA0 && s[2] <= 0xAF)
		return 1;				/* U+2060-U+206F word joiner, isolates */
	if (s[0] == 0xEF && s[1] == 0xBB && s[2] == 0xBF)
		return 1;				/* U+FEFF BOM / zero width no-break space */
	return 0;
}

'''

GATE = r'''		/*
		 * Consume invisible formatting characters without emitting them, so they
		 * cannot make two identical-looking names compare differently (the
		 * zero-width bypass). Visible characters - emoji included - fail the
		 * predicate below and take the stock path unchanged.
		 */
		if (%(marker)s(u8c->s)) {
			unsigned int clen = utf8clen(u8c->s);

			u8c->s += clen;
			if (!u8c->p)
				u8c->len -= clen;
			if (u8c->ccc == STOPPER)
				continue;
			ccc = STOPPER;
			goto ccc_mismatch;
		}

''' % {"marker": MARKER}


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def patch(tree: Path) -> str:
    f = tree / TARGET
    if not f.is_file():
        die(f"{f}: not found - is this a kernel/common tree?")
    src = f.read_text()
    if MARKER in src:
        return "already ported"

    # 1. helper immediately above utf8byte(), which is its only caller
    anchor = "int utf8byte(struct utf8cursor *u8c)\n"
    if src.count(anchor) != 1:
        die(f"{TARGET}: expected exactly one '{anchor.strip()}', found {src.count(anchor)}")
    helper = HELPER % {"marker": MARKER}
    body_at = src.index(anchor)
    src = src[:body_at] + helper + src[body_at:]

    # 2. the gate, after the leaf lookup has established a valid character start.
    #    Search only inside utf8byte(): the same "if (!leaf) return -1;" shape also
    #    appears in utf8ncursor(), where u8c->s and ccc_mismatch do not exist.
    body_at = src.index(anchor) + len(anchor)
    m = re.search(r"(?P<pre>\t\tif \(!leaf\)\n\t\t\treturn -1;\n)", src[body_at:])
    if not m:
        die(f"{TARGET}: 'if (!leaf) return -1;' (the post-lookup check) not found inside utf8byte()")
    at = body_at + m.end()
    src = src[:at] + GATE + src[at:]

    f.write_text(src)
    return "patched"


def main():
    trees = sys.argv[1:]
    if not trees:
        trees = [str(p) for p in Path("/home/james/Projects").glob("kernel-*-lts")]
    for t in trees:
        root = Path(t)
        common = root / "common"
        target = common if (common / TARGET).is_file() else root
        print(f"{root.name:16s} {patch(target)}")


if __name__ == "__main__":
    main()
