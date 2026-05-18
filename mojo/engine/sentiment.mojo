"""
sentiment.mojo — Sentiment analysis. Zero Python imports.

Replaces textblob/vaderSentiment basics with a pure Mojo lexicon-based
sentiment scorer, polarity/subjectivity calculator, and word-level analysis.

Public API:
  sentiment_score       — Score from -1 to +1 using built-in lexicon
  sentiment_label       — "positive" / "negative" / "neutral"
  word_sentiment        — Lookup single word in lexicon
  polarity              — Alias for sentiment_score
  subjectivity          — Proportion of words found in lexicon
  count_positive_words  — Count words with positive sentiment
  count_negative_words  — Count words with negative sentiment
  most_positive_word    — Word with highest sentiment score
  most_negative_word    — Word with lowest sentiment score
  tokenize_lower        — Lowercase tokenization (split on spaces, strip punct)
"""


# ── _is_alpha_byte ────────────────────────────────────────────────────────────


fn _is_alpha_byte(c: UInt8) -> Bool:
    """Check if a byte is alphabetic ASCII."""
    return (c >= 97 and c <= 122) or (c >= 65 and c <= 90)


fn _to_lower_byte(c: UInt8) -> UInt8:
    """Convert uppercase ASCII byte to lowercase."""
    if c >= 65 and c <= 90:
        return c + 32
    return c


# ── tokenize_lower ───────────────────────────────────────────────────────────


fn tokenize_lower(text: String) -> List[String]:
    """Lowercase tokenization: split on spaces, strip basic punctuation."""
    var bs = text.as_bytes()
    var n = len(text)
    var tokens = List[String]()
    var start = -1
    for i in range(n):
        var c = bs[i]
        if c == 32 or c == 9 or c == 10:  # space, tab, newline
            if start >= 0:
                var tok = String("")
                for j in range(start, i):
                    var b = bs[j]
                    if _is_alpha_byte(b) or b == 39 or b == 45:  # ' or -
                        tok += chr(Int(_to_lower_byte(b)))
                if len(tok) > 0:
                    tokens.append(tok^)
                start = -1
        else:
            if start < 0:
                start = i
    if start >= 0:
        var tok = String("")
        for j in range(start, n):
            var b = bs[j]
            if _is_alpha_byte(b) or b == 39 or b == 45:
                tok += chr(Int(_to_lower_byte(b)))
        if len(tok) > 0:
            tokens.append(tok^)
    return tokens^


# ── _lexicon_word / _lexicon_score ───────────────────────────────────────────
# Hardcoded lexicon of ~60 common sentiment words.
# We use parallel lists for word and score since Mojo lacks dict literals.


fn _lexicon_words() -> List[String]:
    """Return list of lexicon words."""
    var w = List[String]()
    # Positive words
    w.append("good")       # 0.7
    w.append("great")      # 0.9
    w.append("excellent")  # 0.95
    w.append("amazing")    # 0.9
    w.append("love")       # 0.8
    w.append("happy")      # 0.7
    w.append("wonderful")  # 0.85
    w.append("fantastic")  # 0.9
    w.append("best")       # 0.8
    w.append("perfect")    # 0.95
    w.append("beautiful")  # 0.8
    w.append("awesome")    # 0.85
    w.append("nice")       # 0.5
    w.append("fine")       # 0.3
    w.append("ok")         # 0.1
    w.append("brilliant")  # 0.9
    w.append("superb")     # 0.9
    w.append("outstanding")# 0.9
    w.append("lovely")     # 0.75
    w.append("pleasant")   # 0.6
    w.append("enjoy")      # 0.7
    w.append("delight")    # 0.8
    w.append("cheerful")   # 0.7
    w.append("positive")   # 0.6
    w.append("like")       # 0.4
    w.append("glad")       # 0.6
    w.append("joy")        # 0.8
    w.append("pleased")    # 0.6
    w.append("exciting")   # 0.75
    w.append("impressive") # 0.7
    # Negative words
    w.append("bad")        # -0.7
    w.append("terrible")   # -0.9
    w.append("awful")      # -0.9
    w.append("horrible")   # -0.95
    w.append("hate")       # -0.8
    w.append("sad")        # -0.7
    w.append("worst")      # -0.9
    w.append("ugly")       # -0.8
    w.append("poor")       # -0.6
    w.append("boring")     # -0.5
    w.append("angry")      # -0.7
    w.append("disappointing") # -0.6
    w.append("weak")       # -0.4
    w.append("fail")       # -0.7
    w.append("wrong")      # -0.5
    w.append("not")        # -0.3
    w.append("never")      # -0.3
    w.append("horrible")   # duplicate, skip in scores
    w.append("disgusting") # -0.85
    w.append("dreadful")   # -0.8
    w.append("miserable")  # -0.8
    w.append("annoying")   # -0.6
    w.append("frustrating")# -0.6
    w.append("painful")    # -0.7
    w.append("useless")    # -0.7
    w.append("disaster")   # -0.85
    w.append("trash")      # -0.7
    w.append("broken")     # -0.5
    w.append("fear")       # -0.6
    w.append("sick")       # -0.5
    return w^


fn _lexicon_scores() -> List[Float64]:
    """Return list of scores corresponding to _lexicon_words()."""
    var s = List[Float64]()
    # Positive
    s.append(0.7)   # good
    s.append(0.9)   # great
    s.append(0.95)  # excellent
    s.append(0.9)   # amazing
    s.append(0.8)   # love
    s.append(0.7)   # happy
    s.append(0.85)  # wonderful
    s.append(0.9)   # fantastic
    s.append(0.8)   # best
    s.append(0.95)  # perfect
    s.append(0.8)   # beautiful
    s.append(0.85)  # awesome
    s.append(0.5)   # nice
    s.append(0.3)   # fine
    s.append(0.1)   # ok
    s.append(0.9)   # brilliant
    s.append(0.9)   # superb
    s.append(0.9)   # outstanding
    s.append(0.75)  # lovely
    s.append(0.6)   # pleasant
    s.append(0.7)   # enjoy
    s.append(0.8)   # delight
    s.append(0.7)   # cheerful
    s.append(0.6)   # positive
    s.append(0.4)   # like
    s.append(0.6)   # glad
    s.append(0.8)   # joy
    s.append(0.6)   # pleased
    s.append(0.75)  # exciting
    s.append(0.7)   # impressive
    # Negative
    s.append(-0.7)  # bad
    s.append(-0.9)  # terrible
    s.append(-0.9)  # awful
    s.append(-0.95) # horrible
    s.append(-0.8)  # hate
    s.append(-0.7)  # sad
    s.append(-0.9)  # worst
    s.append(-0.8)  # ugly
    s.append(-0.6)  # poor
    s.append(-0.5)  # boring
    s.append(-0.7)  # angry
    s.append(-0.6)  # disappointing
    s.append(-0.4)  # weak
    s.append(-0.7)  # fail
    s.append(-0.5)  # wrong
    s.append(-0.3)  # not
    s.append(-0.3)  # never
    s.append(-0.95) # horrible (dup)
    s.append(-0.85) # disgusting
    s.append(-0.8)  # dreadful
    s.append(-0.8)  # miserable
    s.append(-0.6)  # annoying
    s.append(-0.6)  # frustrating
    s.append(-0.7)  # painful
    s.append(-0.7)  # useless
    s.append(-0.85) # disaster
    s.append(-0.7)  # trash
    s.append(-0.5)  # broken
    s.append(-0.6)  # fear
    s.append(-0.5)  # sick
    return s^


# ── word_sentiment ───────────────────────────────────────────────────────────


fn word_sentiment(word: String) -> Float64:
    """Lookup single word in lexicon. Returns score or 0 for unknown."""
    var lower = word.lower()
    var words = _lexicon_words()
    var scores = _lexicon_scores()
    for i in range(len(words)):
        if words[i] == lower:
            return scores[i]
    return 0.0


# ── sentiment_score ──────────────────────────────────────────────────────────


fn sentiment_score(text: String) -> Float64:
    """Score from -1 (negative) to +1 (positive) using built-in lexicon.
    Average of known word scores; 0 if no words found."""
    var tokens = tokenize_lower(text)
    var total: Float64 = 0.0
    var count: Int = 0
    for i in range(len(tokens)):
        var s = word_sentiment(tokens[i])
        if s != 0.0:
            total += s
            count += 1
    if count == 0:
        return 0.0
    return total / Float64(count)


# ── polarity ─────────────────────────────────────────────────────────────────


fn polarity(text: String) -> Float64:
    """Same as sentiment_score (alias)."""
    return sentiment_score(text)


# ── sentiment_label ──────────────────────────────────────────────────────────


fn sentiment_label(score: Float64) -> String:
    """"positive" if score > 0.05, "negative" if < -0.05, else "neutral"."""
    if score > 0.05:
        return "positive"
    if score < -0.05:
        return "negative"
    return "neutral"


# ── subjectivity ─────────────────────────────────────────────────────────────


fn subjectivity(text: String) -> Float64:
    """Proportion of words found in lexicon (subjective words)."""
    var tokens = tokenize_lower(text)
    var total = len(tokens)
    if total == 0:
        return 0.0
    var found: Int = 0
    for i in range(total):
        if word_sentiment(tokens[i]) != 0.0:
            found += 1
    return Float64(found) / Float64(total)


# ── count_positive_words ─────────────────────────────────────────────────────


fn count_positive_words(text: String) -> Int:
    """Count words with positive sentiment."""
    var tokens = tokenize_lower(text)
    var count: Int = 0
    for i in range(len(tokens)):
        if word_sentiment(tokens[i]) > 0.0:
            count += 1
    return count


# ── count_negative_words ─────────────────────────────────────────────────────


fn count_negative_words(text: String) -> Int:
    """Count words with negative sentiment."""
    var tokens = tokenize_lower(text)
    var count: Int = 0
    for i in range(len(tokens)):
        if word_sentiment(tokens[i]) < 0.0:
            count += 1
    return count


# ── most_positive_word ───────────────────────────────────────────────────────


fn most_positive_word(text: String) -> String:
    """Word with highest sentiment score."""
    var tokens = tokenize_lower(text)
    var best_word = String("")
    var best_score: Float64 = -2.0
    for i in range(len(tokens)):
        var s = word_sentiment(tokens[i])
        if s > best_score:
            best_score = s
            best_word = tokens[i]
    return best_word^


# ── most_negative_word ───────────────────────────────────────────────────────


fn most_negative_word(text: String) -> String:
    """Word with lowest sentiment score."""
    var tokens = tokenize_lower(text)
    var worst_word = String("")
    var worst_score: Float64 = 2.0
    for i in range(len(tokens)):
        var s = word_sentiment(tokens[i])
        if s < worst_score:
            worst_score = s
            worst_word = tokens[i]
    return worst_word^
