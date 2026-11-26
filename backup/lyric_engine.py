# lyric_engine.py
import os
import re
import json
import math
import urllib.request
import urllib.parse
from functools import lru_cache
from collections import defaultdict

try:
    import pronouncing
    HAS_PRONOUNCING = True
except ImportError:
    pronouncing = None
    HAS_PRONOUNCING = False

try:
    import cmudict as _cmudict_mod
    _CMU_DICT = _cmudict_mod.dict()
    HAS_CMUDICT = True
except Exception:
    _CMU_DICT = {}
    HAS_CMUDICT = False


@lru_cache(maxsize=16384)
def _all_cmu_pronunciations(word_low: str) -> tuple:
    """Every CMUdict pronunciation of a word (e.g. 'read' has two), via pronouncing or cmudict."""
    prons = []
    if HAS_PRONOUNCING:
        try:
            for plist in pronouncing.phones_for_word(word_low) or []:
                prons.append(tuple(plist.split()))
        except Exception:
            pass
    if not prons and HAS_CMUDICT and word_low in _CMU_DICT:
        for entry in _CMU_DICT[word_low] or []:
            prons.append(tuple(entry))
    seen, out = set(), []
    for pr in prons:
        if pr and pr not in seen:
            seen.add(pr)
            out.append(pr)
    return tuple(out)


def _lookup_cmu_phones(word_low: str) -> list[str]:
    """First CMU pronunciation as an ARPAbet phone list (used for syllable units)."""
    prons = _all_cmu_pronunciations(word_low)
    return list(prons[0]) if prons else []


def _rhyming_part(phones) -> str:
    """CMU rhyming part: from the last stressed (1/2) vowel onward, stress digits removed."""
    phones = list(phones or [])
    start = 0
    for i in range(len(phones) - 1, -1, -1):
        if phones[i][-1:] in ("1", "2"):
            start = i
            break
    return " ".join(re.sub(r"\d", "", p) for p in phones[start:])


# =====================================================================
# CURATED ONLINE CATALOG (COMPATIBLE WITH LexiconManagerDialog)
# =====================================================================
ONLINE_CURATED_CATALOG = [
    {
        "category": "English Slang",
        "name": "Urban & Hip-Hop Slang (Core)",
        "desc": "Modern rap, AAVE, and street terminology",
        "url": "https://raw.githubusercontent.com/dariusk/corpora/master/data/words/proverbs.json",
    },
    {
        "category": "Bahasa Melayu",
        "name": "BM & Bahasa Pasar Extended",
        "desc": "Malaysian urban, KL street & Manglish vocabulary",
        "url": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/ms/ms_50k.txt",
    },
    {
        "category": "English Vocab",
        "name": "English 10k Frequency Words",
        "desc": "Core English vocabulary for fast offline rhyme lookup",
        "url": "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt",
    },
]


def ensure_offline_corpora():
    """Ensures offline phonetic & lexical tables are initialized without network dependency."""
    _ = len(BUILTIN_EN_WORDS) + len(BUILTIN_BM_WORDS)


# =====================================================================
# PHONETIC FEATURE TABLES (ARTICULATORY VOWEL & CONSONANT SPACE)
# =====================================================================
# Vowel coordinates: (height [0=low..3=high], backness [0=front..2=back], tense/diphthong [0..1])
VOWEL_FEATURES = {
    "IY": (3.0, 0.0, 1.0),  # beat
    "IH": (2.5, 0.2, 0.0),  # bit
    "EY": (2.0, 0.1, 1.0),  # bait / day
    "EH": (1.5, 0.2, 0.0),  # bet
    "AE": (0.5, 0.2, 0.0),  # bat / back
    "AA": (0.0, 1.5, 0.5),  # father / hot
    "AO": (1.0, 1.9, 0.5),  # bought / law
    "OW": (2.0, 1.9, 1.0),  # boat / soul
    "UH": (2.5, 1.7, 0.0),  # book
    "UW": (3.0, 2.0, 1.0),  # boot / true
    "AH": (1.2, 1.0, 0.0),  # but / love / sofa
    "ER": (1.8, 1.0, 0.5),  # bird / hurt
    "AY": (0.6, 0.6, 1.0),  # bite / night / time
    "AW": (0.5, 1.4, 1.0),  # bout / crown
    "OY": (1.2, 1.4, 1.0),  # boy / noise
}

# Consonant features: (place [0..5], manner [0=stop,1=affricate,2=fricative,3=nasal,4=liquid,5=glide], voiced [0/1])
CONSONANT_FEATURES = {
    "P": (0, 0, 0), "B": (0, 0, 1),
    "T": (2, 0, 0), "D": (2, 0, 1),
    "K": (4, 0, 0), "G": (4, 0, 1),
    "CH": (3, 1, 0), "JH": (3, 1, 1),
    "F": (1, 2, 0), "V": (1, 2, 1),
    "TH": (1, 2, 0), "DH": (1, 2, 1),
    "S": (2, 2, 0), "Z": (2, 2, 1),
    "SH": (3, 2, 0), "ZH": (3, 2, 1),
    "HH": (5, 2, 0),
    "M": (0, 3, 1), "N": (2, 3, 1), "NG": (4, 3, 1),
    "L": (2, 4, 1), "R": (3, 4, 1),
    "W": (0, 5, 1), "Y": (3, 5, 1),
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "in", "on",
    "at", "by", "for", "with", "is", "am", "are", "was", "were", "be", "been",
    "it", "its", "this", "that", "these", "those", "i", "me", "my", "you", "your",
    "he", "him", "his", "she", "her", "we", "us", "our", "they", "them", "their",
    "as", "so", "do", "did", "does", "have", "has", "had", "just", "from", "into",
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "dengan", "untuk", "pada",
    "adalah", "akan", "sudah", "telah", "juga", "atau", "dalam", "tidak", "tak",
}


def vowel_similarity(v1: str, v2: str) -> float:
    b1 = re.sub(r"\d", "", v1)
    b2 = re.sub(r"\d", "", v2)
    if b1 == b2:
        return 1.0
    f1 = VOWEL_FEATURES.get(b1)
    f2 = VOWEL_FEATURES.get(b2)
    if not f1 or not f2:
        return 0.0
    dist = math.sqrt((f1[0] - f2[0]) ** 2 + (f1[1] - f2[1]) ** 2 + 0.8 * (f1[2] - f2[2]) ** 2)
    return max(0.0, 1.0 - (dist / 3.2))


def consonant_seq_similarity(cseq1: tuple[str, ...], cseq2: tuple[str, ...]) -> float:
    if cseq1 == cseq2:
        return 1.0
    if not cseq1 or not cseq2:
        return 0.25 if (len(cseq1) + len(cseq2) == 1) else 0.0

    # Compare aligned trailing consonants (coda anchor)
    max_len = max(len(cseq1), len(cseq2))
    min_len = min(len(cseq1), len(cseq2))
    score = 0.0
    for i in range(1, min_len + 1):
        c1 = cseq1[-i]
        c2 = cseq2[-i]
        if c1 == c2:
            score += 1.0
            continue
        f1 = CONSONANT_FEATURES.get(c1)
        f2 = CONSONANT_FEATURES.get(c2)
        if f1 and f2:
            same_manner = 1.0 if f1[1] == f2[1] else 0.0
            same_place = 1.0 if abs(f1[0] - f2[0]) <= 1 else 0.0
            same_voice = 1.0 if f1[2] == f2[2] else 0.0
            # Same manner + near place (e.g. T/K, N/M, D/G) forms classic hip-hop slant consonance
            pair_sim = 0.45 * same_manner + 0.35 * same_place + 0.20 * same_voice
            score += pair_sim
    return score / float(max_len)


# =====================================================================
# CURATED PRONUNCIATION OVERRIDES + G2P (ENGLISH & BAHASA MELAYU)
# =====================================================================
EN_ARPABET_OVERRIDES = {
    "night": ["N", "AY1", "T"],
    "light": ["L", "AY1", "T"],
    "write": ["R", "AY1", "T"],
    "right": ["R", "AY1", "T"],
    "sight": ["S", "AY1", "T"],
    "fight": ["F", "AY1", "T"],
    "tight": ["T", "AY1", "T"],
    "flight": ["F", "L", "AY1", "T"],
    "might": ["M", "AY1", "T"],
    "soul": ["S", "OW1", "L"],
    "sole": ["S", "OW1", "L"],
    "goal": ["G", "OW1", "L"],
    "role": ["R", "OW1", "L"],
    "roll": ["R", "OW1", "L"],
    "cold": ["K", "OW1", "L", "D"],
    "gold": ["G", "OW1", "L", "D"],
    "hold": ["HH", "OW1", "L", "D"],
    "sold": ["S", "OW1", "L", "D"],
    "told": ["T", "OW1", "L", "D"],
    "old": ["OW1", "L", "D"],
    "flow": ["F", "L", "OW1"],
    "show": ["SH", "OW1"],
    "know": ["N", "OW1"],
    "go": ["G", "OW1"],
    "so": ["S", "OW1"],
    "pain": ["P", "EY1", "N"],
    "rain": ["R", "EY1", "N"],
    "brain": ["B", "R", "EY1", "N"],
    "chain": ["CH", "EY1", "N"],
    "stain": ["S", "T", "EY1", "N"],
    "lane": ["L", "EY1", "N"],
    "mane": ["M", "EY1", "N"],
    "heart": ["HH", "AA1", "R", "T"],
    "dark": ["D", "AA1", "R", "K"],
    "spark": ["S", "P", "AA1", "R", "K"],
    "start": ["S", "T", "AA1", "R", "T"],
    "part": ["P", "AA1", "R", "T"],
    "love": ["L", "AH1", "V"],
    "enough": ["IH0", "N", "AH1", "F"],
    "tough": ["T", "AH1", "F"],
    "rough": ["R", "AH1", "F"],
    "through": ["TH", "R", "UW1"],
    "true": ["T", "R", "UW1"],
    "blue": ["B", "L", "UW1"],
    "crew": ["K", "R", "UW1"],
    "ride": ["R", "AY1", "D"],
    "time": ["T", "AY1", "M"],
    "life": ["L", "AY1", "F"],
    "grind": ["G", "R", "AY1", "N", "D"],
    "mind": ["M", "AY1", "N", "D"],
    "blind": ["B", "L", "AY1", "N", "D"],
    "blank": ["B", "L", "AE1", "NG", "K"],
    "think": ["TH", "IH1", "NG", "K"],
    "drink": ["D", "R", "IH1", "NG", "K"],
    "ink": ["IH1", "NG", "K"],
    "perfect": ["P", "ER1", "F", "IH0", "K", "T"],
    "worthless": ["W", "ER1", "TH", "L", "AH0", "S"],
    "timing": ["T", "AY1", "M", "IH0", "NG"],
    "climbing": ["K", "L", "AY1", "M", "IH0", "NG"],
    "running": ["R", "AH1", "N", "IH0", "NG"],
    "coming": ["K", "AH1", "M", "IH0", "NG"],
    "away": ["AH0", "W", "EY1"],
    "play": ["P", "L", "EY1"],
    "day": ["D", "EY1"],
    "pavement": ["P", "EY1", "V", "M", "AH0", "N", "T"],
    "back": ["B", "AE1", "K"],
    "crack": ["K", "R", "AE1", "K"],
    "track": ["T", "R", "AE1", "K"],
    "stack": ["S", "T", "AE1", "K"],
    "weird": ["W", "IH1", "R", "D"],
    "beard": ["B", "IH1", "R", "D"],
    "feared": ["F", "IH1", "R", "D"],
    "cleared": ["K", "L", "IH1", "R", "D"],
    "cap": ["K", "AE1", "P"],
    "trap": ["T", "R", "AE1", "P"],
    "rap": ["R", "AE1", "P"],
    "map": ["M", "AE1", "P"],
    "drip": ["D", "R", "IH1", "P"],
    "flip": ["F", "L", "IH1", "P"],
    "clip": ["K", "L", "IH1", "P"],
    "slip": ["S", "L", "IH1", "P"],
    "plug": ["P", "L", "AH1", "G"],
    "mug": ["M", "AH1", "G"],
    "thug": ["TH", "AH1", "G"],
    "opps": ["AA1", "P", "S"],
    "cops": ["K", "AA1", "P", "S"],
    "drops": ["D", "R", "AA1", "P", "S"],
    "tops": ["T", "AA1", "P", "S"],
    "bands": ["B", "AE1", "N", "D", "Z"],
    "hands": ["HH", "AE1", "N", "D", "Z"],
    "stands": ["S", "T", "AE1", "N", "D", "Z"],
    "lit": ["L", "IH1", "T"],
    "hit": ["HH", "IH1", "T"],
    "spit": ["S", "P", "IH1", "T"],
    "shit": ["SH", "IH1", "T"],
    "bitch": ["B", "IH1", "CH"],
    "rich": ["R", "IH1", "CH"],
    "switch": ["S", "W", "IH1", "CH"],
    "drowning": ["D", "R", "AW1", "N", "IH0", "NG"],
    "crowning": ["K", "R", "AW1", "N", "IH0", "NG"],
    "thoughts": ["TH", "AO1", "T", "S"],
    "shots": ["SH", "AA1", "T", "S"],
}

BM_LEXICON_HINTS = {
    "padu", "tapau", "lepak", "kantoi", "bantai", "sembang", "kencang", "kaku",
    "ludah", "lawan", "susun", "kata", "tajam", "senang", "hati", "jalan", "gelap",
    "lampu", "terang", "tinggi", "gua", "lu", "bro", "weh", "lah", "mantap",
    "kacip", "barai", "santai", "gerak", "pacak", "tumbang", "menang", "tenang",
    "hilang", "terbang", "datang", "pulang", "bintang", "gelombang", "malam",
    "dalam", "salam", "diam", "hitam", "azam", "tajam", "faham", "paham",
    "jiwa", "dunia", "raja", "kota", "mata", "nyata", "cinta", "cerita",
    "api", "mati", "pasti", "nanti", "hari", "lari", "cari", "diri", "berdiri",
    "api", "mimpi", "sepi", "tepi", "kopi", "topi", "syok", "gempak", "padu",
    "merecik", "hawau", "sakai", "poyo", "bajet", "koyak", "rabak", "cilok",
    "rembat", "hensem", "cun", "ngam", "steady", "rilek", "hal", "asal", "pasal",
    "akal", "kekal", "kebal", "tebal", "gagal", "mahal", "kapal", "sampai",
    "ramai", "damai", "pantai", "rantai", "selesai", "perangai", "bagus", "hangus",
    "terus", "lurus", "kurus", "urus", "tulus", "mulus", "modus", "fokus",
}


def detect_word_language(word_low: str, custom_bm_words: set[str]) -> str:
    if word_low in BM_LEXICON_HINTS or word_low in custom_bm_words:
        return "BM"
    if word_low in EN_ARPABET_OVERRIDES:
        return "EN"
    if _lookup_cmu_phones(word_low):
        return "EN"
    # Malay morphological / phonotactic cues
    if re.search(r"(ny|sy|kh|ng$|[aeiou]k$|[aeiou]h$)", word_low) and not re.search(r"(th|sh|ch|ph|wh|ight|tion|ough)", word_low):
        if re.match(r"^(me|ber|ter|pe|se|ke|di)", word_low) or re.search(r"(kan|an|i)$", word_low):
            return "BM"
        if re.search(r"(ai|au|oi)$", word_low):
            return "BM"
    return "EN"


def transcribe_bm_to_arpabet(word_low: str) -> list[str]:
    """Converts Bahasa Melayu / Manglish words into accurate ARPAbet syllable phonemes."""
    w = re.sub(r"[^a-z]", "", word_low)
    if not w:
        return []

    # Colloquial contractions / Manglish reductions
    colloquial = {
        "tak": ["T", "AA1", "K"],
        "nak": ["N", "AA1", "K"],
        "dah": ["D", "AA1", "HH"],
        "kan": ["K", "AA1", "N"],
        "lah": ["L", "AA1", "HH"],
        "weh": ["W", "EH1", "HH"],
        "gua": ["G", "W", "AA1"],
        "lu": ["L", "UW1"],
        "syok": ["SH", "AO1", "K"],
        "ngam": ["NG", "AA1", "M"],
        "cun": ["CH", "UW1", "N"],
        "rilek": ["R", "IY1", "L", "EH0", "K"],
    }
    if w in colloquial:
        return colloquial[w]

    # Tokenize into consonant clusters & vowel/diphthong nuclei
    tokens = []
    i = 0
    while i < len(w):
        digraph = w[i:i + 2]
        if digraph in ("ng", "ny", "sy", "kh", "gh", "ai", "au", "oi"):
            tokens.append(digraph)
            i += 2
        else:
            tokens.append(w[i])
            i += 1

    vowel_map = {
        "a": "AA",
        "e": "EH",
        "i": "IY",
        "o": "OW",
        "u": "UW",
        "ai": "AY",
        "au": "AW",
        "oi": "OY",
    }
    cons_map = {
        "b": "B", "c": "CH", "d": "D", "f": "F", "g": "G", "h": "HH",
        "j": "JH", "k": "K", "l": "L", "m": "M", "n": "N", "p": "P",
        "q": "K", "r": "R", "s": "S", "t": "T", "v": "V", "w": "W",
        "x": "K", "y": "Y", "z": "Z", "ng": "NG", "ny": "N", "sy": "SH",
        "kh": "K", "gh": "G",
    }

    # Count vowel nuclei to assign penultimate stress (standard Malay prosody)
    vowel_indices = [idx for idx, tk in enumerate(tokens) if tk in vowel_map]
    if not vowel_indices:
        return ["AH1"]

    stressed_v_pos = vowel_indices[-2] if len(vowel_indices) >= 2 else vowel_indices[-1]
    # If penultimate vowel is schwa 'e' before single consonant, stress shifts to final syllable
    if len(vowel_indices) >= 2 and tokens[stressed_v_pos] == "e":
        stressed_v_pos = vowel_indices[-1]

    phones = []
    for idx, tk in enumerate(tokens):
        if tk in vowel_map:
            base_v = vowel_map[tk]
            # Final closed syllable 'i' or 'u' relaxes slightly toward IH/UH in spoken BM
            if idx == vowel_indices[-1] and idx < len(tokens) - 1:
                if tk == "i":
                    base_v = "IH"
                elif tk == "u":
                    base_v = "UH"
            stress = "1" if idx == stressed_v_pos else "0"
            phones.append(f"{base_v}{stress}")
        elif tk in cons_map:
            # Final 'k' in Malay is a glottal stop / unreleased K
            phones.append(cons_map[tk])

    return phones


def fallback_en_g2p(word_low: str) -> list[str]:
    """Rule-based English Grapheme-to-Phoneme ARPAbet transcriber when CMUdict lacks a word."""
    w = re.sub(r"[^a-z']", "", word_low)
    if not w:
        return []

    # Handle common contractions cleanly
    if w.endswith("in'"):
        stem = w[:-3] + "ing"
        if stem in EN_ARPABET_OVERRIDES:
            return EN_ARPABET_OVERRIDES[stem]
    if w.endswith("'s"):
        base = fallback_en_g2p(w[:-2])
        return base + ["Z"] if base else ["Z"]
    if w.endswith("n't"):
        base = fallback_en_g2p(w[:-3])
        return base + ["N", "T"] if base else ["N", "T"]

    # Common morphological suffixes
    suffix_phones = []
    stem = w
    if len(stem) > 5 and stem.endswith("tion"):
        stem = stem[:-4]
        suffix_phones = ["SH", "AH0", "N"]
    elif len(stem) > 5 and stem.endswith("sion"):
        stem = stem[:-4]
        suffix_phones = ["ZH", "AH0", "N"]
    elif len(stem) > 4 and stem.endswith("ing"):
        stem = stem[:-3]
        suffix_phones = ["IH0", "NG"]
    elif len(stem) > 4 and stem.endswith("ly"):
        stem = stem[:-2]
        suffix_phones = ["L", "IY0"]
    elif len(stem) > 4 and stem.endswith("er"):
        stem = stem[:-2]
        suffix_phones = ["ER0"]

    silent_e = False
    if len(stem) >= 4 and stem.endswith("e") and stem[-2] not in "aeiouy" and stem[-3] in "aeiouy":
        silent_e = True
        stem = stem[:-1]

    long_vowel_map = {"a": "EY", "e": "IY", "i": "AY", "o": "OW", "u": "UW", "y": "AY"}
    short_vowel_map = {"a": "AE", "e": "EH", "i": "IH", "o": "AA", "u": "AH", "y": "IH"}
    digraph_vowels = {
        "ai": "EY", "ay": "EY", "ea": "IY", "ee": "IY", "ei": "EY", "ey": "IY",
        "ie": "IY", "oa": "OW", "oe": "OW", "oi": "OY", "oy": "OY", "oo": "UW",
        "ou": "AW", "ow": "OW", "ue": "UW", "ui": "UW", "au": "AO", "aw": "AO",
    }
    digraph_cons = {
        "ch": ["CH"], "sh": ["SH"], "th": ["TH"], "ph": ["F"], "wh": ["W"],
        "ck": ["K"], "ng": ["NG"], "qu": ["K", "W"], "gh": [],
    }
    single_cons = {
        "b": "B", "c": "K", "d": "D", "f": "F", "g": "G", "h": "HH",
        "j": "JH", "k": "K", "l": "L", "m": "M", "n": "N", "p": "P",
        "r": "R", "s": "S", "t": "T", "v": "V", "w": "W", "x": "K", "z": "Z",
    }

    phones = []
    heavy_idx = -1  # final long vowel (silent-e / "igh") -> carries secondary stress like CMUdict
    i = 0
    while i < len(stem):
        pair = stem[i:i + 2]
        if stem[i:i + 3] == "igh":
            phones.append("AY")
            heavy_idx = len(phones) - 1
            i += 3
        elif pair in digraph_vowels:
            phones.append(digraph_vowels[pair])
            i += 2
        elif pair in digraph_cons:
            phones.extend(digraph_cons[pair])
            i += 2
        elif stem[i] in "aeiouy":
            ch = stem[i]
            # R-controlled vowels
            if i + 1 < len(stem) and stem[i + 1] == "r":
                if ch in ("e", "i", "u"):
                    phones.append("ER")
                elif ch == "a":
                    phones.append("AA")
                else:
                    phones.append("AO")
                i += 1
            elif ch == "y" and i == len(stem) - 1 and any(c in "aeiou" for c in stem[:i]):
                phones.append("IY")  # word-final y in a polysyllable: 'ready', 'heavy' -> /iy/
            else:
                # Open syllable at end or silent-e stem
                is_last_vowel = not any(c in "aeiouy" for c in stem[i + 1:])
                if is_last_vowel and (silent_e or i == len(stem) - 1):
                    if silent_e:
                        heavy_idx = len(phones)
                    phones.append(long_vowel_map[ch])
                else:
                    phones.append(short_vowel_map[ch])
            i += 1
        elif stem[i] in single_cons:
            # Collapse doubled consonants
            if i + 1 < len(stem) and stem[i + 1] == stem[i]:
                i += 1
            phones.append(single_cons[stem[i]])
            i += 1
        else:
            i += 1

    # Assign primary stress to first vowel nucleus in stem
    stressed_assigned = False
    out = []
    for p_idx, ph in enumerate(phones):
        if ph in VOWEL_FEATURES:
            if not stressed_assigned:
                out.append(f"{ph}1")
                stressed_assigned = True
            elif p_idx == heavy_idx:
                out.append(f"{ph}2")
            else:
                out.append(f"{ph}0")
        else:
            out.append(ph)

    out.extend(suffix_phones)
    if not any(re.sub(r"\d", "", p) in VOWEL_FEATURES for p in out):
        out.insert(0, "AH1")
    return out


# =====================================================================
# RHYME TAIL & SYLLABLE EXTRACTION
# =====================================================================
def extract_syllable_units(phones: list[str]) -> list[dict]:
    """
    Splits an ARPAbet phoneme list into syllable units:
    [{"vowel": "AY", "stress": 1, "coda": ("T",)}, ...]
    """
    vowel_positions = [
        i for i, p in enumerate(phones)
        if re.sub(r"\d", "", p) in VOWEL_FEATURES
    ]
    if not vowel_positions:
        return []

    units = []
    for idx, v_pos in enumerate(vowel_positions):
        raw_v = phones[v_pos]
        v_base = re.sub(r"\d", "", raw_v)
        stress_m = re.search(r"(\d)", raw_v)
        stress = int(stress_m.group(1)) if stress_m else 0

        next_v_pos = vowel_positions[idx + 1] if idx + 1 < len(vowel_positions) else len(phones)
        inter_cons = phones[v_pos + 1:next_v_pos]

        # Maximal onset principle: keep final consonant(s) as coda for the last syllable,
        # or split medial clusters so stressed syllables retain coda weight
        if idx == len(vowel_positions) - 1:
            coda = tuple(inter_cons)
        elif len(inter_cons) <= 1:
            coda = tuple(inter_cons) if stress >= 1 else ()
        else:
            coda = tuple(inter_cons[:-1])

        units.append({
            "vowel": v_base,
            "stress": stress,
            "coda": coda,
        })
    return units


def score_rhyme_pair(units_a: list[dict], units_b: list[dict]) -> tuple[float, str, int]:
    """
    Near-rhyme scorer for ungrouped line-end pairs (Slant Rhyme / Assonance / Consonance).
    Perfect rhymes are handled exclusively by _token_rhyme_key bucketing.
    """
    if not units_a or not units_b:
        return 0.0, "None", 0

    tail_a = _rhyme_tail_units(units_a)
    tail_b = _rhyme_tail_units(units_b)
    if not tail_a or not tail_b:
        return 0.0, "None", 0

    comp_len = min(len(tail_a), len(tail_b))
    len_penalty = 0.72 if len(tail_a) != len(tail_b) else 1.0

    syl_scores = []
    for idx in range(comp_len):
        ua = tail_a[idx]
        ub = tail_b[idx]
        v_sim = vowel_similarity(ua["vowel"], ub["vowel"])
        c_sim = consonant_seq_similarity(ua["coda"], ub["coda"])
        syl_scores.append(0.65 * v_sim + 0.35 * c_sim)

    if not syl_scores:
        return 0.0, "None", 0

    raw_conf = (sum(syl_scores) / float(len(syl_scores))) * len_penalty * 100.0

    u0_a, u0_b = tail_a[0], tail_b[0]
    v0_sim = vowel_similarity(u0_a["vowel"], u0_b["vowel"])
    c0_sim = consonant_seq_similarity(u0_a["coda"], u0_b["coda"])

    if v0_sim >= 0.85 and c0_sim < 0.45:
        category = "Assonance"
        raw_conf = min(raw_conf, 84.0)
    elif v0_sim < 0.60 and c0_sim >= 0.85 and u0_a["coda"]:
        category = "Consonance"
        raw_conf = min(raw_conf, 76.0)
    elif raw_conf >= 62.0:
        category = "Slant Rhyme"
    else:
        category = "None"

    return round(min(99.0, raw_conf), 1), category, 1


# =====================================================================
# CONTEXTUAL WORDPLAY, HOMOPHONES & BILINGUAL SLANG ENGINE
# =====================================================================
HOMOPHONE_PAIRS = {
    "write": ("right", "Homophone: 'write' (pen lyrics) / 'right' (correct / direction)"),
    "right": ("write", "Homophone: 'right' (correct / privilege) / 'write' (compose)"),
    "soul": ("sole", "Homophone: 'soul' (spirit / emotion) / 'sole' (shoe bottom / only)"),
    "sole": ("soul", "Homophone: 'sole' (sneaker bottom / lone) / 'soul' (spirit)"),
    "night": ("knight", "Homophone: 'night' (darkness) / 'knight' (armored warrior)"),
    "knight": ("night", "Homophone: 'knight' (warrior) / 'night' (after dark)"),
    "pain": ("pane", "Homophone: 'pain' (suffering) / 'pane' (window glass)"),
    "pane": ("pain", "Homophone: 'pane' (glass) / 'pain' (ache)"),
    "rain": ("reign", "Homophone: 'rain' (weather) / 'reign' (royal rule)"),
    "reign": ("rain", "Homophone: 'reign' (rule) / 'rain' (storm)"),
    "blew": ("blue", "Homophone: 'blew' (past of blow / spent fast) / 'blue' (color / sad)"),
    "blue": ("blew", "Homophone: 'blue' (color / melancholy) / 'blew' (blew up / spent)"),
    "peace": ("piece", "Homophone: 'peace' (calm) / 'piece' (firearm / slice)"),
    "piece": ("peace", "Homophone: 'piece' (gun / slice) / 'peace' (serenity)"),
    "steal": ("steel", "Homophone: 'steal' (rob) / 'steel' (metal / blade)"),
    "steel": ("steal", "Homophone: 'steel' (metal) / 'steal' (take)"),
    "weight": ("wait", "Homophone: 'weight' (heavy burden / product) / 'wait' (patience)"),
    "wait": ("weight", "Homophone: 'wait' (pause) / 'weight' (pressure / mass)"),
    "break": ("brake", "Homophone: 'break' (shatter / lucky break) / 'brake' (stop)"),
    "brake": ("break", "Homophone: 'brake' (slow down) / 'break' (fracture)"),
    "sight": ("site", "Homophone: 'sight' (vision / gun scope) / 'site' (location)"),
    "hear": ("here", "Homophone: 'hear' (listen) / 'here' (present place)"),
    "here": ("hear", "Homophone: 'here' (this spot) / 'hear' (perceive sound)"),
}

# Contextual double-entendre rules:
# Triggered ONLY when target word co-occurs with a semantic foil in the same or adjacent bar
CONTEXTUAL_DOUBLE_ENTENDRES = [
    {
        "trigger": "ice",
        "foils": {"cold", "freeze", "frozen", "wrist", "chain", "neck", "water", "melt", "drip", "diamonds", "vvs"},
        "label": "Double Entendre (88%)",
        "note": "Wordplay: 'ice' = diamonds/jewelry vs. freezing temperature",
        "conf": 88.0,
    },
    {
        "trigger": "cold",
        "foils": {"ice", "freeze", "winter", "heart", "stone", "flow", "mic", "booth", "spit", "bars"},
        "label": "Double Entendre / Slang (84%)",
        "note": "Contextual Slang: 'cold' = ruthless/impressive delivery vs. literal temperature",
        "conf": 84.0,
    },
    {
        "trigger": "bars",
        "foils": {"prison", "cell", "jail", "lock", "spit", "pen", "verse", "gold", "xan", "booth", "heavy"},
        "label": "Double Entendre (91%)",
        "note": "Wordplay: 'bars' = 16-bar rap verses vs. prison cell bars / gold bullion",
        "conf": 91.0,
    },
    {
        "trigger": "crown",
        "foils": {"heavy", "king", "head", "queen", "throne", "teeth", "gold", "royalty"},
        "label": "Double Entendre (86%)",
        "note": "Wordplay: 'crown' = royal sovereignty vs. dental gold crown / top of head",
        "conf": 86.0,
    },
    {
        "trigger": "cap",
        "foils": {"no", "lie", "lying", "shoot", "gun", "head", "hat", "starter", "fitted", "truth"},
        "label": "Slang / Wordplay (89%)",
        "note": "Contextual Slang: 'cap' = lie/exaggeration ('no cap') vs. fitted hat / bullet",
        "conf": 89.0,
    },
    {
        "trigger": "plug",
        "foils": {"connect", "wire", "spark", "socket", "charge", "supply", "pack", "call", "line"},
        "label": "Slang / Double Entendre (85%)",
        "note": "Contextual Slang: 'plug' = supplier/connection vs. electrical outlet",
        "conf": 85.0,
    },
    {
        "trigger": "drip",
        "foils": {"water", "ice", "sink", "faucet", "fit", "designer", "sauce", "wet", "drown"},
        "label": "Slang / Metaphor (85%)",
        "note": "Contextual Slang: 'drip' = luxury style/jewelry vs. falling water",
        "conf": 85.0,
    },
    {
        "trigger": "bands",
        "foils": {"rubber", "cash", "money", "stack", "rack", "play", "stage", "guitar", "drum"},
        "label": "Slang / Double Entendre (86%)",
        "note": "Contextual Slang: 'bands' = $1,000 cash stacks vs. musical bands",
        "conf": 86.0,
    },
    {
        "trigger": "lit",
        "foils": {"fire", "match", "flame", "smoke", "crowd", "club", "night", "burn", "spark"},
        "label": "Slang / Double Entendre (82%)",
        "note": "Contextual Slang: 'lit' = high-energy/exciting vs. ignited with fire",
        "conf": 82.0,
    },
    {
        "trigger": "scope",
        "foils": {"sniper", "aim", "shoot", "eye", "vision", "range", "graze", "missed"},
        "label": "Double Entendre (84%)",
        "note": "Wordplay: 'scope' = rifle optic vs. range of vision/ambition",
        "conf": 84.0,
    },
    {
        "trigger": "tapau",
        "foils": {"habis", "bungkus", "semua", "lawan", "game", "beat", "kalah", "makan"},
        "label": "BM Slang / Double Entendre (90%)",
        "note": "BM Slang: 'tapau' = wipe out / dominate opponents vs. takeaway food",
        "conf": 90.0,
    },
    {
        "trigger": "sembang",
        "foils": {"kencang", "kosong", "lebat", "kari", "lebih", "poyo", "bajet", "bukan"},
        "label": "BM Slang / Idiom (92%)",
        "note": "BM Slang: 'sembang kencang/kosong' = all talk / bluffing without proof",
        "conf": 92.0,
    },
    {
        "trigger": "kacip",
        "foils": {"otak", "kepala", "pinang", "pening", "sangkut", "high", "layan"},
        "label": "BM Street Slang (87%)",
        "note": "BM Street Slang: 'kacip' = mentally locked/tripping vs. betel-nut cutter",
        "conf": 87.0,
    },
]

RHYME_PALETTE = [
    ("#441579", "#EFE2FD"),
    ("#157915", "#E2FDE2"),
    ("#C2230A", "#FDE6E2"),
    ("#156579", "#E2F8FD"),
    ("#0C0CDF", "#E2E2FD"),
    ("#C20A6C", "#FDE2F1"),
    ("#825F2B", "#FDF2E2"),
    ("#A90AC2", "#FAE2FD"),
    ("#6B2432", "#FDE2E7"),
    ("#3B62B0", "#E2EBFD"),
    ("#0C52DF", "#E2EBFD"),
    ("#157958", "#E2FDF4"),
    ("#822B6B", "#FDE2F6"),
    ("#A50932", "#FDE2E9"),
    ("#883207", "#FDEBE2"),
    ("#2809A5", "#E7E2FD"),
    ("#586B24", "#F6FDE2"),
    ("#A50990", "#FDE2FA"),
    ("#24406B", "#E2EDFD"),
    ("#893BB0", "#F4E2FD"),
    ("#24286B", "#E2E4FD"),
    ("#093DA5", "#E2EBFD"),
    ("#8A0CDF", "#F2E2FD"),
    ("#931A4B", "#FDE2ED"),
]

def _strip_stress(phones: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(re.sub(r"\d", "", p) for p in phones)

def _build_phoneme_indexes() -> None:
    global _PHONEME_TO_WORDS, _MALAY_PHONEME_INDEX
    if _PHONEME_TO_WORDS:
        return
    for word, prons in _CMU_DICT.items():
        if not word.isalpha() or len(word) < 2:
            continue
        for p in prons:
            key = _strip_stress(p)
            bucket = _PHONEME_TO_WORDS.setdefault(key, [])
            if word not in bucket:
                bucket.append(word)

    for bm in set(_COMMON_BM_PUN_WORDS) | BM_LEXICON_HINTS:
        phones = transcribe_bm_to_arpabet(bm)
        if phones:
            key = _strip_stress(phones)
            bucket = _MALAY_PHONEME_INDEX.setdefault(key, [])
            if bm not in bucket:
                bucket.append(bm)

def generate_wordplay_ideas(word: str, max_results: int = 8) -> dict:
    """
    Dynamically generates exact homophones, 2-word phonetic splits (oronyms),
    near-homophone flips, and cross-lingual (EN <-> BM) phonetic matches.
    """
    _build_phoneme_indexes()
    clean = re.sub(r"[^a-zA-Z'-]", "", word).lower().strip("'-")
    result = {
        "word": clean,
        "homophones": [],
        "oronyms": [],
        "bilingual_flips": [],
        "near_flips": [],
    }
    if not clean or len(clean) < 2:
        return result

    target_keys: list[tuple[str, ...]] = []
    prons = _all_cmu_pronunciations(clean)
    if prons:
        for p in prons:
            k = _strip_stress(p)
            if k not in target_keys:
                target_keys.append(k)
    else:
        prof = LEXICON.get_phonetic_profile(clean)
        if prof["phones"]:
            target_keys.append(_strip_stress(prof["phones"]))

    if not target_keys:
        return result

    for key in target_keys:
        # 1. Exact English Homophones
        for cand in _PHONEME_TO_WORDS.get(key, []):
            if cand != clean and cand not in result["homophones"]:
                result["homophones"].append(cand)

        # 2. Cross-Lingual EN <-> BM Exact Phonetic Matches
        for bm_cand in _MALAY_PHONEME_INDEX.get(key, []):
            if bm_cand != clean and bm_cand not in result["bilingual_flips"]:
                result["bilingual_flips"].append(bm_cand)

        # 3. 2-Word Phonetic Splits / Oronyms (e.g., "forgive" -> "four give")
        if len(key) >= 4:
            for split_idx in range(2, len(key) - 1):
                left_key = key[:split_idx]
                right_key = key[split_idx:]
                left_words = [w for w in _PHONEME_TO_WORDS.get(left_key, []) if len(w) >= 2][:4]
                right_words = [w for w in _PHONEME_TO_WORDS.get(right_key, []) if len(w) >= 2][:4]
                for lw in left_words:
                    for rw in right_words:
                        phrase = f"{lw} {rw}"
                        if phrase != clean and phrase not in result["oronyms"]:
                            result["oronyms"].append(phrase)
                        if len(result["oronyms"]) >= max_results:
                            break
                    if len(result["oronyms"]) >= max_results:
                        break

        # 4. Near-Homophone Flips (1-phoneme edit distance for slant punchlines)
        if len(key) >= 3 and len(result["near_flips"]) < max_results:
            for cand_key, cand_words in _PHONEME_TO_WORDS.items():
                if len(cand_key) != len(key) or cand_key == key:
                    continue
                if cand_key[0] == key[0] and cand_key[-1] == key[-1]:
                    diffs = sum(1 for a, b in zip(key, cand_key) if a != b)
                    if diffs == 1:
                        for cw in cand_words:
                            if cw != clean and cw not in result["near_flips"]:
                                result["near_flips"].append(cw)
                                if len(result["near_flips"]) >= max_results:
                                    break
                if len(result["near_flips"]) >= max_results:
                    break

    result["homophones"] = result["homophones"][:max_results]
    result["bilingual_flips"] = result["bilingual_flips"][:max_results]
    result["oronyms"] = result["oronyms"][:max_results]
    result["near_flips"] = result["near_flips"][:max_results]
    return result
    
# Unambiguous modern English, AAVE, BM & Manglish slang (high precision, low false positive)
CONTEXTUAL_SLANG_LEXICON = {
    # English / Hip-Hop / AAVE
    "opps": ("EN Hip-Hop Slang", "Opposition / rivals / enemies", 92.0, None),
    "bussin": ("AAVE / Internet Slang", "Extremely good / impressive", 90.0, None),
    "rizz": ("Internet / Modern Slang", "Charisma / charm", 91.0, None),
    "finna": ("AAVE Slang", "Going to / preparing to", 93.0, None),
    "lowkey": ("Modern Slang", "Subtly / quietly / secretly", 88.0, None),
    "highkey": ("Modern Slang", "Openly / intensely", 88.0, None),
    "glizzy": ("Hip-Hop Slang", "Glock handgun (or hot dog)", 89.0, None),
    "choppa": ("Hip-Hop Slang", "Automatic rifle / AK-47", 94.0, None),
    "blammy": ("Hip-Hop Slang", "Firearm / handgun", 92.0, None),
    "vvs": ("Hip-Hop Jewelry Slang", "Very Very Slightly Included diamond clarity", 95.0, None),
    "benjamins": ("Hip-Hop Slang", "$100 bills (Benjamin Franklin)", 92.0, None),
    "racks": ("Hip-Hop Slang", "Stacks of $1,000 cash", 84.0, {"cash", "money", "bands", "stack", "count", "spent"}),
    "sauce": ("Hip-Hop Slang", "Swagger / unique style / confidence", 80.0, {"drip", "swag", "flow", "got", "lost", "too"}),
    "flex": ("Hip-Hop Slang", "Show off wealth or skill", 82.0, {"no", "hard", "wrist", "chain", "bag", "muscles"}),
    "ghost": ("Hip-Hop Slang", "Disappear / cut contact / ghostwrite", 80.0, {"went", "write", "pen", "whip", "ride"}),
    "spit": ("Hip-Hop Slang", "Rap / deliver verses", 84.0, {"bars", "mic", "fire", "flow", "verse", "booth", "rhyme"}),
    "booth": ("Studio Slang", "Vocal recording booth", 86.0, {"mic", "record", "track", "spit", "heart", "heat"}),
    # Bahasa Melayu / Pasar / Manglish
    "padu": ("BM Urban Slang", "Solid, heavy-hitting, top-tier quality", 91.0, None),
    "lepak": ("BM Pasar / Manglish", "Chill / hang out casually", 94.0, None),
    "kantoi": ("BM Pasar Slang", "Caught red-handed / exposed", 95.0, None),
    "bantai": ("BM Pasar Slang", "Go all out / thrash / improvise aggressively", 89.0, None),
    "gempak": ("BM Urban Slang", "Epic / awesome / explosive impact", 91.0, None),
    "merecik": ("BM Street Slang", "Fire / dripping with style ('merecik hawau')", 93.0, None),
    "hawau": ("Malaysian Slang", "Melaka/Urban exclamation for crazy/wild", 94.0, None),
    "koyak": ("BM Internet / Street Slang", "Mentally broken / triggered / defeated", 89.0, None),
    "rabak": ("BM Pasar Slang", "Wrecked / torn apart / exhausted", 90.0, None),
    "cilok": ("BM Street Slang", "Weave through traffic / sneak past", 91.0, None),
    "rembat": ("BM Pasar Slang", "Snatch / swipe / strike hard", 90.0, None),
    "poyo": ("BM Pasar Slang", "Fake / trying too hard / pretentious", 93.0, None),
    "bajet": ("BM Pasar Slang", "Acting like a big shot / bluffing", 88.0, None),
    "ngam": ("Manglish / BM Slang", "Perfect fit / on point / agreed", 92.0, None),
    "cun": ("Manglish / BM Slang", "Clean, sharp, looking good", 91.0, None),
    "mantap": ("BM Urban Slang", "Steady, powerful, well-executed", 90.0, None),
    "power": ("Manglish Slang", "Impressive / next-level skill", 78.0, {"memang", "gila", "bro", "weh", "lah", "padu", "sangat"}),
    "barai": ("BM Street Slang", "Burned out / exhausted / scattered", 91.0, None),
}

# Idiomatic multi-word phrases & figurative similes/metaphors
MULTIWORD_WORDPLAY_PATTERNS = [
    (re.compile(r"\bno\s+cap\b", re.IGNORECASE), "EN Slang (95%)", "Slang Phrase: 'no cap' = no lie / for real", 95.0),
    (re.compile(r"\bcold\s+as\s+ice\b", re.IGNORECASE), "Simile / Wordplay (88%)", "Simile + Wordplay: freezing temperature vs. cold jewelry/demeanor", 88.0),
    (re.compile(r"\bdrowning\s+in\s+(my\s+)?thoughts\b", re.IGNORECASE), "Metaphor (86%)", "Metaphor: overwhelmed by internal overthinking", 86.0),
    (re.compile(r"\bheavy\s+is\s+the\s+crown\b", re.IGNORECASE), "Idiom / Metaphor (90%)", "Idiom: the burden and responsibility of leadership/status", 90.0),
    (re.compile(r"\bbleeding\s+(truth|ink)\b", re.IGNORECASE), "Metaphor (85%)", "Metaphor: raw honesty poured onto paper", 85.0),
    (re.compile(r"\bsembang\s+(kencang|kosong|kari)\b", re.IGNORECASE), "BM Slang Idiom (94%)", "BM Slang: boasting / talking big without substance", 94.0),
    (re.compile(r"\bmerecik\s+hawau\b", re.IGNORECASE), "Malaysian Slang (96%)", "Malaysian Slang: undeniably fire / stylish", 96.0),
    (re.compile(r"\btak\s+masuk\s+akal\b", re.IGNORECASE), "BM Idiom (85%)", "BM Idiom: unbelievable / beyond logic", 85.0),
    (re.compile(r"\bpecah\s+kepala\b", re.IGNORECASE), "BM Metaphor (84%)", "BM Metaphor: racking one's brain / intense overthinking", 84.0),
]


# =====================================================================
# LEXICON MANAGER (PROFILE-SCOPED CUSTOM SLANG + LANGUAGE PACKS)
# =====================================================================
class LexiconManager:
    def __init__(self):
        self.profile_dir = None
        self.custom_slang = {}
        self.language_packs = {}
        self.active_pack_words = set()
        self.pron_overrides = {}
        self._phoneme_cache = {}

    def load_profile(self, profile_dir: str):
        self.profile_dir = profile_dir
        os.makedirs(self.profile_dir, exist_ok=True)
        self.custom_slang = {}
        self.language_packs = {}
        self.pron_overrides = {}
        self._phoneme_cache = {}  # never leak another profile's pronunciations

        pron_path = os.path.join(self.profile_dir, "pronunciations.json")
        if os.path.exists(pron_path):
            try:
                with open(pron_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for w, ent in (raw or {}).items():
                    if isinstance(ent, dict) and ent.get("phones"):
                        self.pron_overrides[w.strip().lower()] = {
                            "spec": str(ent.get("spec", "")),
                            "phones": [str(x) for x in ent["phones"]],
                        }
            except Exception:
                self.pron_overrides = {}

        slang_path = os.path.join(self.profile_dir, "custom_slang.json")
        if os.path.exists(slang_path):
            try:
                with open(slang_path, "r", encoding="utf-8") as f:
                    self.custom_slang = json.load(f)
            except Exception:
                self.custom_slang = {}

        packs_path = os.path.join(self.profile_dir, "language_packs.json")
        if os.path.exists(packs_path):
            try:
                with open(packs_path, "r", encoding="utf-8") as f:
                    self.language_packs = json.load(f)
            except Exception:
                self.language_packs = {}

        self._rebuild_active_pack_set()

    def _save_slang(self):
        if not self.profile_dir:
            return
        with open(os.path.join(self.profile_dir, "custom_slang.json"), "w", encoding="utf-8") as f:
            json.dump(self.custom_slang, f, indent=2, ensure_ascii=False)

    def _save_pron(self):
        if not self.profile_dir:
            return
        with open(os.path.join(self.profile_dir, "pronunciations.json"), "w", encoding="utf-8") as f:
            json.dump(self.pron_overrides, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _normalise_arpabet(tokens: list[str]) -> list[str] | None:
        """Accepts 'N AY1 T' / 'n ay t'. Returns None if any symbol is not ARPAbet."""
        out, any_stress = [], False
        for tk in tokens:
            base = re.sub(r"\d", "", tk).upper()
            if base not in VOWEL_FEATURES and base not in CONSONANT_FEATURES:
                return None
            digit = re.search(r"\d", tk)
            if base in VOWEL_FEATURES:
                if digit:
                    any_stress = True
                out.append(base + (digit.group(0) if digit else ""))
            else:
                out.append(base)
        if not any_stress:  # no stress marks given: primary stress on the last vowel
            last_v = max((i for i, p in enumerate(out) if re.sub(r"\d", "", p) in VOWEL_FEATURES), default=None)
            if last_v is None:
                return None
            out = [(p + ("1" if i == last_v else "0")) if re.sub(r"\d", "", p) in VOWEL_FEATURES else p
                   for i, p in enumerate(out)]
        return out

    def set_pronunciation(self, word: str, spec: str) -> list[str]:
        """
        Teaches the engine how *you* say a word. `spec` is either ARPAbet ('N AY1 T') or a
        respelling / rhyme word ('nite', 'sounds like fight'). Returns the stored phones ([] if invalid).
        """
        key = re.sub(r"^[^A-Za-z0-9']+|[^A-Za-z0-9']+$", "", word or "").lower()
        spec = (spec or "").strip()
        if not key or not spec:
            return []
        phones = self._normalise_arpabet(spec.replace(",", " ").split())
        if phones is None:
            cleaned = re.sub(r"(?i)^sounds?\s+like\s+", "", spec)
            parts = [w for w in re.findall(r"[A-Za-z']+", cleaned)]
            phones = []
            for w in parts:
                lw = w.lower()
                if lw == key:
                    return []
                saved = self.pron_overrides.pop(lw, None)
                try:
                    phones.extend(self.get_phonetic_profile(lw)["phones"])
                finally:
                    if saved is not None:
                        self.pron_overrides[lw] = saved
        if not phones or not any(re.sub(r"\d", "", p) in VOWEL_FEATURES for p in phones):
            return []
        self.pron_overrides[key] = {"spec": spec, "phones": phones}
        self._phoneme_cache = {}
        self._save_pron()
        return phones

    def remove_pronunciation(self, word: str):
        key = re.sub(r"^[^A-Za-z0-9']+|[^A-Za-z0-9']+$", "", word or "").lower()
        if key in self.pron_overrides:
            del self.pron_overrides[key]
            self._phoneme_cache = {}
            self._save_pron()

    def _save_packs(self):
        if not self.profile_dir:
            return
        with open(os.path.join(self.profile_dir, "language_packs.json"), "w", encoding="utf-8") as f:
            json.dump(self.language_packs, f, indent=2, ensure_ascii=False)

    def _rebuild_active_pack_set(self):
        words = set()
        for pdata in self.language_packs.values():
            if pdata.get("enabled", True):
                for w in pdata.get("words", []):
                    words.add(w.strip().lower())
        self.active_pack_words = words

    def add_custom_slang(self, word: str, meaning: str, tag: str = "CUSTOM SLANG"):
        key = word.strip().lower()
        if not key:
            return
        self.custom_slang[key] = {"meaning": meaning.strip(), "tag": tag.strip() or "CUSTOM SLANG"}
        self._save_slang()

    def remove_custom_slang(self, word: str):
        key = word.strip().lower()
        if key in self.custom_slang:
            del self.custom_slang[key]
            self._save_slang()

    def add_language_pack(self, pack_name: str, words: list[str]) -> int:
        clean = sorted(list({w.strip().lower() for w in words if len(w.strip()) >= 2}))
        existing = set(self.language_packs.get(pack_name, {}).get("words", []))
        merged = sorted(list(existing.union(clean)))
        self.language_packs[pack_name] = {"enabled": True, "words": merged}
        self._rebuild_active_pack_set()
        self._save_packs()
        return len(merged)

    def toggle_language_pack(self, pack_name: str, enabled: bool):
        if pack_name in self.language_packs:
            self.language_packs[pack_name]["enabled"] = bool(enabled)
            self._rebuild_active_pack_set()
            self._save_packs()

    def delete_language_pack(self, pack_name: str):
        if pack_name in self.language_packs:
            del self.language_packs[pack_name]
            self._rebuild_active_pack_set()
            self._save_packs()

    def get_phonetic_profile(self, word: str, force_lang: str | None = None) -> dict:
        w_low = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", word).lower()
        if not w_low:
            return {"word": word, "norm": "", "lang": "EN", "phones": [], "units": [], "syllables": 0,
                    "pron_override": False}

        cache_key = (w_low, force_lang)
        cached = self._phoneme_cache.get(cache_key)
        if cached is not None:
            return cached

        lang = force_lang or detect_word_language(w_low, self.active_pack_words)
        override = self.pron_overrides.get(w_low)
        phones = []

        if override:
            phones = list(override["phones"])
        elif w_low in EN_ARPABET_OVERRIDES:
            phones = list(EN_ARPABET_OVERRIDES[w_low])
            lang = "EN"
        elif lang == "BM":
            phones = transcribe_bm_to_arpabet(w_low)
        else:
            phones = _lookup_cmu_phones(w_low)
        if not phones:
            phones = fallback_en_g2p(w_low)

        units = extract_syllable_units(phones)
        syl_count = max(1, len(units)) if re.search(r"[a-z0-9]", w_low) else 0
        profile = {
            "word": word,
            "norm": w_low,
            "lang": lang,
            "phones": phones,
            "units": units,
            "syllables": syl_count,
            "pron_override": bool(override),
        }
        self._phoneme_cache[cache_key] = profile
        return profile


LEXICON = LexiconManager()
BUILTIN_EN_WORDS = sorted(list(EN_ARPABET_OVERRIDES.keys()))
BUILTIN_BM_WORDS = sorted(list(BM_LEXICON_HINTS))


# =====================================================================
# CORE ANALYSIS ENGINE (RHYMES, MULTISYLLABIC SEQUENCES & WORDPLAY)
# =====================================================================
def _is_known_english(w_low: str) -> bool:
    return w_low in EN_ARPABET_OVERRIDES or bool(_all_cmu_pronunciations(w_low))


def _is_ambiguous_word(w_low: str) -> bool:
    """A real English word that is also on the BM/slang hint lists (e.g. 'steady', 'power')."""
    hinted = w_low in BM_LEXICON_HINTS or w_low in LEXICON.active_pack_words
    return hinted and w_low not in EN_ARPABET_OVERRIDES and bool(_all_cmu_pronunciations(w_low))


def _line_language_for_ambiguous(matches) -> str:
    """Decides EN vs BM for ambiguous words from the rest of the line (English line => English)."""
    en_votes = bm_votes = 0
    for m in matches:
        w = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", m.group(0)).lower()
        hinted = w in BM_LEXICON_HINTS or w in LEXICON.active_pack_words
        if hinted and not _is_known_english(w):
            bm_votes += 1
        elif not hinted and _is_known_english(w):
            en_votes += 1
    return "EN" if en_votes > bm_votes else "BM"


def _tokenize_lyrics(text: str) -> tuple[list[dict], list[dict]]:
    """Preserves exact character offsets across lines, punctuation, and contractions."""
    lines_info = []
    tokens = []
    offset = 0

    for line_idx, raw_line in enumerate(text.splitlines(keepends=True)):
        clean_line = raw_line.rstrip("\r\n")
        stripped = clean_line.strip()
        is_header = bool(stripped.startswith("[") and stripped.endswith("]"))
        line_syllables = 0
        line_token_indices = []

        if not is_header and stripped:
            # Skip inline timestamps like [01:12]
            ts_spans = [(m.start(), m.end()) for m in re.finditer(r"\[\d{1,2}:\d{2}\]", clean_line)]

            line_matches = [
                m for m in re.finditer(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*'?", clean_line)
                if not any(ts_s <= m.start() < ts_e for ts_s, ts_e in ts_spans)
            ]
            ambiguous_lang = _line_language_for_ambiguous(line_matches)

            for m in line_matches:
                s_rel, e_rel = m.start(), m.end()

                raw_tok = m.group(0)
                w_low = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", raw_tok).lower()
                force = ambiguous_lang if _is_ambiguous_word(w_low) else None
                prof = LEXICON.get_phonetic_profile(raw_tok, force_lang=force)
                if prof["syllables"] == 0:
                    continue

                line_syllables += prof["syllables"]
                tok_idx = len(tokens)
                line_token_indices.append(tok_idx)

                tokens.append({
                    "idx": tok_idx,
                    "line": line_idx,
                    "start": offset + s_rel,
                    "end": offset + e_rel,
                    "rhyme_start": offset + s_rel,
                    "rhyme_end": offset + e_rel,
                    "word": raw_tok,
                    "norm": prof["norm"],
                    "lang": prof["lang"],
                    "phones": prof["phones"],
                    "units": prof["units"],
                    "syllables": prof["syllables"],
                    "pron_override": prof.get("pron_override", False),
                    "rhyme_parts": None,
                    "near_rhyme": None,
                    "is_repeat": False,
                    "is_stopword": prof["norm"] in STOPWORDS,
                    "is_line_end": False,
                    "rhyme_group": None,
                    "color_idx": None,
                    "rhyme_category": None,
                    "rhyme_confidence": 0.0,
                    "rhyme_explanation": "",
                    "multie_count": 1,
                    "wordplay": None,
                    "wordplay_confidence": 0.0,
                })

            if line_token_indices:
                tokens[line_token_indices[-1]]["is_line_end"] = True

        lines_info.append({
            "line": line_idx,
            "text": clean_line,
            "is_header": is_header,
            "syllables": line_syllables,
            "token_indices": line_token_indices,
        })
        offset += len(raw_line)

    return lines_info, tokens


def _rhyme_tail_units(units: list[dict]) -> list[dict]:
    """Returns syllable units starting at the last primary/secondary stressed vowel."""
    if not units:
        return []
    stressed = [i for i, u in enumerate(units) if u["stress"] in (1, 2)]
    start_idx = stressed[-1] if stressed else max(0, len(units) - 1)
    return units[start_idx:]


_ONSET_DIGRAPHS = ("sh", "ch", "th", "ph", "wh", "ck", "qu", "gh")


def _letter_vowel_groups(word: str, n_syllables: int) -> list[tuple[int, int]]:
    """
    Maps written vowel groups to spoken syllables. Drops a silent final 'e' and a leading
    consonant-'y', then returns the group spans only if they line up with the syllable count.
    """
    w = word.lower()
    groups = [m.span() for m in re.finditer(r"[aeiouy]+", w)]
    if groups and groups[0][0] == 0 and w[0] == "y" and len(w) > 1 and w[1] in "aeiou":
        groups[0] = (1, groups[0][1])  # 'yeah', 'you': y is a consonant here
    if len(groups) > n_syllables and w.endswith("e") and groups and groups[-1] == (len(w) - 1, len(w)):
        groups = groups[:-1]  # silent e: 'dynamite' -> y / a / i
    if len(groups) > n_syllables and w.endswith(("es", "ed")) and len(w) > 3:
        if groups and groups[-1][0] == len(w) - 2:
            groups = groups[:-1]
    return groups if len(groups) == n_syllables else []


def _tail_syllable_count(units: list[dict]) -> int:
    """Syllables from the last stressed vowel to the end of the word (the CMU rhyming part)."""
    if not units:
        return 0
    for idx in range(len(units) - 1, -1, -1):
        if units[idx].get("stress") in (1, 2):
            return len(units) - idx
    return 1


def _tail_char_span(word: str, tok_start: int, tok_end: int, units: list[dict], rhyme_syls: int = 1) -> tuple[int, int]:
    """
    Returns the character span of the *rhyming syllables only*, e.g. 'mite' in 'dynamite',
    'hend' in 'comprehend'. Falls back to the whole word when the tail covers it or when the
    spelling cannot be aligned with the pronunciation reliably.
    """
    total_syls = len(units or [])
    if total_syls <= 1 or len(word) <= 3:
        return tok_start, tok_end

    tail_syls = min(total_syls, max(int(rhyme_syls or 1), _tail_syllable_count(units)))
    if tail_syls >= total_syls:
        return tok_start, tok_end

    groups = _letter_vowel_groups(word, total_syls)
    if not groups:
        return tok_start, tok_end

    rel_start = groups[total_syls - tail_syls][0]
    # pull in the onset consonant(s) of that syllable ('m' in 'mite', 'sh' in 'ation')
    if rel_start >= 2 and word[rel_start - 2:rel_start].lower() in _ONSET_DIGRAPHS:
        rel_start -= 2
    elif rel_start >= 1 and word[rel_start - 1].lower() not in "aeiouy":
        rel_start -= 1

    if rel_start <= 0 or rel_start >= (tok_end - tok_start):
        return tok_start, tok_end
    return tok_start + rel_start, tok_end


_VOWEL_BUCKETS = {
    "AA": "AH_AA", "AH": "AH_AA",
    "AE": "AE", "EH": "EH",
    "IH": "IH_IY", "IY": "IH_IY",
    "AO": "AO_OW", "OW": "AO_OW",
    "UH": "UH_UW", "UW": "UH_UW",
    "ER": "ER",
    "AY": "AY", "AW": "AW", "OY": "OY",
}

_CODA_BUCKETS = {
    "": "OPEN",
    "N": "N_FLOW", "NG": "N_FLOW",
    "T": "STOP_T_D", "D": "STOP_T_D",
    "K": "K_FLOW", "KS": "K_FLOW", "KT": "K_FLOW",
    "S": "S_FLOW", "Z": "S_FLOW",
    "L": "L_FLOW",
    "R": "R_FLOW", "RD": "R_FLOW",
    "M": "M_FLOW",
    "P": "P_FLOW", "B": "P_FLOW",
}


def _bucket_syllable(unit: dict) -> tuple[str, str]:
    vowel = unit.get("vowel", "")
    coda = "".join(unit.get("coda") or [])
    vb = _VOWEL_BUCKETS.get(vowel, vowel)
    coda_core = re.sub(r"[SZTD]+$", "", coda) or coda
    cb = _CODA_BUCKETS.get(coda_core, coda_core)
    return (vb, cb)


def _clean_norm(word: str) -> str:
    clean = re.sub(r"^[^a-zA-Z]+|[^a-zA-Z']+$", "", (word or "").lower())
    return re.sub(r"['’]s$", "", clean)


def _token_rhyme_parts(tok: dict) -> frozenset:
    """
    All acceptable rhyming parts of a token: the user's pronunciation override if set, otherwise
    every CMU pronunciation (BM-tagged words skip CMU and use the BM transcription instead).
    """
    if tok.get("pron_override"):
        part = _rhyming_part(tok.get("phones") or [])
        return frozenset([part]) if part else frozenset()
    if tok.get("lang") == "BM":
        return frozenset()
    resolved = tok.get("rhyme_parts")
    if resolved:
        return frozenset(resolved)
    return frozenset(_raw_cmu_parts(tok))


def _raw_cmu_parts(tok: dict) -> tuple:
    """Every CMU rhyming part of a token, primary pronunciation first, without duplicates."""
    clean = _clean_norm(tok.get("word", ""))
    if not clean or tok.get("pron_override") or tok.get("lang") == "BM":
        return ()
    out = []
    for pr in _all_cmu_pronunciations(clean):
        part = _rhyming_part(pr) if pr else ""
        if part and part not in out:
            out.append(part)
    return tuple(out)


def _resolve_homographs(tokens: list[dict], window: int):
    """
    A word with several pronunciations ('read', 'live') must commit to ONE rhyme family, otherwise
    it would bridge two unrelated families into one colour group. Pick the pronunciation shared with
    the most neighbours in the same section/window; ties keep the dictionary's primary pronunciation.
    """
    all_parts = [_raw_cmu_parts(t) for t in tokens]
    for i, tok in enumerate(tokens):
        tok["rhyme_parts"] = None
        parts = all_parts[i]
        if len(parts) < 2 or tok["is_stopword"]:
            continue
        best_part, best_count = parts[0], -1
        for part in parts:
            count = 0
            for j, other in enumerate(tokens):
                if j == i or other["section"] != tok["section"] or other["norm"] == tok["norm"]:
                    continue
                if abs(other["line"] - tok["line"]) > window:
                    continue
                if other["is_stopword"] and not other["is_line_end"]:
                    continue
                if part in all_parts[j]:
                    count += 1
            if count > best_count:
                best_part, best_count = part, count
        tok["rhyme_parts"] = (best_part,)


def _token_rhyme_key(tok: dict) -> tuple | None:
    """
    Single canonical rhyme key for perfect-rhyme bucketing:
    1. ('CMU', rhyming_part) when a CMU / override pronunciation exists.
    2. ('TAIL', head_bucket, post_buckets) for Malay / unknown G2P words.
    """
    parts = _token_rhyme_parts(tok)
    if parts:
        return ("CMU", next(iter(parts)))

    tail = _rhyme_tail_units(tok.get("units") or [])
    if not tail or not tail[0].get("vowel"):
        return None
    head_bucket = _bucket_syllable(tail[0])
    post_buckets = tuple(_bucket_syllable(u) for u in tail[1:])
    return ("TAIL", head_bucket, post_buckets)


NEAR_RHYME_MIN_CONF = 66.0


def _near_rhyme_strength(tok_a: dict, tok_b: dict) -> tuple[float, str]:
    """Score-based slant / assonance detector for ungrouped line-end words."""
    if tok_a["norm"] == tok_b["norm"] or not tok_a["units"] or not tok_b["units"]:
        return 0.0, "None"
    ka, kb = _token_rhyme_key(tok_a), _token_rhyme_key(tok_b)
    if ka is not None and ka == kb:
        return 0.0, "None"
    conf, cat, _ = score_rhyme_pair(tok_a["units"], tok_b["units"])
    if cat in ("Slant Rhyme", "Assonance") and conf >= NEAR_RHYME_MIN_CONF:
        return conf, cat
    return 0.0, "None"

_SIMILE_SETUP_PATTERNS = [
    re.compile(r"\b(?:like a|like an|like the|got more .+ than|call me .+ how i)\b", re.IGNORECASE),
    re.compile(r"\b(?:macam|ibarat|bagaikan|umpama|serupa)\b", re.IGNORECASE),
]

_DE_BY_TRIGGER = {item["trigger"]: item for item in CONTEXTUAL_DOUBLE_ENTENDRES}


def _scan_wordplay_and_entendres(lines_info: list[dict], tokens: list[dict], window: int = 2) -> int:
    """
    Populates tok['wordplay'] (string) and tok['wordplay_confidence'] (float) across tokens
    using existing Double Entendre / Slang / Multiword tables + dynamic cross-bar homophone flips.
    """
    if not tokens:
        return 0

    line_tokens_map: dict[int, list[dict]] = defaultdict(list)
    for tok in tokens:
        line_tokens_map[tok["line"]].append(tok)

    # Precompute context word sets per line (within +/- window lines in same section)
    line_ctx_words: dict[int, set[str]] = {}
    for linfo in lines_info:
        l_idx = linfo["line"]
        if linfo["is_header"] or not linfo["token_indices"]:
            continue
        sec = tokens[linfo["token_indices"][0]]["section"]
        ctx = set()
        for adj in range(max(0, l_idx - window), min(len(lines_info), l_idx + window + 1)):
            for t in line_tokens_map.get(adj, []):
                if t["section"] == sec:
                    ctx.add(t["norm"])
        line_ctx_words[l_idx] = ctx

    total_hits = 0

    # 1. Multi-word idioms & simile patterns per line
    for linfo in lines_info:
        if linfo["is_header"] or not linfo["token_indices"]:
            continue
        l_idx = linfo["line"]
        raw_line = linfo["text"]
        l_toks = line_tokens_map[l_idx]

        for pat, label, note, conf in MULTIWORD_WORDPLAY_PATTERNS:
            m = pat.search(raw_line)
            if m:
                # Attach to first token overlapping the matched phrase
                for t in l_toks:
                    if not t["wordplay"]:
                        t["wordplay"] = f"⚡ {label}\n{note}"
                        t["wordplay_confidence"] = conf
                        total_hits += 1
                        break

        if any(p.search(raw_line) for p in _SIMILE_SETUP_PATTERNS):
            for t in l_toks:
                if t["norm"] in {"like", "macam", "ibarat", "bagaikan", "umpama"} and not t["wordplay"]:
                    t["wordplay"] = "⚡ Simile / Punchline Setup (82%)\nComparison setup — land a double-meaning noun at the bar end."
                    t["wordplay_confidence"] = 82.0
                    total_hits += 1
                    break

    # 2. Token-level Custom Slang, Contextual Double Entendres & Contextual Slang
    for tok in tokens:
        if tok["wordplay"]:
            continue
        w = tok["norm"]
        ctx = line_ctx_words.get(tok["line"], set()) - {w}

        if w in LEXICON.custom_slang:
            entry = LEXICON.custom_slang[w]
            tok["wordplay"] = f"⚡ {entry.get('tag', 'CUSTOM SLANG')} (95%)\n{entry.get('meaning', '')}"
            tok["wordplay_confidence"] = 95.0
            total_hits += 1
            continue

        if w in _DE_BY_TRIGGER:
            de = _DE_BY_TRIGGER[w]
            matched = ctx & de["foils"]
            if matched:
                tok["wordplay"] = f"⚡ {de['label']}\n{de['note']} [foils: {', '.join(sorted(matched)[:3])}]"
                tok["wordplay_confidence"] = de["conf"]
                total_hits += 1
                continue

        if w in CONTEXTUAL_SLANG_LEXICON:
            cat_s, meaning_s, conf_s, req_foils = CONTEXTUAL_SLANG_LEXICON[w]
            if req_foils is None or (ctx & req_foils):
                tok["wordplay"] = f"⚡ {cat_s} ({int(conf_s)}%)\n{meaning_s}"
                tok["wordplay_confidence"] = conf_s
                total_hits += 1
                continue

    # 3. Cross-Bar Homophone Flip Detection (different words, identical pronunciation)
    tok_pkeys = [_strip_stress(t["phones"]) if t["phones"] else () for t in tokens]
    for i, ti in enumerate(tokens):
        if ti["wordplay"] or ti["is_stopword"] or len(ti["norm"]) < 3 or not tok_pkeys[i]:
            continue
        for j in range(i + 1, len(tokens)):
            tj = tokens[j]
            if tj["section"] != ti["section"] or tj["line"] - ti["line"] > window:
                break
            if tj["is_stopword"] or tj["norm"] == ti["norm"]:
                continue
            if tok_pkeys[i] == tok_pkeys[j]:
                note_i = f"⚡ Homophone Flip (92%)\nSounds identical to '{tj['word']}' (L{tj['line'] + 1:02d}) with different spelling/meaning."
                note_j = f"⚡ Homophone Flip (92%)\nSounds identical to '{ti['word']}' (L{ti['line'] + 1:02d}) with different spelling/meaning."
                ti["wordplay"] = note_i
                ti["wordplay_confidence"] = 92.0
                total_hits += 1
                if not tj["wordplay"]:
                    tj["wordplay"] = note_j
                    tj["wordplay_confidence"] = 92.0
                    total_hits += 1
                break

    return total_hits
    
DEFAULT_PALETTE_SIZE = 8


def analyze_lyrics(
    text: str,
    rhyme_window: int = 6,
    manual_rhyme_pairs: list[tuple[int, int]] | None = None,
    granularity: str = "syllable",
    palette_size: int = DEFAULT_PALETTE_SIZE,
) -> dict:
    """
    O(N) section-aware rhyme scheme analyzer using canonical rhyme-key bucketing
    and line-distance window splitting.
    """
    lines_info, tokens = _tokenize_lyrics(text)

    section_id = 0
    line_to_section = {}
    for linfo in lines_info:
        txt = linfo["text"].strip()
        if not txt or linfo["is_header"]:
            if line_to_section:
                section_id += 1
        line_to_section[linfo["line"]] = section_id

    for tok in tokens:
        tok["section"] = line_to_section.get(tok["line"], 0)
        r_s, r_e = _tail_char_span(tok["word"], tok["start"], tok["end"], tok["units"])
        tok["rhyme_start"] = r_s
        tok["rhyme_end"] = r_e

    n = len(tokens)
    try:
        effective_window = max(1, int(rhyme_window))
    except (TypeError, ValueError):
        effective_window = 6

    _resolve_homographs(tokens, effective_window)

    # Step 1: Group tokens by (section, canonical_rhyme_key)
    buckets = defaultdict(list)
    for tok in tokens:
        if tok["is_stopword"] and not tok["is_line_end"]:
            continue
        r_key = _token_rhyme_key(tok)
        if r_key is not None:
            buckets[(tok["section"], r_key)].append(tok)

    # Step 2: Split each bucket where consecutive line distance exceeds effective_window
    raw_clusters = []
    for (sec, r_key), group_toks in buckets.items():
        if len(group_toks) < 2:
            continue

        cur_cluster = [group_toks[0]]
        for tok in group_toks[1:]:
            if tok["line"] - cur_cluster[-1]["line"] <= effective_window:
                cur_cluster.append(tok)
            else:
                raw_clusters.append((r_key, cur_cluster))
                cur_cluster = [tok]
        raw_clusters.append((r_key, cur_cluster))

    # Step 3: Keep clusters with >= 2 distinct words & assign scheme group IDs in reading order
    valid_clusters = []
    for r_key, cluster in raw_clusters:
        distinct_norms = {re.sub(r"['’]s$", "", t["norm"]) for t in cluster}
        distinct_norms.discard("")
        if len(distinct_norms) >= 2:
            valid_clusters.append((cluster[0]["idx"], r_key, cluster))

    valid_clusters.sort(key=lambda item: item[0])

    next_group_id = 0
    for _, r_key, cluster in valid_clusters:
        gid = next_group_id
        next_group_id += 1
        lines_in_cluster = {t["line"] for t in cluster}
        is_end_rhyme = sum(1 for t in cluster if t["is_line_end"]) >= 2

        for tok in cluster:
            partner = next(
                (other for other in cluster if other["norm"] != tok["norm"]),
                cluster[0],
            )
            pos_tag = (
                "Internal"
                if len(lines_in_cluster) == 1
                else ("End Rhyme" if is_end_rhyme and tok["is_line_end"] else "Cross-Bar")
            )
            conf = 95.0 if (r_key[0] == "CMU" and tok["is_line_end"]) else (88.0 if r_key[0] == "CMU" else 82.0)

            tok["rhyme_group"] = gid
            tok["rhyme_confidence"] = conf
            tok["rhyme_category"] = f"Rhyme ({pos_tag})"
            tok["rhyme_explanation"] = f"Rhymes with '{partner['word']}' [{pos_tag}] ({conf:.0f}%)"

    # Step 3a: Near rhymes (slant / assonance) & repeated end-words between ungrouped line-end tokens
    end_tokens = [t for t in tokens if t["is_line_end"] and not t["is_stopword"]]
    for i, ti in enumerate(end_tokens):
        for j in range(i + 1, len(end_tokens)):
            tj = end_tokens[j]
            if tj["section"] != ti["section"] or tj["line"] - ti["line"] > effective_window:
                break
            if tj["line"] == ti["line"]:
                continue
            if ti["norm"] == tj["norm"]:
                ti["is_repeat"] = tj["is_repeat"] = True
                continue
            if ti["rhyme_group"] is not None and tj["rhyme_group"] is not None:
                continue
            conf, cat = _near_rhyme_strength(ti, tj)
            if conf <= 0.0:
                continue
            for tok_ref, partner_ref in ((ti, tj), (tj, ti)):
                if tok_ref["rhyme_group"] is not None:
                    continue
                cur = tok_ref["near_rhyme"]
                if cur is None or conf > cur["confidence"]:
                    tok_ref["near_rhyme"] = {
                        "partner": partner_ref["idx"],
                        "partner_word": partner_ref["word"],
                        "category": cat,
                        "confidence": conf,
                    }

    # Step 3b: Apply user-forced Alt+Click rhyme pairs
    if manual_rhyme_pairs:
        manual_groups = []
        for a_idx, b_idx in manual_rhyme_pairs:
            if not (0 <= a_idx < n and 0 <= b_idx < n) or a_idx == b_idx:
                continue
            placed = False
            for grp in manual_groups:
                if a_idx in grp or b_idx in grp:
                    grp.add(a_idx)
                    grp.add(b_idx)
                    placed = True
                    break
            if not placed:
                manual_groups.append({a_idx, b_idx})

        for grp in manual_groups:
            existing_ids = [tokens[i]["rhyme_group"] for i in grp if tokens[i]["rhyme_group"] is not None]
            gid = existing_ids[0] if existing_ids else next_group_id
            if not existing_ids:
                next_group_id += 1
            for i in grp:
                tokens[i]["rhyme_group"] = gid
                tokens[i]["rhyme_start"] = tokens[i]["start"]
                tokens[i]["rhyme_end"] = tokens[i]["end"]
                tokens[i]["rhyme_confidence"] = max(tokens[i]["rhyme_confidence"], 100.0)
                tokens[i]["rhyme_category"] = "Manual Rhyme (Alt+Click)"
                tokens[i]["rhyme_explanation"] = "Forced rhyme link via Alt+Click (saved with draft)"

    # Recompute exact tail spans for automatic rhymes
    for tok in tokens:
        if tok["rhyme_group"] is not None and tok.get("rhyme_category") != "Manual Rhyme (Alt+Click)":
            r_s, r_e = _tail_char_span(
                tok["word"],
                tok["start"],
                tok["end"],
                tok["units"],
            )
            tok["rhyme_start"] = r_s
            tok["rhyme_end"] = r_e

    # Compute single canonical palette color index & syllable-tail span per token
    n_colors = max(1, int(palette_size or DEFAULT_PALETTE_SIZE))
    for tok in tokens:
        gid = tok["rhyme_group"]
        tok["color_idx"] = (gid % n_colors) if gid is not None else None
        if granularity == "word" or gid is None:
            tok["rhyme_start"], tok["rhyme_end"] = tok["start"], tok["end"]
        tok["is_syllable_rhyme"] = tok["rhyme_start"] > tok["start"]

    total_rhymes = sum(1 for t in tokens if t["rhyme_group"] is not None)
    total_near = sum(1 for t in tokens if t["near_rhyme"] is not None and t["rhyme_group"] is None)
    total_wordplay = _scan_wordplay_and_entendres(lines_info, tokens, window=min(3, effective_window))

    return {
        "total_near": total_near,
        "lines": lines_info,
        "tokens": tokens,
        "total_rhymes": total_rhymes,
        "total_multies": 0,
        "total_wordplay": total_wordplay,
    }

# =====================================================================
# RHYME ENGINE SIDEBAR LOOKUP (EN+SLANG / BM+PASAR / PACKS / SLANT)
# =====================================================================
def find_rhymes_for_word(word: str) -> dict:
    clean = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", word).strip()
    if not clean:
        return {
            "word": "",
            "syllables": 0,
            "lang": "EN",
            "perfect_en": [],
            "perfect_bm": [],
            "perfect_custom": [],
            "slant": [],
            "wordplay": "",
        }

    target_prof = LEXICON.get_phonetic_profile(clean)
    t_units = target_prof["units"]

    perfect_en = []
    perfect_bm = []
    perfect_custom = []
    slant = []

# Candidate pool from offline EN + pronouncing/cmudict + BM + Custom Slang + Language Packs
    en_candidates = set(EN_ARPABET_OVERRIDES.keys())
    if HAS_PRONOUNCING:
        try:
            en_candidates.update(pronouncing.rhymes(clean.lower())[:100])
        except Exception:
            pass

    for cand in sorted(en_candidates):
        if cand == target_prof["norm"]:
            continue
        c_prof = LEXICON.get_phonetic_profile(cand)
        conf, cat, syls = score_rhyme_pair(t_units, c_prof["units"])
        badge = " 🔥" if syls >= 2 else ""
        if conf >= 88.0:
            perfect_en.append(f"{cand}{badge}")
        elif conf >= 68.0:
            slant.append(f"{cand} [{int(conf)}%]")

    for cand in sorted(BM_LEXICON_HINTS):
        if cand == target_prof["norm"]:
            continue
        c_prof = LEXICON.get_phonetic_profile(cand)
        conf, cat, syls = score_rhyme_pair(t_units, c_prof["units"])
        badge = " 🔥" if syls >= 2 else ""
        if conf >= 85.0:
            perfect_bm.append(f"{cand}{badge}")
        elif conf >= 68.0:
            slant.append(f"{cand} [BM {int(conf)}%]")

    custom_pool = set(LEXICON.custom_slang.keys()).union(LEXICON.active_pack_words).union(CONTEXTUAL_SLANG_LEXICON.keys())
    for cand in sorted(custom_pool):
        if cand == target_prof["norm"]:
            continue
        c_prof = LEXICON.get_phonetic_profile(cand)
        conf, cat, syls = score_rhyme_pair(t_units, c_prof["units"])
        if conf >= 72.0:
            tag = " (slang)" if (cand in LEXICON.custom_slang or cand in CONTEXTUAL_SLANG_LEXICON) else ""
            perfect_custom.append(f"{cand}{tag} [{int(conf)}%]")

    # Wordplay & Double Entendre Lab notes
    w_low = target_prof["norm"]
    wp_notes = [f"Phonemes: {' '.join(target_prof['phones'])}"]
    if w_low in LEXICON.custom_slang:
        entry = LEXICON.custom_slang[w_low]
        wp_notes.append(f"• [{entry.get('tag', 'CUSTOM SLANG')}] {entry.get('meaning', '')}")
    if w_low in HOMOPHONE_PAIRS:
        wp_notes.append(f"• {HOMOPHONE_PAIRS[w_low][1]}")
    for de in CONTEXTUAL_DOUBLE_ENTENDRES:
        if de["trigger"] == w_low:
            wp_notes.append(f"• {de['note']}")
    if w_low in CONTEXTUAL_SLANG_LEXICON:
        cat_s, m_s, _, _ = CONTEXTUAL_SLANG_LEXICON[w_low]
        wp_notes.append(f"• [{cat_s}] {m_s}")

    return {
        "word": clean,
        "syllables": target_prof["syllables"],
        "lang": target_prof["lang"],
        "perfect_en": perfect_en[:60],
        "perfect_bm": perfect_bm[:60],
        "perfect_custom": perfect_custom[:60],
        "slant": slant[:60],
        "wordplay": "\n".join(wp_notes),
    }


# =====================================================================
# PEN METER SCORECARD (rate_lyrics_comprehensive)
# =====================================================================
def rate_lyrics_comprehensive(text: str, rhyme_window: int = 4) -> dict:
    res = analyze_lyrics(text, rhyme_window=rhyme_window)
    lines = res["lines"]
    tokens = res["tokens"]

    active_lines = [l for l in lines if not l["is_header"] and l["syllables"] > 0]
    headers = [l for l in lines if l["is_header"]]
    bars = len(active_lines)
    word_count = len(tokens)

    if bars == 0 or word_count == 0:
        return {
            "overall": 0,
            "tier": "EMPTY SHEET",
            "color": "#A1A1AA",
            "metrics": {"bars": 0, "words": 0, "multie_chains": 0, "wordplay_hits": 0},
            "breakdown": {"multies": 0, "wordplay": 0, "flow": 0, "structure": 0, "vocab": 0},
            "highlights": [],
            "tips": ["Write at least 4 bars to evaluate multies, cadence pocket, and wordplay."],
        }

    multie_ratio = res["total_multies"] / float(max(1, word_count))
    rhyme_ratio = res["total_rhymes"] / float(max(1, word_count))
    wp_ratio = res["total_wordplay"] / float(max(1, bars))

    multies_score = min(100, int(round((multie_ratio * 240.0) + (rhyme_ratio * 65.0))))
    wordplay_score = min(100, int(round(wp_ratio * 135.0)))

    # Cadence consistency across adjacent bars
    syl_seq = [l["syllables"] for l in active_lines]
    if len(syl_seq) >= 2:
        diffs = [abs(syl_seq[i] - syl_seq[i - 1]) for i in range(1, len(syl_seq))]
        avg_diff = sum(diffs) / float(len(diffs))
        flow_score = max(25, min(100, int(round(100.0 - max(0.0, avg_diff - 1.5) * 11.0))))
    else:
        flow_score = 60

    structure_score = min(100, 45 + len(headers) * 18 + min(25, bars * 2))
    unique_norms = {t["norm"] for t in tokens if not t["is_stopword"]}
    langs_used = {t["lang"] for t in tokens}
    vocab_score = min(100, int(round((len(unique_norms) / float(max(1, word_count))) * 125.0)) + (8 if len(langs_used) > 1 else 0))

    overall = int(round(
        0.30 * multies_score
        + 0.25 * wordplay_score
        + 0.20 * flow_score
        + 0.15 * structure_score
        + 0.10 * vocab_score
    ))

    if overall >= 85:
        tier, color = "S // ELITE PENMANSHIP", "#C084FC"
    elif overall >= 72:
        tier, color = "A // SHARP LYRICIST", "#A855F7"
    elif overall >= 55:
        tier, color = "B // SOLID CADENCE", "#38BDF8"
    else:
        tier, color = "C // ROUGH DRAFT", "#FBBF24"

    highlights = []
    seen_lines = set()
    for t in tokens:
        if t["line"] in seen_lines:
            continue
        if t["multie_count"] >= 2 and t["rhyme_confidence"] >= 75.0:
            highlights.append({
                "badge": f"🔥 {t['multie_count']}x MULTIE ({int(t['rhyme_confidence'])}%)",
                "detail": f"L{t['line'] + 1:02d}: {t['rhyme_explanation']}",
                "line": t["line"],
            })
            seen_lines.add(t["line"])
        elif t["wordplay"] and t["wordplay_confidence"] >= 80.0:
            first_line_wp = t["wordplay"].splitlines()[0].replace("⚡ ", "")
            highlights.append({
                "badge": f"⚡ {first_line_wp}",
                "detail": f"L{t['line'] + 1:02d}: '{t['word']}' — {lines[t['line']]['text'].strip()}",
                "line": t["line"],
            })
            seen_lines.add(t["line"])

    tips = []
    if multies_score < 65:
        tips.append("Stack 2-to-3 syllable internal vowel chains across bar endings to raise Multie density.")
    if wordplay_score < 60:
        tips.append("Pair homophones (e.g. soul/sole, write/right) or double-meaning anchors with contextual setup words.")
    if flow_score < 65:
        tips.append("Tighten syllable variance between consecutive bars so your cadence locks cleanly into the pocket.")
    if not tips:
        tips.append("Strong phonetic density, clean cadence pocket, and contextual double entendres across your bars.")

    return {
        "overall": overall,
        "tier": tier,
        "color": color,
        "metrics": {
            "bars": bars,
            "words": word_count,
            "multie_chains": res["total_multies"],
            "wordplay_hits": res["total_wordplay"],
        },
        "breakdown": {
            "multies": multies_score,
            "wordplay": wordplay_score,
            "flow": flow_score,
            "structure": structure_score,
            "vocab": vocab_score,
        },
        "highlights": highlights[:12],
        "tips": tips,
    }


# =====================================================================
# NETWORK HELPERS FOR LexiconManagerDialog (ONLINE PACK DOWNLOADER)
# =====================================================================
def fetch_url_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "NOCTURNE-Lyricist-DAW/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse_wordlist_content(raw_text: str, is_json: bool = False) -> list[str]:
    words = []
    if is_json:
        try:
            data = json.loads(raw_text)
            if isinstance(data, list):
                for item in data:
                    words.extend(re.findall(r"[A-Za-z'-]{2,}", str(item)))
            elif isinstance(data, dict):
                for k, v in data.items():
                    words.extend(re.findall(r"[A-Za-z'-]{2,}", str(k)))
                    if isinstance(v, list):
                        for item in v:
                            words.extend(re.findall(r"[A-Za-z'-]{2,}", str(item)))
        except Exception:
            words = re.findall(r"[A-Za-z'-]{2,}", raw_text)
    else:
        for line in raw_text.splitlines():
            parts = line.strip().split()
            if parts:
                w = re.sub(r"[^A-Za-z'-]", "", parts[0])
                if len(w) >= 2:
                    words.append(w.lower())
    return sorted(list(set(words)))


def search_github_wordlists(query: str) -> list[dict]:
    q = urllib.parse.quote(f"{query} wordlist OR dictionary OR slang")
    url = f"https://api.github.com/search/repositories?q={q}&sort=stars&per_page=12"
    raw = fetch_url_text(url, timeout=15)
    data = json.loads(raw)
    out = []
    for item in data.get("items", []):
        out.append({
            "full_name": item.get("full_name", ""),
            "description": item.get("description") or "No description",
            "stars": item.get("stargazers_count", 0),
            "branch": item.get("default_branch", "main"),
        })
    return out


def fetch_repo_wordlist_files(repo_full_name: str, branch: str = "main") -> list[dict]:
    url = f"https://api.github.com/repos/{repo_full_name}/git/trees/{branch}?recursive=1"
    raw = fetch_url_text(url, timeout=15)
    data = json.loads(raw)
    files = []
    for node in data.get("tree", []):
        path = node.get("path", "")
        if node.get("type") == "blob" and path.lower().endswith((".txt", ".json")):
            size_kb = max(1, round(node.get("size", 1024) / 1024.0, 1))
            files.append({
                "path": path,
                "size_kb": size_kb,
                "is_json": path.lower().endswith(".json"),
                "raw_url": f"https://raw.githubusercontent.com/{repo_full_name}/{branch}/{path}",
            })
    return files[:40]