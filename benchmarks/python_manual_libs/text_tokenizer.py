"""Manual Python reference for text/tokenizer.mojo."""

from __future__ import annotations


def _is_punct(c: int) -> bool:
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


def _to_lower(c: int) -> int:
    if c >= ord("A") and c <= ord("Z"):
        return c + 32
    return c


def _is_whitespace(c: int) -> bool:
    return c == ord(" ") or c == ord("\t") or c == ord("\n") or c == ord("\r")


def _substr(s: str, start: int, end: int) -> str:
    return s.encode("utf-8")[start:end].decode("utf-8")


def is_stopword(word: str) -> bool:
    if word == "the" or word == "a" or word == "an" or word == "is":
        return True
    if word == "are" or word == "was" or word == "were" or word == "be":
        return True
    if word == "been" or word == "being" or word == "have" or word == "has":
        return True
    if word == "had" or word == "do" or word == "does" or word == "did":
        return True
    if word == "in" or word == "on" or word == "at" or word == "to":
        return True
    if word == "for" or word == "of" or word == "and" or word == "or":
        return True
    if word == "but" or word == "not" or word == "with" or word == "this":
        return True
    if word == "that" or word == "it" or word == "from" or word == "by":
        return True
    if word == "as" or word == "if" or word == "so":
        return True
    return False


def word_tokenize(text: str) -> list[str]:
    b = text.encode("utf-8")
    n = len(b)
    tokens: list[str] = []
    current = ""

    for i in range(n):
        c = int(b[i])
        if _is_whitespace(c) or _is_punct(c):
            if current:
                tokens.append(current)
                current = ""
        else:
            current += chr(_to_lower(c))

    if current:
        tokens.append(current)

    return tokens


def sentence_tokenize(text: str) -> list[str]:
    b = text.encode("utf-8")
    n = len(b)
    sentences: list[str] = []
    start = 0

    for i in range(n):
        c = int(b[i])
        if c == ord(".") or c == ord("!") or c == ord("?"):
            is_boundary = False
            if i == n - 1:
                is_boundary = True
            elif _is_whitespace(int(b[i + 1])):
                is_boundary = True

            if is_boundary:
                s_start = start
                while s_start <= i and _is_whitespace(int(b[s_start])):
                    s_start += 1
                if s_start <= i:
                    sentences.append(_substr(text, s_start, i + 1))
                start = i + 1

    if start < n:
        s_start = start
        s_end = n
        while s_start < s_end and _is_whitespace(int(b[s_start])):
            s_start += 1
        while s_end > s_start and _is_whitespace(int(b[s_end - 1])):
            s_end -= 1
        if s_start < s_end:
            sentences.append(_substr(text, s_start, s_end))

    return sentences


def char_ngrams(text: str, n: int) -> list[str]:
    length = len(text)
    if n <= 0 or length < n:
        return []
    result: list[str] = []
    for i in range(length - n + 1):
        result.append(_substr(text, i, i + n))
    return result


def word_ngrams(tokens: list[str], n: int) -> list[str]:
    length = len(tokens)
    if n <= 0 or length < n:
        return []
    result: list[str] = []
    for i in range(length - n + 1):
        gram = tokens[i]
        for j in range(1, n):
            gram += "_" + tokens[i + j]
        result.append(gram)
    return result


def remove_stopwords(tokens: list[str]) -> list[str]:
    result: list[str] = []
    for token in tokens:
        if not is_stopword(token):
            result.append(token)
    return result


def stem_simple(word: str) -> str:
    b = word.encode("utf-8")
    n = len(b)
    if n < 4:
        return word

    if (
        n > 3
        and int(b[n - 3]) == ord("i")
        and int(b[n - 2]) == ord("n")
        and int(b[n - 1]) == ord("g")
    ):
        return _substr(word, 0, n - 3)

    if n > 2 and int(b[n - 2]) == ord("e") and int(b[n - 1]) == ord("d"):
        return _substr(word, 0, n - 2)

    if n > 2 and int(b[n - 2]) == ord("l") and int(b[n - 1]) == ord("y"):
        return _substr(word, 0, n - 2)

    if n > 1 and int(b[n - 1]) == ord("s") and int(b[n - 2]) != ord("s"):
        return _substr(word, 0, n - 1)

    return word


def vocabulary_size(tokens: list[str]) -> int:
    unique: list[str] = []
    for token in tokens:
        found = False
        for item in unique:
            if item == token:
                found = True
                break
        if not found:
            unique.append(token)
    return len(unique)


def token_frequency(tokens: list[str]) -> list[list[str]]:
    unique: list[str] = []
    counts: list[int] = []
    for token in tokens:
        found = False
        for index, item in enumerate(unique):
            if item == token:
                counts[index] += 1
                found = True
                break
        if not found:
            unique.append(token)
            counts.append(1)

    for i in range(1, len(unique)):
        key_count = counts[i]
        key_token = unique[i]
        j = i - 1
        while j >= 0 and counts[j] < key_count:
            counts[j + 1] = counts[j]
            unique[j + 1] = unique[j]
            j -= 1
        counts[j + 1] = key_count
        unique[j + 1] = key_token

    result: list[list[str]] = []
    for index, token in enumerate(unique):
        result.append([token, str(counts[index])])
    return result


def pad_sequence(tokens: list[str], max_len: int, pad_token: str) -> list[str]:
    if max_len <= 0:
        return []

    result: list[str] = []
    n = len(tokens)
    for i in range(max_len):
        if i < n:
            result.append(tokens[i])
        else:
            result.append(pad_token)
    return result
