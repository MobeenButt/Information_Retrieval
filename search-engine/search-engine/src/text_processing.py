"""Text processing primitives for the structured-document search engine.

Pipeline (Week 1, "Text Processing"): tokenize -> remove stop-words -> stem.

The SAME pipeline is applied to documents (at index time) and to queries
(at search time) so that index terms and query terms line up exactly.

Everything here is implemented from scratch (no backend/ imports).
"""
from __future__ import annotations

import re
from typing import Dict, List

# Week 1 - Stop-word list: very common words dropped because they carry little
# ranking signal ("the", "is", "of", ...). Kept as a frozenset for O(1) lookups.
STOPWORDS: frozenset = frozenset(
    """
    a about above after again all also am an and any are as at be because been
    before being below between both but by can could did do does doing down
    during each few for from further had has have having he her here hers him
    his how i if in into is it its itself just me more most my no nor not now
    of off on once only or other our out over own same she should so some such
    than that the their them then there these they this those through to too
    under until up very was we were what when where which while who whom why
    will with would you your
    """.split()
)

# Week 1 - Tokenizer regex: a token is any run of lowercase letters or digits.
_TOKEN_RE: re.Pattern = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    """Lowercase the text and split it into alphanumeric tokens.

    Week 1 - Tokenization. Returns an ordered list of tokens (with repeats),
    e.g. tokenize("The running machines") -> ["the", "running", "machines"].
    """
    return _TOKEN_RE.findall(text.lower())


def remove_stopwords(tokens: List[str]) -> List[str]:
    """Drop stop-words ("the", "is", "of") that carry little meaning.

    Week 1 - Stop-word removal. Preserves token order and multiplicity for
    the tokens that remain.
    """
    return [t for t in tokens if t not in STOPWORDS]


# ─────────────────────────────────────────────
#  Week 1 - Porter-style stemmer (from scratch)
#
#  A faithful, compact implementation of the classic Porter (1980) suffix
#  stripping algorithm. Words are reduced to a common root so that
#  "running" -> "run" and "machines" -> "machin". A word is treated as a
#  consonant/vowel sequence and the measure m (the number of VC repeats)
#  gates each rewrite rule. Public entry point: stem(word).
# ─────────────────────────────────────────────
class _PorterStemmer:
    """Stateful core of the Porter algorithm; one instance is reused per call."""

    def __init__(self) -> None:
        self.b: str = ""   # word buffer
        self.k: int = 0    # index of the last char of the (sub)word
        self.j: int = 0    # set by ends() to the end of the stem

    # -- consonant test -------------------------------------------------
    def _cons(self, i: int) -> bool:
        """True if b[i] is a consonant. 'y' is a vowel iff preceded by a consonant."""
        ch = self.b[i]
        if ch in "aeiou":
            return False
        if ch == "y":
            return True if i == 0 else not self._cons(i - 1)
        return True

    # -- measure --------------------------------------------------------
    def _m(self) -> int:
        """Measure: number of VC sequences between index 0 and j."""
        n = 0
        i = 0
        while True:
            if i > self.j:
                return n
            if not self._cons(i):
                break
            i += 1
        i += 1
        while True:  # outer loop over VC pairs
            while True:
                if i > self.j:
                    return n
                if self._cons(i):
                    break
                i += 1
            i += 1
            n += 1
            while True:
                if i > self.j:
                    return n
                if not self._cons(i):
                    break
                i += 1
            i += 1

    def _vowelinstem(self) -> bool:
        """True if the stem (0..k) contains at least one vowel."""
        return any(not self._cons(i) for i in range(self.k + 1))

    def _doublec(self, j: int) -> bool:
        """True if b[j-1..j] are the same consonant."""
        if j < 1 or self.b[j] != self.b[j - 1]:
            return False
        return self._cons(j)

    def _cvc(self, i: int) -> bool:
        """True if b[i] ends a consonant-vowel-consonant sequence that is not
        one of w, x, y (used to restore a final 'e')."""
        if i < 2 or not self._cons(i) or self._cons(i - 1) or not self._cons(i - 2):
            return False
        return self.b[i] not in "wxy"

    def _ends(self, s: str) -> bool:
        """True if the (sub)word ends with s; sets j to the stem end on success."""
        length = len(s)
        if s[length - 1] != self.b[self.k]:
            return False
        if length > self.k + 1:
            return False
        if self.b[self.k - length + 1:self.k + 1] != s:
            return False
        self.j = self.k - length
        return True

    def _setto(self, s: str) -> None:
        """Replace the suffix (j+1..k) with s and move k to the end of s."""
        length = len(s)
        self.b = self.b[:self.j + 1] + s + self.b[self.j + length + 1:]
        self.k = self.j + length

    def _r(self, s: str) -> None:
        """_setto(s) only if the measure of the stem is > 0."""
        if self._m() > 0:
            self._setto(s)

    # -- the five Porter steps -----------------------------------------
    def _step1ab(self) -> None:
        """Plurals and past-tense endings (SSES, IES, SS, S, EED, ED, ING)."""
        if self.b[self.k] == "s":
            if self._ends("sses"):
                self.k -= 2
            elif self._ends("ies"):
                self._setto("i")
            elif self.b[self.k - 1] != "s":
                self.k -= 1
        if self._ends("eed"):
            if self._m() > 0:
                self.k -= 1
        elif (self._ends("ed") or self._ends("ing")) and self._vowelinstem():
            self.k = self.j
            if self._ends("at"):
                self._setto("ate")
            elif self._ends("bl"):
                self._setto("ble")
            elif self._ends("iz"):
                self._setto("ize")
            elif self._doublec(self.k):
                self.k -= 1
                if self.b[self.k] in "lsz":
                    self.k += 1
            elif self._m() == 1 and self._cvc(self.k):
                self._setto("e")

    def _step1c(self) -> None:
        """Turn a final 'y' into 'i' when the stem contains a vowel."""
        if self._ends("y") and self._vowelinstem():
            self.b = self.b[:self.k] + "i" + self.b[self.k + 1:]

    def _step2(self) -> None:
        """Map common suffixes to canonical forms (gated by m > 0)."""
        last = self.b[self.k - 1]
        if last == "a":
            if self._ends("ational"):
                self._r("ate")
            elif self._ends("tional"):
                self._r("tion")
        elif last == "c":
            if self._ends("enci"):
                self._r("ence")
            elif self._ends("anci"):
                self._r("ance")
        elif last == "e":
            if self._ends("izer"):
                self._r("ize")
        elif last == "l":
            if self._ends("bli"):
                self._r("ble")
            elif self._ends("alli"):
                self._r("al")
            elif self._ends("entli"):
                self._r("ent")
            elif self._ends("eli"):
                self._r("e")
            elif self._ends("ousli"):
                self._r("ous")
        elif last == "o":
            if self._ends("ization"):
                self._r("ize")
            elif self._ends("ation"):
                self._r("ate")
            elif self._ends("ator"):
                self._r("ate")
        elif last == "s":
            if self._ends("alism"):
                self._r("al")
            elif self._ends("iveness"):
                self._r("ive")
            elif self._ends("fulness"):
                self._r("ful")
            elif self._ends("ousness"):
                self._r("ous")
        elif last == "t":
            if self._ends("aliti"):
                self._r("al")
            elif self._ends("iviti"):
                self._r("ive")
            elif self._ends("biliti"):
                self._r("ble")
        elif last == "g":
            if self._ends("logi"):
                self._r("log")

    def _step3(self) -> None:
        """Further suffix cleanup (gated by m > 0)."""
        last = self.b[self.k]
        if last == "e":
            if self._ends("icate"):
                self._r("ic")
            elif self._ends("alize"):
                self._r("al")
        elif last == "i":
            if self._ends("iciti"):
                self._r("ic")
        elif last == "l":
            if self._ends("ical"):
                self._r("ic")
        elif last == "s":
            if self._ends("ness"):
                pass

    def _step4(self) -> None:
        """Remove derivational suffixes when the stem measure is > 1."""
        last = self.b[self.k - 1]
        matched = False
        if last == "a":
            matched = self._ends("al")
        elif last == "c":
            matched = self._ends("ance") or self._ends("ence")
        elif last == "e":
            matched = self._ends("er")
        elif last == "i":
            matched = self._ends("ic")
        elif last == "l":
            matched = self._ends("able") or self._ends("ible")
        elif last == "n":
            matched = (self._ends("ant") or self._ends("ement")
                       or self._ends("ment") or self._ends("ent"))
        elif last == "o":
            if self._ends("ion") and self.b[self.j] in "st":
                matched = True
            elif self._ends("ou"):
                matched = True
        elif last == "s":
            matched = self._ends("ism")
        elif last == "t":
            matched = self._ends("ate") or self._ends("iti")
        elif last == "u":
            matched = self._ends("ous")
        elif last == "v":
            matched = self._ends("ive")
        elif last == "z":
            matched = self._ends("ize")
        if matched and self._m() > 1:
            self.k = self.j

    def _step5(self) -> None:
        """Tidy up a trailing 'e' and a double 'l' when the measure allows."""
        self.j = self.k
        if self.b[self.k] == "e":
            a = self._m()
            if a > 1 or (a == 1 and not self._cvc(self.k - 1)):
                self.k -= 1
        if self.b[self.k] == "l" and self._doublec(self.k) and self._m() > 1:
            self.k -= 1

    def stem_word(self, w: str) -> str:
        """Run all Porter steps on w and return the stem."""
        if len(w) <= 2:
            return w
        self.b = w
        self.k = len(w) - 1
        self._step1ab()
        self._step1c()
        self._step2()
        self._step3()
        self._step4()
        self._step5()
        return self.b[:self.k + 1]


# Reused instance so stem() avoids per-call allocation.
_STEMMER = _PorterStemmer()


def stem(word: str) -> str:
    """Reduce a token to its Porter-style stem (running -> run, machines -> machin).

    Week 1 - Stemming. Words of length <= 2 are returned unchanged.
    """
    return _STEMMER.stem_word(word)


def stem_all(tokens: List[str]) -> List[str]:
    """Apply stem() to every token, preserving order."""
    return [stem(t) for t in tokens]


def preprocess(text: str) -> List[str]:
    """Full pipeline: text -> list of index terms (tokens without stop-words, stemmed).

    Week 1 - Preprocessing pipeline. Applied identically to documents and queries.
    """
    return stem_all(remove_stopwords(tokenize(text)))


def analyze_pipeline(text: str) -> Dict[str, object]:
    """Return every stage of the pipeline for inspection/display.

    Week 1 - Analysis pipeline. Keys:
      raw     : the original text
      tokens  : tokenize(text)
      no_stop : remove_stopwords(tokens)
      stems   : stem_all(no_stop)
    """
    tokens = tokenize(text)
    no_stop = remove_stopwords(tokens)
    return {
        "raw": text,
        "tokens": tokens,
        "no_stop": no_stop,
        "stems": stem_all(no_stop),
    }
