# lyric_engine.py
import os
import re
import json
import math
import urllib.request
import urllib.parse
import base64
import hashlib
import hmac
import secrets
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

_ACTIVE_PROFILE_KEYS: dict[str, bytes] = {}

def set_active_profile_key(profile_dir: str, raw_key: bytes):
    if profile_dir and raw_key:
        _ACTIVE_PROFILE_KEYS[os.path.abspath(profile_dir)] = raw_key


def derive_profile_crypto_key(secret_material: str, salt_hex: str) -> bytes:
    salt_bytes = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac(
        "sha256",
        secret_material.encode("utf-8"),
        salt_bytes,
        200_000,
        dklen=64,
    )


def _derive_profile_key_from_disk(profile_dir: str) -> bytes:
    abs_dir = os.path.abspath(profile_dir)
    if abs_dir in _ACTIVE_PROFILE_KEYS:
        return _ACTIVE_PROFILE_KEYS[abs_dir]

    meta_path = os.path.join(profile_dir, "profile_meta.json")
    meta = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {}

    salt_hex = meta.get("crypto_salt")
    if not salt_hex:
        salt_hex = secrets.token_hex(16)
        meta["crypto_salt"] = salt_hex
        try:
            os.makedirs(profile_dir, exist_ok=True)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception:
            pass

    fallback_secret = f"nocturne_open_vault_{os.path.basename(abs_dir)}_{salt_hex}"
    key = derive_profile_crypto_key(fallback_secret, salt_hex)
    _ACTIVE_PROFILE_KEYS[abs_dir] = key
    return key


def _xor_ctr_stream(data: bytes, enc_key: bytes, nonce: bytes) -> bytes:
    out = bytearray(len(data))
    counter = 0
    offset = 0
    while offset < len(data):
        block = hmac.new(enc_key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        chunk = data[offset : offset + 32]
        for i, b in enumerate(chunk):
            out[offset + i] = b ^ block[i]
        offset += 32
        counter += 1
    return bytes(out)


def encrypt_profile_payload(payload_obj, profile_dir: str, override_key: bytes | None = None) -> dict:
    raw_key = override_key or _derive_profile_key_from_disk(profile_dir)
    enc_key, mac_key = raw_key[:32], raw_key[32:]
    plaintext = json.dumps(payload_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    nonce = secrets.token_bytes(16)
    ciphertext = _xor_ctr_stream(plaintext, enc_key, nonce)
    tag = hmac.new(mac_key, b"NOCTURNE_ENC_V1" + nonce + ciphertext, hashlib.sha256).digest()
    return {
        "__nocturne_enc__": 1,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "tag": base64.b64encode(tag).decode("ascii"),
        "data": base64.b64encode(ciphertext).decode("ascii"),
    }


def decrypt_profile_payload(raw_obj, profile_dir: str, override_key: bytes | None = None):
    if not isinstance(raw_obj, dict) or raw_obj.get("__nocturne_enc__") != 1:
        return raw_obj
    raw_key = override_key or _derive_profile_key_from_disk(profile_dir)
    enc_key, mac_key = raw_key[:32], raw_key[32:]
    nonce = base64.b64decode(raw_obj["nonce"])
    tag = base64.b64decode(raw_obj["tag"])
    ciphertext = base64.b64decode(raw_obj["data"])
    expected_tag = hmac.new(mac_key, b"NOCTURNE_ENC_V1" + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Invalid profile encryption key or tampered file.")
    plaintext = _xor_ctr_stream(ciphertext, enc_key, nonce)
    return json.loads(plaintext.decode("utf-8"))


def write_encrypted_profile_json(filepath: str, payload_obj, profile_dir: str, override_key: bytes | None = None):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    envelope = encrypt_profile_payload(payload_obj, profile_dir, override_key=override_key)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2)


def read_encrypted_profile_json(filepath: str, profile_dir: str, default=None, override_key: bytes | None = None):
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return decrypt_profile_payload(raw, profile_dir, override_key=override_key)
    except Exception:
        return default
    
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


HAS_CMU_SOURCE = HAS_PRONOUNCING or HAS_CMUDICT


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
        "category": "English",
        "name": "English - Frequency Words",
        "desc": "High frequency words - over 200,000 ",
        "url": "https://raw.githubusercontent.com/zydou/high-frequency-words/refs/heads/master/200k.txt",
    },
    {
        "category": "Malay (165k words)",
        "name": "Bahasa Malaysia",
        "desc": "Over 165,400 words - library from Leipzig Corpora",
        "url": "https://raw.githubusercontent.com/muhdrasydan99/nocturne-words-library/refs/heads/main/lang/ms_165k.txt",
    },
    {
     "category": "English",
        "name": "English",
        "desc": "Over 137,485 words - library from Leipzig Corpora ",
        "url": "https://raw.githubusercontent.com/muhdrasydan99/nocturne-words-library/refs/heads/main/lang/en_137k.txt",
    },
]


def ensure_offline_corpora():
    """Ensures offline phonetic & lexical tables are initialized without network dependency."""
    _ = len(BUILTIN_EN_WORDS) + len(BUILTIN_BM_WORDS)


# =====================================================================
# PHONETIC FEATURE TABLES (ARTICULATORY VOWEL & CONSONANT SPACE)
# =====================================================================
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
    "aku", "kau", "baik", "naik", "laut", "daun", "pulau", "makan", "dengan",
    "rindu", "sayang", "syurga", "khabar", "emak", "nyanyi", "berlari",
    "padu", "tapau", "lepak", "kantoi", "bantai", "sembang", "kencang", "kaku",
    "ludah", "lawan", "susun", "kata", "tajam", "senang", "hati", "jalan", "gelap",
    "lampu", "terang", "tinggi", "gua", "lu", "bro", "weh", "lah", "mantap",
    "kacip", "barai", "santai", "gerak", "pacak", "tumbang", "menang", "tenang",
    "hilang", "terbang", "datang", "pulang", "bintang", "gelombang", "malam",
    "dalam", "salam", "diam", "hitam", "azam", "faham", "paham",
    "jiwa", "dunia", "raja", "kota", "mata", "nyata", "cinta", "cerita",
    "api", "mati", "pasti", "nanti", "hari", "lari", "cari", "diri", "berdiri",
    "mimpi", "sepi", "tepi", "kopi", "topi", "syok", "gempak",
    "merecik", "hawau", "sakai", "poyo", "bajet", "koyak", "rabak", "cilok",
    "rembat", "hensem", "cun", "ngam", "steady", "rilek", "hal", "asal", "pasal",
    "akal", "kekal", "kebal", "tebal", "gagal", "mahal", "kapal", "sampai",
    "ramai", "damai", "pantai", "rantai", "selesai", "perangai", "bagus", "hangus",
    "terus", "lurus", "kurus", "urus", "tulus", "mulus", "modus", "fokus",
}


def detect_word_language(word_low: str, custom_bm_words: set[str]) -> str:
    if word_low in BM_LEXICON_HINTS:
        return "BM"
    if word_low in EN_ARPABET_OVERRIDES:
        return "EN"
    if _lookup_cmu_phones(word_low):
        return "EN"
    if word_low in custom_bm_words:
        return "BM"
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

    tokens = []
    i = 0
    while i < len(w):
        digraph = w[i:i + 2]
        if digraph in ("ng", "ny", "sy", "kh", "gh") or (
                digraph in ("ai", "au", "oi") and i + 2 == len(w)):
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

    vowel_indices = [idx for idx, tk in enumerate(tokens) if tk in vowel_map]
    if not vowel_indices:
        return ["AH1"]

    stressed_v_pos = vowel_indices[-2] if len(vowel_indices) >= 2 else vowel_indices[-1]
    if len(vowel_indices) >= 2 and tokens[stressed_v_pos] == "e":
        stressed_v_pos = vowel_indices[-1]

    phones = []
    for idx, tk in enumerate(tokens):
        if tk in vowel_map:
            base_v = vowel_map[tk]
            if idx == vowel_indices[-1] and idx < len(tokens) - 1:
                if tk == "i":
                    base_v = "IH"
                elif tk == "u":
                    base_v = "UH"
            stress = "1" if idx == stressed_v_pos else "0"
            phones.append(f"{base_v}{stress}")
        elif tk == "ny":
            phones.extend(["N", "Y"])
        elif tk in cons_map:
            phones.append(cons_map[tk])

    return phones


def fallback_en_g2p(word_low: str) -> list[str]:
    """Rule-based English Grapheme-to-Phoneme ARPAbet transcriber when CMUdict lacks a word."""
    w = re.sub(r"[^a-z']", "", word_low)
    if not w:
        return []

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
    heavy_idx = -1
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
            if i + 1 < len(stem) and stem[i + 1] == "r":
                if ch in ("e", "i", "u"):
                    phones.append("ER")
                elif ch == "a":
                    phones.append("AA")
                else:
                    phones.append("AO")
                i += 1
            elif ch == "y" and i == len(stem) - 1 and any(c in "aeiou" for c in stem[:i]):
                phones.append("IY")
            else:
                is_last_vowel = not any(c in "aeiouy" for c in stem[i + 1:])
                if is_last_vowel and (silent_e or i == len(stem) - 1):
                    if silent_e:
                        heavy_idx = len(phones)
                    phones.append(long_vowel_map[ch])
                else:
                    phones.append(short_vowel_map[ch])
            i += 1
        elif stem[i] in single_cons:
            if i + 1 < len(stem) and stem[i + 1] == stem[i]:
                i += 1
            phones.append(single_cons[stem[i]])
            i += 1
        else:
            i += 1

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
        self._phoneme_cache = {}

        pron_path = os.path.join(self.profile_dir, "pronunciations.json")
        raw_pron = read_encrypted_profile_json(pron_path, self.profile_dir, default={})
        for w, ent in (raw_pron or {}).items():
            if isinstance(ent, dict) and ent.get("phones"):
                self.pron_overrides[w.strip().lower()] = {
                    "spec": str(ent.get("spec", "")),
                    "phones": [str(x) for x in ent["phones"]],
                }

        slang_path = os.path.join(self.profile_dir, "custom_slang.json")
        self.custom_slang = read_encrypted_profile_json(slang_path, self.profile_dir, default={}) or {}

        packs_path = os.path.join(self.profile_dir, "language_packs.json")
        self.language_packs = read_encrypted_profile_json(packs_path, self.profile_dir, default={}) or {}

        self._rebuild_active_pack_set()

    def _save_slang(self):
        if not self.profile_dir:
            return
        write_encrypted_profile_json(
            os.path.join(self.profile_dir, "custom_slang.json"),
            self.custom_slang,
            self.profile_dir,
        )

    def _save_pron(self):
        if not self.profile_dir:
            return
        write_encrypted_profile_json(
            os.path.join(self.profile_dir, "pronunciations.json"),
            self.pron_overrides,
            self.profile_dir,
        )

    @staticmethod
    def _normalise_arpabet(tokens: list[str]) -> list[str] | None:
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
        if not any_stress:
            last_v = max((i for i, p in enumerate(out) if re.sub(r"\d", "", p) in VOWEL_FEATURES), default=None)
            if last_v is None:
                return None
            out = [(p + ("1" if i == last_v else "0")) if re.sub(r"\d", "", p) in VOWEL_FEATURES else p
                   for i, p in enumerate(out)]
        return out

    def set_pronunciation(self, word: str, spec: str) -> list[str]:
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
        write_encrypted_profile_json(
            os.path.join(self.profile_dir, "language_packs.json"),
            self.language_packs,
            self.profile_dir,
        )

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
# CORE ANALYSIS ENGINE (RHYMES & SYLLABLE SEQUENCES)
# =====================================================================
def _is_known_english(w_low: str) -> bool:
    return w_low in EN_ARPABET_OVERRIDES or bool(_all_cmu_pronunciations(w_low))


def _is_ambiguous_word(w_low: str) -> bool:
    hinted = w_low in BM_LEXICON_HINTS or w_low in LEXICON.active_pack_words
    return hinted and w_low not in EN_ARPABET_OVERRIDES and bool(_all_cmu_pronunciations(w_low))


def _line_language_for_ambiguous(matches) -> str:
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
                if force is None and HAS_CMU_SOURCE and _looks_malay(w_low):
                    force = "BM"
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
    if not units:
        return []
    stressed = [i for i, u in enumerate(units) if u["stress"] in (1, 2)]
    start_idx = stressed[-1] if stressed else max(0, len(units) - 1)
    return units[start_idx:]


_ONSET_DIGRAPHS = ("sh", "ch", "th", "ph", "wh", "ck", "qu", "gh")


def _letter_vowel_groups(word: str, n_syllables: int) -> list[tuple[int, int]]:
    w = word.lower()
    groups = [m.span() for m in re.finditer(r"[aeiouy]+", w)]
    if groups and groups[0][0] == 0 and w[0] == "y" and len(w) > 1 and w[1] in "aeiou":
        groups[0] = (1, groups[0][1])
    if len(groups) > n_syllables and w.endswith("e") and groups and groups[-1] == (len(w) - 1, len(w)):
        groups = groups[:-1]
    if len(groups) > n_syllables and w.endswith(("es", "ed")) and len(w) > 3:
        if groups and groups[-1][0] == len(w) - 2:
            groups = groups[:-1]
    return groups if len(groups) == n_syllables else []


def _tail_syllable_count(units: list[dict]) -> int:
    if not units:
        return 0
    for idx in range(len(units) - 1, -1, -1):
        if units[idx].get("stress") in (1, 2):
            return len(units) - idx
    return 1


def _tail_char_span(word: str, tok_start: int, tok_end: int, units: list[dict], rhyme_syls: int = 1) -> tuple[int, int]:
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
    if rel_start >= 2 and word[rel_start - 2:rel_start].lower() in _ONSET_DIGRAPHS:
        rel_start -= 2
    elif rel_start >= 1 and word[rel_start - 1].lower() not in "aeiouy":
        rel_start -= 1

    if rel_start <= 0 or rel_start >= (tok_end - tok_start):
        return tok_start, tok_end
    return tok_start + rel_start, tok_end


def _clean_norm(word: str) -> str:
    clean = re.sub(r"^[^a-zA-Z]+|[^a-zA-Z']+$", "", (word or "").lower())
    return re.sub(r"['’]s$", "", clean)


def _token_rhyme_parts(tok: dict) -> frozenset:
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
    parts = _token_rhyme_parts(tok)
    if parts:
        return ("CMU", next(iter(parts)))

    phones = _strip_stress(tok.get("phones") or [])
    vowels = [i for i, p in enumerate(phones) if p in VOWEL_FEATURES]
    if not vowels:
        return None
    ending = phones[vowels[-1]:]
    if len(ending) == 1 and ending[0] not in ("AY", "AW", "OY") and len(vowels) >= 2:
        ending = (phones[vowels[-2]],) + ending
    return ("SOUND", ending)


NEAR_RHYME_MIN_CONF = 66.0


def _near_rhyme_strength(tok_a: dict, tok_b: dict) -> tuple[float, str]:
    if tok_a["norm"] == tok_b["norm"] or not tok_a["units"] or not tok_b["units"]:
        return 0.0, "None"
    ka, kb = _token_rhyme_key(tok_a), _token_rhyme_key(tok_b)
    if ka is not None and ka == kb:
        return 0.0, "None"
    conf, cat, _ = score_rhyme_pair(tok_a["units"], tok_b["units"])
    if cat in ("Slant Rhyme", "Assonance") and conf >= NEAR_RHYME_MIN_CONF:
        return conf, cat
    return 0.0, "None"


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
    and line-distance window splitting. Wordplay detection is handled on-demand by Gemini AI.
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

    buckets = defaultdict(list)
    for tok in tokens:
        if tok["is_stopword"] and not tok["is_line_end"]:
            continue
        r_key = _token_rhyme_key(tok)
        if r_key is not None:
            buckets[(tok["section"], r_key)].append(tok)

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

    n_colors = max(1, int(palette_size or DEFAULT_PALETTE_SIZE))
    for tok in tokens:
        gid = tok["rhyme_group"]
        tok["color_idx"] = (gid % n_colors) if gid is not None else None
        if granularity == "word" or gid is None:
            tok["rhyme_start"], tok["rhyme_end"] = tok["start"], tok["end"]
        tok["is_syllable_rhyme"] = tok["rhyme_start"] > tok["start"]

    total_rhymes = sum(1 for t in tokens if t["rhyme_group"] is not None)
    total_near = sum(1 for t in tokens if t["near_rhyme"] is not None and t["rhyme_group"] is None)

    return {
        "total_near": total_near,
        "lines": lines_info,
        "tokens": tokens,
        "total_rhymes": total_rhymes,
        "total_multies": 0,
        "total_wordplay": 0,
    }


# =====================================================================
# RHYME ENGINE SIDEBAR LOOKUP 
# =====================================================================
_RHYME_PART_INDEX: dict[str, list[tuple[str, int]]] = {}
_VOWEL_TAIL_INDEX: dict[str, list[tuple[str, int]]] = {}
_BM_RHYME_INDEX: list[tuple[str, dict]] = []
_BM_RHYME_INDEX_SIG: tuple[int, int] = (-1, -1)


def _ensure_rhyme_lookup_indexes() -> None:
    if _RHYME_PART_INDEX:
        return

    seen_pairs: set[tuple[str, str]] = set()

    def _index_word(w_low: str, phones: list[str] | tuple[str, ...]):
        part = _rhyming_part(phones)
        if not part:
            return
        pair = (part, w_low)
        if pair in seen_pairs:
            return
        seen_pairs.add(pair)
        syls = sum(1 for p in phones if re.sub(r"\d", "", p) in VOWEL_FEATURES)
        syls = max(1, syls)
        _RHYME_PART_INDEX.setdefault(part, []).append((w_low, syls))

        part_tokens = part.split()
        if part_tokens:
            lead_vowel = part_tokens[0]
            if lead_vowel in VOWEL_FEATURES:
                _VOWEL_TAIL_INDEX.setdefault(lead_vowel, []).append((w_low, syls))

    for w_ov, ph_ov in EN_ARPABET_OVERRIDES.items():
        _index_word(w_ov, ph_ov)

    for w_cmu, prons in _CMU_DICT.items():
        if not re.match(r"^[a-z][a-z'-]{1,22}$", w_cmu):
            continue
        for pr in prons[:2]:
            _index_word(w_cmu, pr)

    for part_k in _RHYME_PART_INDEX:
        _RHYME_PART_INDEX[part_k].sort(key=lambda item: (item[1], item[0]))


def _get_bm_rhyme_pool() -> list[tuple[str, dict]]:
    global _BM_RHYME_INDEX, _BM_RHYME_INDEX_SIG
    sig = (len(BM_LEXICON_HINTS), len(LEXICON.active_pack_words))
    if _BM_RHYME_INDEX and _BM_RHYME_INDEX_SIG == sig:
        return _BM_RHYME_INDEX

    bm_words = set(BM_LEXICON_HINTS)
    for w in LEXICON.active_pack_words:
        if detect_word_language(w, LEXICON.active_pack_words) == "BM":
            bm_words.add(w)

    built = []
    for w in sorted(bm_words):
        prof = LEXICON.get_phonetic_profile(w, force_lang="BM")
        if prof["units"]:
            built.append((w, prof))
    _BM_RHYME_INDEX = built
    _BM_RHYME_INDEX_SIG = sig
    return _BM_RHYME_INDEX


NEAREST_LIMIT = 12


def _vowel_positions(phones: tuple[str, ...]) -> list[int]:
    return [i for i, p in enumerate(phones) if p in VOWEL_FEATURES]


def _shared_suffix_len(a: tuple[str, ...], b: tuple[str, ...]) -> int:
    n = 0
    while n < min(len(a), len(b)) and a[-1 - n] == b[-1 - n]:
        n += 1
    return n


def _bm_rhyme_tier(target: tuple[str, ...], cand: tuple[str, ...]) -> int:
    va, vb = _vowel_positions(target), _vowel_positions(cand)
    if not va or not vb or target[va[-1]:] != cand[vb[-1]:]:
        return 0
    if len(va) == 1:
        return 4
    if len(vb) == 1 or target[va[-2]] != cand[vb[-2]]:
        return 1
    if target[va[-2]:] == cand[vb[-2]:]:
        return 4
    return 3 if target[max(va[-1] - 1, 0):] == cand[max(vb[-1] - 1, 0):] else 2


def _looks_malay(word_low: str) -> bool:
    if word_low in EN_ARPABET_OVERRIDES or _all_cmu_pronunciations(word_low):
        return False
    if re.search(r"(th|ph|wh|ck|ee|oo|ou|ow|igh|tion|q|x|[^aeiou]e$|[^aeiou]y$)", word_low):
        return False
    return bool(re.search(r"([aiu]|ng|ah|an|ak|at|am|ap|ar|al|as|uk|up|um|ur|ul|us|ut|uh|ik|ih|in|it|ip|ir|il|is|im)$", word_low))


def _syl_badge(syls: int) -> str:
    return f" ·{syls}s" if syls >= 2 else ""


_CUSTOM_POOL_CACHE = {
    "sig": None,
    "by_part": {},
    "by_vowel": {},
    "fallback": [],
}


def _get_indexed_custom_candidates(target_parts: list[str], t_phones: tuple, is_bm: bool) -> list[tuple[str, dict]]:
    """Build O(1) phonetic buckets for custom_slang + active_pack_words (supports 300k+ entries)."""
    slang_keys = tuple(LEXICON.custom_slang.keys())
    pack_words = LEXICON.active_pack_words
    pack_len = len(pack_words)
    # Fast lightweight signature to detect pack/slang updates without hashing 300k strings every call
    sample = tuple(list(pack_words)[:5] + list(pack_words)[-5:]) if pack_len else ()
    sig = (len(slang_keys), slang_keys[:10], pack_len, sample)

    if _CUSTOM_POOL_CACHE["sig"] != sig:
        by_part: dict[str, list[tuple[str, dict]]] = {}
        by_vowel: dict[str, list[tuple[str, dict]]] = {}
        fallback: list[tuple[str, dict]] = []

        seen = set()
        for raw_cand in list(slang_keys) + list(pack_words):
            cand = raw_cand.strip()
            if not cand or cand in seen:
                continue
            seen.add(cand)

            # For multi-word lines/phrases, index by the final word's phonetics
            tail_word = cand.split()[-1] if " " in cand else cand
            c_prof = LEXICON.get_phonetic_profile(tail_word)
            phones = c_prof.get("phones", ())
            stripped = _strip_stress(phones)

            rpart = _rhyming_part(phones) if phones else ""
            if rpart:
                by_part.setdefault(rpart, []).append((cand, c_prof))

            v_pos = _vowel_positions(stripped) if stripped else []
            if v_pos:
                last_v = stripped[v_pos[-1]]
                by_vowel.setdefault(last_v, []).append((cand, c_prof))
            else:
                fallback.append((cand, c_prof))

        _CUSTOM_POOL_CACHE["sig"] = sig
        _CUSTOM_POOL_CACHE["by_part"] = by_part
        _CUSTOM_POOL_CACHE["by_vowel"] = by_vowel
        _CUSTOM_POOL_CACHE["fallback"] = fallback

    # Retrieve only relevant phonetic buckets instead of scanning all 300k+ entries
    bucket: list[tuple[str, dict]] = []
    seen_cands = set()

    for part in target_parts:
        for item in _CUSTOM_POOL_CACHE["by_part"].get(part, ()):
            if item[0] not in seen_cands:
                seen_cands.add(item[0])
                bucket.append(item)

    v_pos_t = _vowel_positions(t_phones) if t_phones else []
    if v_pos_t:
        last_v_t = t_phones[v_pos_t[-1]]
        for item in _CUSTOM_POOL_CACHE["by_vowel"].get(last_v_t, ()):
            if item[0] not in seen_cands:
                seen_cands.add(item[0])
                bucket.append(item)

    if is_bm and not bucket:
        bucket.extend(_CUSTOM_POOL_CACHE["fallback"][:500])

    return bucket


def find_rhymes_for_word(word: str, limit: int = 150) -> dict:
    clean = re.sub(r"^[^A-Za-z0-9'-]+|[^A-Za-z0-9'-]+$", "", word).strip()
    if not clean:
        return {
            "word": "",
            "syllables": 0,
            "lang": "EN",
            "phones": [],
            "perfect_en": [],
            "perfect_bm": [],
            "perfect_custom": [],
            "slant": [],
        }

    _ensure_rhyme_lookup_indexes()
    target_prof = LEXICON.get_phonetic_profile(clean)
    norm = target_prof["norm"]
    if (target_prof["lang"] != "BM" and not target_prof["pron_override"]
            and HAS_CMU_SOURCE and _looks_malay(norm)):
        target_prof = LEXICON.get_phonetic_profile(clean, force_lang="BM")
    is_bm = target_prof["lang"] == "BM"
    t_phones = _strip_stress(target_prof["phones"])

    target_parts: list[str] = []
    if target_prof["phones"]:
        p0 = _rhyming_part(target_prof["phones"])
        if p0:
            target_parts.append(p0)
    if not is_bm and not target_prof["pron_override"]:
        for pr in _all_cmu_pronunciations(norm):
            p_cmu = _rhyming_part(pr)
            if p_cmu and p_cmu not in target_parts:
                target_parts.append(p_cmu)

    def _match_tier(c_prof: dict) -> int:
        c_phones = _strip_stress(c_prof["phones"])
        if not c_phones:
            return 0
        if is_bm:
            return _bm_rhyme_tier(t_phones, c_phones)
        if c_prof["lang"] == "BM":
            for part in target_parts:
                p = tuple(part.split())
                v = _vowel_positions(c_phones)
                if v and c_phones[-len(p):] == p:
                    return 4
            return 0
        return 4 if _rhyming_part(c_prof["phones"]) in target_parts else 0

    def _closeness(c_prof: dict) -> tuple:
        return (-_shared_suffix_len(t_phones, _strip_stress(c_prof["phones"])),
                abs(c_prof["syllables"] - target_prof["syllables"]))

    perfect_en: list[str] = []
    if not is_bm:
        found: dict[str, tuple] = {}
        for part in target_parts:
            for cand, syls in _RHYME_PART_INDEX.get(part, []):
                if cand == norm or cand in found:
                    continue
                phones = next((pr for pr in ((tuple(EN_ARPABET_OVERRIDES.get(cand, ())),)
                                             + _all_cmu_pronunciations(cand))
                               if pr and _rhyming_part(pr) == part), ())
                shared = _shared_suffix_len(t_phones, _strip_stress(phones))
                found[cand] = (-shared, abs(syls - target_prof["syllables"]), cand, syls)
        perfect_en = [f"{c}{_syl_badge(v[3])}"
                      for c, v in sorted(found.items(), key=lambda kv: kv[1][:3])][:limit]

    bm_matches = []
    for cand, c_prof in _get_bm_rhyme_pool():
        if cand != norm:
            tier = _match_tier(c_prof)
            if tier:
                bm_matches.append((tier, _closeness(c_prof), cand, c_prof))

    custom_matches = []
    for cand, c_prof in _get_indexed_custom_candidates(target_parts, t_phones, is_bm):
        if cand != norm:
            tier = _match_tier(c_prof)
            if tier:
                custom_matches.append((tier, _closeness(c_prof), cand, c_prof))

    best = max((m[0] for m in bm_matches + custom_matches), default=0)

    def _top(matches):
        return sorted((m for m in matches if m[0] == best and best >= 2), key=lambda m: (m[1], m[2]))

    perfect_bm = [f"{c}{_syl_badge(p['syllables'])}" for _, _, c, p in _top(bm_matches)][:limit]

    perfect_custom: list[str] = []
    for _, _, cand, _p in _top(custom_matches):
        is_slang = cand in LEXICON.custom_slang
        perfect_custom.append(f"{cand} [slang]" if is_slang else cand)
    perfect_custom = perfect_custom[:limit]

    slant: list[str] = []
    if not (perfect_en or perfect_bm or perfect_custom):
        near: dict[str, tuple] = {}
        for tier, key, cand, c_prof in bm_matches + custom_matches:
            near[cand] = (0, key, cand, f"{cand} [near]")
        if not is_bm:
            t_tail = _rhyme_tail_units(target_prof["units"])
            lead_v = t_tail[0]["vowel"] if t_tail else ""
            for cand, _syls in _VOWEL_TAIL_INDEX.get(lead_v, []):
                if cand == norm or cand in near:
                    continue
                c_units = extract_syllable_units(_lookup_cmu_phones(cand))
                c_tail = _rhyme_tail_units(c_units)
                if len(c_tail) != len(t_tail) or c_tail[0]["vowel"] != lead_v:
                    continue
                if any(a["vowel"] != b["vowel"] for a, b in zip(t_tail, c_tail)):
                    continue
                conf = sum(consonant_seq_similarity(a["coda"], b["coda"])
                           for a, b in zip(t_tail, c_tail)) / len(t_tail)
                if conf >= 0.5:
                    pct = int(65 + 34 * min(conf, 1.0))
                    near[cand] = (1, (-conf, len(cand)), cand, f"{cand} [{pct}%]")
        slant = [v[3] for v in sorted(near.values(), key=lambda v: v[:3])][:min(limit, NEAREST_LIMIT)]

    return {
        "word": clean,
        "syllables": target_prof["syllables"],
        "lang": target_prof["lang"],
        "phones": target_prof["phones"],
        "perfect_en": perfect_en[:limit],
        "perfect_bm": perfect_bm[:limit],
        "perfect_custom": perfect_custom[:limit],
        "slant": slant,
    }


# =====================================================================
# PEN METER SCORECARD (rate_lyrics_comprehensive)
# =====================================================================
MIN_UNIQUE_BARS = 4


def rate_lyrics_comprehensive(
    text: str,
    rhyme_window: int = 4,
) -> dict:
    res = analyze_lyrics(text, rhyme_window=rhyme_window)

    lines = res["lines"]
    tokens = res["tokens"]

    active_lines = [l for l in lines if not l["is_header"] and l["syllables"] > 0]
    bars = len(active_lines)
    word_count = len(tokens)

    seen_text, unique_lines = set(), []
    for l in active_lines:
        key = " ".join(tokens[i]["norm"] for i in l["token_indices"])
        if key not in seen_text:
            seen_text.add(key)
            unique_lines.append(l)
    n_unique = len(unique_lines)

    if n_unique < MIN_UNIQUE_BARS:
        return {
            "overall": 0,
            "tier": "NEED 4+ UNIQUE BARS" if bars else "EMPTY SHEET",
            "color": "#A1A1AA",
            "metrics": {"bars": bars, "words": word_count, "multie_chains": 0},
            "breakdown": {"multies": 0, "flow": 0, "structure": 0, "vocab": 0},
            "highlights": [],
            "tips": [f"Write at least {MIN_UNIQUE_BARS} different bars to get a score."],
        }

    unique_tokens = [tokens[i] for l in unique_lines for i in l["token_indices"]]

    group_words = defaultdict(set)
    for t in unique_tokens:
        if t["rhyme_group"] is not None:
            group_words[t["rhyme_group"]].add(t["norm"])
    rhyming = [t for t in unique_tokens
               if t["rhyme_group"] is not None and len(group_words[t["rhyme_group"]]) >= 2]
    end_points = sum(1.0 if t in rhyming else (0.25 if t["near_rhyme"] else 0.0)
                     for t in unique_tokens if t["is_line_end"])
    internal = {(t["rhyme_group"], t["norm"]) for t in rhyming
                if not t["is_line_end"] and not t["is_stopword"]
                and any(o["rhyme_group"] == t["rhyme_group"] and o["norm"] != t["norm"]
                        and abs(o["line"] - t["line"]) <= 1 for o in rhyming)}
    rhyme_score = end_points / n_unique * 70.0 + min(1.0, len(internal) / n_unique / 1.5) * 30.0
    if rhyming:
        variety = len({t["norm"] for t in rhyming}) / len(rhyming)
        rhyme_score *= min(1.0, variety * 1.4)
    multies_score = min(100, int(round(rhyme_score)))

    diffs = []
    for prev, cur in zip(lines, lines[1:]):
        if all(l["syllables"] > 0 and not l["is_header"] for l in (prev, cur)):
            diffs.append(abs(cur["syllables"] - prev["syllables"]))
    if diffs:
        avg_diff = sum(diffs) / float(len(diffs))
        flow_score = max(25, min(100, int(round(100.0 - max(0.0, avg_diff - 1.5) * 11.0))))
    else:
        flow_score = 60

    filled_sections, waiting_header = 0, False
    for l in lines:
        if l["is_header"]:
            waiting_header = True
        elif l["syllables"] > 0 and waiting_header:
            filled_sections += 1
            waiting_header = False
    structure_score = min(100, 45 + filled_sections * 15 + min(25, n_unique * 2))

    content = [t["norm"] for t in unique_tokens if not t["is_stopword"]]
    vocab_score = int(round(len(set(content)) / len(content) * 100.0)) if content else 0

    overall = int(round(
        0.40 * multies_score
        + 0.27 * flow_score
        + 0.20 * structure_score
        + 0.13 * vocab_score
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
    for t in unique_tokens:
        if t["line"] in seen_lines:
            continue
        if t in rhyming and not t["is_line_end"] and t["rhyme_confidence"] >= 82.0:
            highlights.append({
                "badge": f"🎵 INTERNAL RHYME ({int(t['rhyme_confidence'])}%)",
                "detail": f"L{t['line'] + 1:02d}: '{t['word']}' — {t['rhyme_explanation']}",
                "line": t["line"],
            })
            seen_lines.add(t["line"])

    tips = []
    if multies_score < 65:
        tips.append("Make more bar endings rhyme, then add internal rhymes with different words.")
    if flow_score < 65:
        tips.append("Syllable counts vary a lot between neighbouring bars. Check them against your beat.")
    if vocab_score < 60:
        tips.append("Many content words repeat. Try swapping some of them.")
    if not tips:
        tips.append("The technical checks look good. This score cannot judge delivery or vocal tone.")

    return {
        "overall": overall,
        "tier": tier,
        "color": color,
        "metrics": {
            "bars": bars,
            "words": word_count,
            "multie_chains": len(internal),
        },
        "breakdown": {
            "multies": multies_score,
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

def check_rhyme_pair(word_a: str, word_b: str) -> dict:
    """Compare two words/phrases and return phonetic similarity breakdown."""
    w1 = re.sub(r"[^a-zA-Z0-9'-]", "", (word_a or "").strip().lower())
    w2 = re.sub(r"[^a-zA-Z0-9'-]", "", (word_b or "").strip().lower())

    if not w1 or not w2:
        return {"score": 0, "label": "Enter 2 words", "phon_a": "-", "phon_b": "-", "match_part": "-"}

    if w1 == w2:
        return {"score": 100, "label": "Identical Word", "phon_a": w1.upper(), "phon_b": w2.upper(), "match_part": w1.upper()}

    # Analisis kedua-dua perkataan melalui enjin sedia ada
    sample_text = f"{w1}\n{w2}"
    res = analyze_lyrics(sample_text, rhyme_window=4, granularity="syllable")
    tokens = res.get("tokens", [])

    tok_a = tokens[0] if len(tokens) >= 1 else {}
    tok_b = tokens[1] if len(tokens) >= 2 else {}

    key_a = str(tok_a.get("rhyme_key") or tok_a.get("phonetic") or w1[-3:])
    key_b = str(tok_b.get("rhyme_key") or tok_b.get("phonetic") or w2[-3:])

    is_exact_group = (
        tok_a.get("rhyme_group") is not None
        and tok_a.get("rhyme_group") == tok_b.get("rhyme_group")
    )
    is_near = bool(tok_a.get("near_rhyme") or tok_b.get("near_rhyme"))

    # Kira persamaan ekor fonetik / vokal
    tail_a = key_a.split("-")[-1] if "-" in key_a else key_a[-3:]
    tail_b = key_b.split("-")[-1] if "-" in key_b else key_b[-3:]

    vowels_a = "".join(re.findall(r"[aeiou]+", w1))
    vowels_b = "".join(re.findall(r"[aeiou]+", w2))

    if is_exact_group:
        score = 96 if tail_a == tail_b else 88
        label = "🔥 Perfect / Strong Rhyme"
    elif tail_a == tail_b and len(tail_a) >= 2:
        score = 85
        label = "✨ End-Syllable Rhyme"
    elif is_near or (vowels_a and vowels_b and vowels_a[-2:] == vowels_b[-2:]):
        score = 68
        label = "〰 Slant / Assonance Match"
    elif vowels_a and vowels_b and vowels_a[-1:] == vowels_b[-1:]:
        score = 45
        label = "🔸 Loose Vowel Match"
    else:
        score = 12
        label = "✖ Weak / No Rhyme"

    return {
        "score": score,
        "label": label,
        "phon_a": key_a.upper(),
        "phon_b": key_b.upper(),
        "match_part": tail_a.upper() if score >= 45 else "NONE",
    }

def run_songwriting_coach(lyrics_text: str, mode: str = "critique", focus_problem: str = "") -> dict:
    """Offline Songwriting Coach following Vocaler SKILL.md rules (no ghostwriting, quote real lines)."""
    raw_lines = [ln.strip() for ln in (lyrics_text or "").splitlines()]
    lyric_lines = [ln for ln in raw_lines if ln and not (ln.startswith("[") and ln.endswith("]"))]
    section_headers = [ln.upper() for ln in raw_lines if ln.startswith("[") and ln.endswith("]")]

    # 1. Mode: Writer's Block (tidak perlukan lirik penuh)
    if mode == "block":
        exercises = [
            ("Object Writing (5 Mins)", "Pick one physical object near you right now (e.g. a cracked phone screen, cold kopi, rain on zinc). Write non-stop for 5 minutes using only the 5 senses—no rhyming allowed."),
            ("Destination Writing", "Write your ending hook line first—the exact truth you want the listener to remember—then write 4 bars leading into that landing."),
            ("Title-First Constraint", "Lock a 2-to-4 word song title. Every bar in your first 8 lines must connect back to an image implied by that title."),
        ]
        ex_title, ex_desc = exercises[len(lyric_lines) % len(exercises)]
        return {
            "what_works": "You showed up to the blank page with a clear intent to break through resistance instead of forcing generic filler bars.",
            "notes": [
                "Waiting for a 'perfect' opening bar stalls momentum (why: your inner editor blocks raw ideas before they exist) — Ask yourself: What is the ugliest, most honest 4-bar version I can write in 3 minutes?",
                "Starting with abstract emotions ('sad', 'hustle', 'pain') feels vague (why: listeners connect to scenes they can picture) — Ask yourself: What specific place, time, or object proves that feeling?",
            ],
            "exercise": f"{ex_title}: {ex_desc}",
            "next_step": "Set a 10-minute timer, write 8 unedited lines in the canvas without hitting Backspace, then run Professional Critique.",
        }

    if not lyric_lines:
        return {
            "what_works": "Your canvas is clean and ready for a fresh draft.",
            "notes": [
                "No lyrics detected in the active editor yet (why: feedback requires real lines to quote and measure) — Ask yourself: What single moment or story is this track about?",
            ],
            "exercise": "10-Minute Timed Draft: Write at least 8 bars in your natural voice before checking rhymes.",
            "next_step": "Draft 4 to 8 bars in the editor, then click Analyze again.",
        }

    # Analisis baris melalui enjin fonetik sedia ada
    analysis = analyze_lyrics("\n".join(lyric_lines), rhyme_window=4, granularity="syllable")
    tokens = analysis.get("tokens", [])

    # Kira suku kata & skema rima hujung setiap baris
    line_syllables = []
    end_keys = []
    for idx, ln in enumerate(lyric_lines):
        words = re.findall(r"[a-zA-Z0-9'-]+", ln.lower())
        syl = sum(max(1, len(re.findall(r"[aeiouy]+", w))) for w in words) if words else 0
        line_syllables.append(syl)
        line_toks = [t for t in tokens if t.get("line") == idx]
        if line_toks:
            end_keys.append(str(line_toks[-1].get("rhyme_key") or words[-1][-2:]))
        else:
            end_keys.append(words[-1][-2:] if words else "")

    # Kenal pasti skema rima 4 baris pertama
    scheme_letters = []
    seen_keys = {}
    alphabet = "ABCD"
    for k in end_keys[:4]:
        if k not in seen_keys:
            seen_keys[k] = alphabet[len(seen_keys)] if len(seen_keys) < 4 else "X"
        scheme_letters.append(seen_keys[k])
    rhyme_scheme = "".join(scheme_letters) if len(scheme_letters) == 4 else ""

    # Cari baris paling kuat untuk "What works"
    best_idx = 0
    best_score = -1
    for i, ln in enumerate(lyric_lines):
        w_cnt = len(ln.split())
        # Beri keutamaan kepada baris dengan kepadatan suku kata seimbang & perkataan konkrit
        sc = w_cnt + (3 if 7 <= line_syllables[i] <= 14 else 0)
        if sc > best_score:
            best_score = sc
            best_idx = i

    quoted_best = lyric_lines[best_idx]
    scheme_note = f" Your opening 4-bar end-rhyme scheme locks into {rhyme_scheme}." if rhyme_scheme and len(set(rhyme_scheme)) < 4 else ""
    what_works = f"Line {best_idx + 1} (\"{quoted_best}\") carries clear rhythmic momentum ({line_syllables[best_idx]} syllables).{scheme_note}"

    # Bina Notes (maksimum 3)
    notes = []

    # Semak Clichés (EN & BM)
    cliches = [
        "from the bottom", "started from the bottom", "broken heart", "tears fall",
        "chase my dreams", "chasing dreams", "haters gonna hate", "fake friends",
        "real ones", "pain inside", "lost in the dark", "hujan turun", "hati luka",
        "air mata", "mimpi indah", "janji palsu", "dunia kejam"
    ]
    found_cliche = None
    cliche_line_num = 0
    for i, ln in enumerate(lyric_lines):
        low = ln.lower()
        for c in cliches:
            if c in low:
                found_cliche = c
                cliche_line_num = i + 1
                break
        if found_cliche:
            break

    if found_cliche:
        notes.append(
            f"Line {cliche_line_num} uses the stock phrase '{found_cliche}' (why: clichés feel predictable so listeners tune out) — Ask yourself: What specific detail from your own life shows this instead?"
        )

    # Semak Abstract vs Concrete ("Show, don't tell")
    abstract_words = {"love", "pain", "hate", "sad", "happy", "alone", "lost", "broken", "soul", "dream", "cinta", "rindu", "sedih", "kecewa", "sakit", "jiwa", "sunyi"}
    all_words = re.findall(r"[a-zA-Z']+", " ".join(lyric_lines).lower())
    abs_hits = [w for w in all_words if w in abstract_words]
    if len(abs_hits) >= 2 and len(notes) < 3:
        sample_abs = ", ".join(dict.fromkeys(abs_hits[:3]))
        notes.append(
            f"Heavy reliance on abstract words ({sample_abs}) (why: 'telling' emotions leaves the listener with nothing visual to hold onto) — Ask yourself: Which 2 abstract words can you replace with something a camera could film?"
        )

    # Semak lompatan suku kata (Cadence / Prosody)
    if len(line_syllables) >= 2 and len(notes) < 3:
        diffs = [(abs(line_syllables[i] - line_syllables[i - 1]), i) for i in range(1, len(line_syllables))]
        max_jump, jump_idx = max(diffs, key=lambda x: x[0])
        if max_jump >= 6:
            notes.append(
                f"Sharp syllable jump between Line {jump_idx} ({line_syllables[jump_idx - 1]} syl) and Line {jump_idx + 1} ({line_syllables[jump_idx]} syl) (why: sudden count swings can trip your vocal pocket on beat) — Ask yourself: Are you intentionally double-timing Line {jump_idx + 1}, or can you trim 2–3 filler words?"
            )

    # Semak struktur lagu (untuk Finish Song Plan atau draft pendek)
    if (mode == "finish" or len(lyric_lines) < 12) and len(notes) < 3:
        has_hook = any("HOOK" in h or "CHORUS" in h for h in section_headers)
        if not has_hook:
            notes.append(
                f"Draft is currently {len(lyric_lines)} lines with no labeled [Hook] / [Chorus] section (why: without a central anchor, verses wander instead of building toward a payoff) — Ask yourself: Which 2 bars in your draft summarize the whole song's thesis?"
            )

    if not notes:
        notes.append(
            f"Your {len(lyric_lines)}-bar flow holds steady cadence, though end-rhymes stay mostly single-syllable (why: multi-syllabic end rhymes elevate replay value) — Ask yourself: Can you bend the last two words of Line 2 and Line 4 to share two vowel sounds?"
        )

    # Pilih Exercise & Next Step mengikut mode
    if mode == "finish":
        exercise = "Destination Writing (10 Mins): Write your 4-bar [Hook] first, then write a 4-bar [Bridge] that flips the perspective before returning to the hook."
        next_step = "Add [Verse 1] and [Hook] headers in your lyrics, complete the missing section, and check your score in Pen Meter."
    elif mode == "fix":
        target = focus_problem.strip() or "your weakest bar"
        exercise = f"3-Pass Rewrite on '{target}': Write 3 alternate versions of that single line—Pass 1 for pure meaning, Pass 2 for sharper imagery, Pass 3 for tighter rhythm."
        next_step = "Test your new end-word pair inside the Rhyme Checker on the right panel to verify sound strength."
    else:
        exercise = "Object Writing (5 Mins): Pick one physical object mentioned or implied in your verse and list 5 sensory details (sight, sound, texture) to swap into your weak bars."
        next_step = "Pick Note #1, revise just those lines in the editor, and use Rhyme Checker to verify your updated end rhymes."

    return {
        "what_works": what_works,
        "notes": notes[:3],
        "exercise": exercise,
        "next_step": next_step,
    }
