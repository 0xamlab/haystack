"""
tokenizer.mojo — Advanced text tokenizer utilities. Zero Python imports.

Extends the text package with word/sentence tokenization, n-grams,
stopword removal, simple stemming, and sequence padding.

Public API:
  word_tokenize      — Split on whitespace + punctuation, lowercase
  sentence_tokenize  — Split into sentences on .!? boundaries
  char_ngrams        — Character-level n-grams
  word_ngrams        — Word-level n-grams joined with "_"
  remove_stopwords   — Remove common English stopwords
  stem_simple        — Simple suffix stemmer (ing, ed, ly, s)
  vocabulary_size    — Count unique tokens
  token_frequency    — [[token, count_str], ...] sorted by freq desc
  pad_sequence       — Pad or truncate to fixed length
  is_stopword        — Check if word is a stopword
"""


# ── Helpers ───────────────────────────────────────────────────────────────────


fn _is_punct(c: Int) -> Bool:
    """True if byte is common ASCII punctuation (not alphanumeric/space)."""
    if c == ord(",") or c == ord(".") or c == ord("!") or c == ord("?"):
        return True
    if c == ord(";") or c == ord(":") or c == ord("'") or c == ord('"'):
        return True
    if c == ord("(") or c == ord(")") or c == ord("[") or c == ord("]"):
        return True
    if c == ord("{") or c == ord("}") or c == ord("-") or c == ord("/"):
        return True
    if c == ord("@") or c == ord("#") or c == ord("$") or c == ord("%"):
        return True
    if c == ord("&") or c == ord("*") or c == ord("+") or c == ord("="):
        return True
    if c == ord("<") or c == ord(">") or c == ord("\\") or c == ord("`"):
        return True
    if c == ord("~") or c == ord("^") or c == ord("|") or c == ord("_"):
        return True
    return False


fn _to_lower(c: Int) -> Int:
    """Lowercase an ASCII byte."""
    if c >= ord("A") and c <= ord("Z"):
        return c + 32
    return c


fn _is_whitespace(c: Int) -> Bool:
    """True if byte is whitespace."""
    return c == ord(" ") or c == ord("\t") or c == ord("\n") or c == ord("\r")


fn _substr(s: String, start: Int, end: Int) -> String:
    """Extract a substring from s using byte positions."""
    return String(s[byte=start:end])


fn _all_unique(tokens: List[String]) -> Bool:
    var n = len(tokens)
    for i in range(n):
        for j in range(i):
            if tokens[j] == tokens[i]:
                return False
    return True


fn is_stopword(word: String) -> Bool:
    """Check if word is a common English stopword (35 words)."""
    var b = word.as_bytes()
    var n = len(b)
    if n == 1:
        return Int(b[0]) == ord("a")

    if n == 2:
        var c0 = Int(b[0])
        var c1 = Int(b[1])
        if c0 == ord("a"):
            return c1 == ord("n") or c1 == ord("t") or c1 == ord("s")
        if c0 == ord("b"):
            return c1 == ord("e") or c1 == ord("y")
        if c0 == ord("d"):
            return c1 == ord("o")
        if c0 == ord("i"):
            return c1 == ord("n") or c1 == ord("f") or c1 == ord("s") or c1 == ord("t")
        if c0 == ord("o"):
            return c1 == ord("f") or c1 == ord("n") or c1 == ord("r")
        if c0 == ord("s"):
            return c1 == ord("o")
        if c0 == ord("t"):
            return c1 == ord("o")
        return False

    if n == 3:
        if word == "the" or word == "are" or word == "was" or word == "has":
            return True
        if word == "had" or word == "did" or word == "for" or word == "and":
            return True
        if word == "but" or word == "not":
            return True
        return False

    if n == 4:
        if word == "were" or word == "been" or word == "have" or word == "does":
            return True
        if word == "with" or word == "this" or word == "that" or word == "from":
            return True
        return False

    if n == 5:
        return word == "being"
    return False


# ── Word Tokenize ─────────────────────────────────────────────────────────────


fn word_tokenize(text: String) -> List[String]:
    """Split text on whitespace and punctuation, lowercase all tokens.

    Punctuation characters are removed. Empty tokens are discarded.
    """
    var b = text.as_bytes()
    var n = len(b)
    if n == 0:
        return List[String]()
    var tokens = List[String](capacity=n)
    var current = String("")

    for i in range(n):
        var c = Int(b[i])
        if _is_whitespace(c):
            if len(current) > 0:
                tokens.append(current^)
                current = String("")
        elif _is_punct(c):
            if len(current) > 0:
                tokens.append(current^)
                current = String("")
        else:
            current += chr(_to_lower(c))

    if len(current) > 0:
        tokens.append(current^)

    return tokens^


# ── Sentence Tokenize ─────────────────────────────────────────────────────────


fn sentence_tokenize(text: String) -> List[String]:
    """Split text into sentences on .!? followed by space or end.

    Trims whitespace from each sentence. Empty sentences are discarded.
    """
    var b = text.as_bytes()
    var n = len(b)
    var sentences = List[String](capacity=n)
    var start = 0

    for i in range(n):
        var c = Int(b[i])
        if c == ord(".") or c == ord("!") or c == ord("?"):
            var is_boundary = False
            if i == n - 1:
                is_boundary = True
            elif _is_whitespace(Int(b[i + 1])):
                is_boundary = True

            if is_boundary:
                # Trim leading whitespace
                var s_start = start
                while s_start <= i and _is_whitespace(Int(b[s_start])):
                    s_start += 1
                if s_start <= i:
                    sentences.append(_substr(text, s_start, i + 1))
                start = i + 1

    # Remaining text after last sentence boundary
    if start < n:
        var s_start = start
        var s_end = n
        while s_start < s_end and _is_whitespace(Int(b[s_start])):
            s_start += 1
        while s_end > s_start and _is_whitespace(Int(b[s_end - 1])):
            s_end -= 1
        if s_start < s_end:
            sentences.append(_substr(text, s_start, s_end))

    return sentences^


# ── Character N-grams ─────────────────────────────────────────────────────────


fn char_ngrams(text: String, n: Int) -> List[String]:
    """Generate character-level n-grams from text."""
    var length = len(text)
    if n <= 0 or length < n:
        return List[String]()
    var result = List[String](capacity=length - n + 1)
    for i in range(length - n + 1):
        result.append(_substr(text, i, i + n))
    return result^


# ── Word N-grams ──────────────────────────────────────────────────────────────


fn word_ngrams(tokens: List[String], n: Int) -> List[String]:
    """Generate word-level n-grams joined with '_'."""
    var length = len(tokens)
    if n <= 0 or length < n:
        return List[String]()
    if length == n:
        var result = List[String](capacity=1)
        if n == 1:
            result.append(tokens[0])
            return result^
        if n == 2:
            result.append(tokens[0] + "_" + tokens[1])
            return result^
        if n == 3:
            result.append(tokens[0] + "_" + tokens[1] + "_" + tokens[2])
            return result^
        if n == 4:
            result.append(tokens[0] + "_" + tokens[1] + "_" + tokens[2] + "_" + tokens[3])
            return result^
        if n == 5:
            result.append(
                tokens[0]
                + "_"
                + tokens[1]
                + "_"
                + tokens[2]
                + "_"
                + tokens[3]
                + "_"
                + tokens[4]
            )
            return result^
        var gram = tokens[0]
        for j in range(1, n):
            gram += "_" + tokens[j]
        result.append(gram)
        return result^
    var result = List[String](capacity=length - n + 1)
    for i in range(length - n + 1):
        var gram = tokens[i]
        for j in range(1, n):
            gram += "_" + tokens[i + j]
        result.append(gram^)
    return result^


# ── Remove Stopwords ──────────────────────────────────────────────────────────


fn remove_stopwords(tokens: List[String]) -> List[String]:
    """Remove common English stopwords from token list."""
    var n = len(tokens)
    var result = List[String](capacity=n)
    for i in range(n):
        if not is_stopword(tokens[i]):
            result.append(tokens[i])
    return result^


# ── Simple Stemmer ────────────────────────────────────────────────────────────


fn stem_simple(word: String) -> String:
    """Very simple suffix stemmer.

    Removes trailing 'ing', 'ed', 'ly', 's' if word length > 4.
    Only removes one suffix per call. Priority: ing > ed > ly > s.
    """
    var b = word.as_bytes()
    var n = len(b)

    # Only stem words with at least 4 characters
    if n < 4:
        return word

    # Try "ing" (3 chars) — need at least 1 char remaining
    if n > 3:
        if (
            Int(b[n - 3]) == ord("i")
            and Int(b[n - 2]) == ord("n")
            and Int(b[n - 1]) == ord("g")
        ):
            return _substr(word, 0, n - 3)

    # Try "ed" (2 chars)
    if n > 2:
        if Int(b[n - 2]) == ord("e") and Int(b[n - 1]) == ord("d"):
            return _substr(word, 0, n - 2)

    # Try "ly" (2 chars)
    if n > 2:
        if Int(b[n - 2]) == ord("l") and Int(b[n - 1]) == ord("y"):
            return _substr(word, 0, n - 2)

    # Try "s" (1 char) — not "ss"
    if n > 1:
        if Int(b[n - 1]) == ord("s") and Int(b[n - 2]) != ord("s"):
            return _substr(word, 0, n - 1)

    return word


# ── Vocabulary Size ───────────────────────────────────────────────────────────


fn vocabulary_size(tokens: List[String]) -> Int:
    """Count unique tokens in the list (O(n²) simple approach)."""
    var n = len(tokens)
    var count = 0
    for i in range(n):
        var seen = False
        for j in range(i):
            if tokens[j] == tokens[i]:
                seen = True
                break
        if not seen:
            count += 1
    return count


# ── Token Frequency ───────────────────────────────────────────────────────────


fn token_frequency(tokens: List[String]) -> List[List[String]]:
    """Compute token frequencies as [[token, count_str], ...] sorted desc.

    O(n²) approach suitable for moderate-sized token lists.
    """
    var n_tokens = len(tokens)
    if n_tokens == 0:
        return List[List[String]]()

    if _all_unique(tokens):
        var unique_result = List[List[String]](capacity=n_tokens)
        for i in range(n_tokens):
            var pair = List[String](capacity=2)
            pair.append(tokens[i])
            pair.append("1")
            unique_result.append(pair^)
        return unique_result^

    var unique = List[String](capacity=n_tokens)
    var counts = List[Int](capacity=n_tokens)
    for i in range(n_tokens):
        var found = False
        for j in range(len(unique)):
            if unique[j] == tokens[i]:
                counts[j] = counts[j] + 1
                found = True
                break
        if not found:
            unique.append(tokens[i])
            counts.append(1)

    # Stable insertion sort by count descending.
    var nu = len(unique)
    for i in range(1, nu):
        var key_count = counts[i]
        var key_token = unique[i]
        var j = i - 1
        while j >= 0 and counts[j] < key_count:
            counts[j + 1] = counts[j]
            unique[j + 1] = unique[j]
            j -= 1
        counts[j + 1] = key_count
        unique[j + 1] = key_token

    var result = List[List[String]](capacity=nu)
    for i in range(nu):
        var pair = List[String](capacity=2)
        pair.append(unique[i])
        pair.append(String(counts[i]))
        result.append(pair^)
    return result^


# ── Pad Sequence ──────────────────────────────────────────────────────────────


fn pad_sequence(
    tokens: List[String], max_len: Int, pad_token: String
) -> List[String]:
    """Pad or truncate token list to fixed length.

    If tokens shorter than max_len, pad on right.
    If tokens longer, truncate to max_len.
    """
    if max_len <= 0:
        return List[String]()

    var n = len(tokens)
    var result = List[String](capacity=max_len)
    var copy_len = n
    if copy_len > max_len:
        copy_len = max_len
    for i in range(copy_len):
        result.append(tokens[i])
    for _ in range(copy_len, max_len):
        result.append(pad_token)
    return result^
