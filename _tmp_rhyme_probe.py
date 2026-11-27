import time
import lyric_engine as le

# Simulate the shipped CMU pronunciations for the requested example.
le._CMU_DICT = {
    "enemies": [["EH1", "N", "AH0", "M", "IY0", "Z"]],
    "memories": [["M", "EH1", "M", "ER0", "IY0", "Z"]],
    "remedies": [["R", "EH1", "M", "AH0", "D", "IY0", "Z"]],
    "friendly": [["F", "R", "EH1", "N", "D", "L", "IY0"]],
    "tennis": [["T", "EH1", "N", "IH0", "S"]],
    "night": [["N", "AY1", "T"]],
    "light": [["L", "AY1", "T"]],
}
le.HAS_CMU_SOURCE = True
le.LEXICON.add_language_pack("English - Frequency Words", [
    "enemies", "memories", "remedies", "friendly", "tennis", "night", "light", "time",
])
le.LEXICON.add_language_pack("Bahasa Melayu - Test", ["cinta", "dunia", "bicara", "kata", "malam"])
le.warm_up_rhyme_index()

res = le.find_rhymes_for_word("enemies", 150)
expected = {"memories", "remedies", "friendly", "tennis"}
got = {s.rsplit(" [near]", 1)[0] for s in res["slant"]}
print("enemies slant:", res["slant"])
print("all expected present:", expected <= got, "labels ok:", all(s.endswith(" [near]") for s in res["slant"]))

night = le.find_rhymes_for_word("night", 150)
print("night exact count:", len(night["perfect_en"]), "slant count:", len(night["slant"]))
print("exact not repeated in slant:", not ({le._base_rhyme_word(x) for x in night["perfect_en"]} & {s.rsplit(" [near]",1)[0] for s in night["slant"]}))

bm = le.find_rhymes_for_word("cinta", 150)
print("cinta BM:", bm["lang"], "exact:", bm["perfect_bm"][:3], "slant:", bm["slant"][:5])
print("bm labels ok:", all(s.endswith(" [near]") for s in bm["slant"]))

# Pack-only target still resolves through fallback G2P and gets near rhymes.
le.LEXICON.add_language_pack("English - Frequency Words", ["sublime", "crime", "rhyme", "lime", "dime"])
le.warm_up_rhyme_index()
sub = le.find_rhymes_for_word("sublime", 150)
print("sublime target:", sub["lang"], "exact:", sub["perfect_custom"][:4], "slant:", sub["slant"][:4])
