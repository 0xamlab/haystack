"""Tests for Wave 53 — Network Protocols, Naive Bayes, Advanced Tokenizer."""

from network_protocol import (
    http_status_text,
    is_success,
    is_redirect,
    is_client_error,
    is_server_error,
    mime_type,
    parse_content_type,
    is_json_type,
    is_text_type,
    build_query_string,
    parse_query_string,
)
from ml.naive_bayes import (
    gaussian_nb_fit,
    gaussian_nb_predict,
    gaussian_nb_predict_batch,
    compute_priors,
    gaussian_log_likelihood,
    accuracy,
    confusion_matrix,
    precision_recall,
)
from text.tokenizer import (
    word_tokenize,
    sentence_tokenize,
    char_ngrams,
    word_ngrams,
    remove_stopwords,
    stem_simple,
    vocabulary_size,
    token_frequency,
    pad_sequence,
    is_stopword,
)
from std.math import abs as fabs


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error(
            "FAIL: " + msg + " | got " + String(a) + " expected " + String(b)
        )


# ── Network Protocol Tests ───────────────────────────────────────────────────


def test_http_status_text() raises:
    print("  http_status_text...")
    _assert(http_status_text(200) == "OK", "200→OK")                        # 1
    _assert(http_status_text(201) == "Created", "201→Created")              # 2
    _assert(http_status_text(204) == "No Content", "204→No Content")        # 3
    _assert(http_status_text(301) == "Moved Permanently", "301")            # 4
    _assert(http_status_text(400) == "Bad Request", "400→Bad Request")      # 5
    _assert(http_status_text(404) == "Not Found", "404→Not Found")          # 6
    _assert(
        http_status_text(500) == "Internal Server Error", "500→ISE"
    )                                                                       # 7
    _assert(http_status_text(503) == "Service Unavailable", "503")          # 8
    _assert(http_status_text(429) == "Too Many Requests", "429")            # 9
    _assert(http_status_text(999) == "Unknown", "999→Unknown")              # 10


def test_status_classification() raises:
    print("  is_success/redirect/client_error/server_error...")
    _assert(is_success(200), "200 is success")                              # 11
    _assert(is_success(299), "299 is success")                              # 12
    _assert(not is_success(404), "404 not success")                         # 13
    _assert(is_redirect(301), "301 is redirect")                            # 14
    _assert(is_redirect(302), "302 is redirect")                            # 15
    _assert(not is_redirect(200), "200 not redirect")                       # 16
    _assert(is_client_error(400), "400 is client error")                    # 17
    _assert(is_client_error(404), "404 is client error")                    # 18
    _assert(not is_client_error(500), "500 not client error")               # 19
    _assert(is_server_error(500), "500 is server error")                    # 20
    _assert(is_server_error(503), "503 is server error")                    # 21
    _assert(not is_server_error(200), "200 not server error")               # 22


def test_mime_types() raises:
    print("  mime_type...")
    _assert(mime_type("json") == "application/json", "json mime")           # 23
    _assert(mime_type("html") == "text/html", "html mime")                  # 24
    _assert(mime_type("csv") == "text/csv", "csv mime")                     # 25
    _assert(mime_type("png") == "image/png", "png mime")                    # 26
    _assert(mime_type("pdf") == "application/pdf", "pdf mime")              # 27
    _assert(mime_type("xyz") == "application/octet-stream", "unknown")      # 28


def test_content_type_parsing() raises:
    print("  parse_content_type / is_json / is_text...")
    _assert(
        parse_content_type("text/html; charset=utf-8") == "text/html",
        "parse ct with charset",
    )                                                                       # 29
    _assert(
        parse_content_type("application/json") == "application/json",
        "parse ct no params",
    )                                                                       # 30
    _assert(is_json_type("application/json"), "json type true")             # 31
    _assert(is_json_type("application/vnd.api+json"), "+json suffix")       # 32
    _assert(not is_json_type("text/html"), "html not json")                 # 33
    _assert(is_text_type("text/html"), "text/html is text")                 # 34
    _assert(is_text_type("text/csv"), "text/csv is text")                   # 35
    _assert(not is_text_type("image/png"), "image not text")                # 36


def test_query_string() raises:
    print("  build_query_string / parse_query_string...")
    var keys = List[String]()
    keys.append("a")
    keys.append("b")
    var vals = List[String]()
    vals.append("1")
    vals.append("2")
    _assert(build_query_string(keys, vals) == "a=1&b=2", "build qs")       # 37

    var parsed = parse_query_string("a=1&b=2")
    _assert(len(parsed) == 2, "parse qs 2 pairs")                          # 38
    _assert(parsed[0][0] == "a", "first key a")                            # 39
    _assert(parsed[0][1] == "1", "first val 1")                            # 40
    _assert(parsed[1][0] == "b", "second key b")                           # 41
    _assert(parsed[1][1] == "2", "second val 2")                           # 42

    var keys3 = List[String]()
    keys3.append("x")
    var vals3 = List[String]()
    vals3.append("hello")
    _assert(build_query_string(keys3, vals3) == "x=hello", "single pair")  # 43


# ── Naive Bayes Tests ─────────────────────────────────────────────────────────


def test_compute_priors() raises:
    print("  compute_priors...")
    var y = List[Int]()
    y.append(0)
    y.append(0)
    y.append(1)
    y.append(1)
    var priors = compute_priors(y, 2)
    _assert_close(priors[0], 0.5, 1e-12, "prior class 0 = 0.5")           # 44
    _assert_close(priors[1], 0.5, 1e-12, "prior class 1 = 0.5")           # 45

    var y2 = List[Int]()
    y2.append(0)
    y2.append(0)
    y2.append(0)
    y2.append(1)
    var priors2 = compute_priors(y2, 2)
    _assert_close(priors2[0], 0.75, 1e-12, "prior 0 = 0.75")              # 46
    _assert_close(priors2[1], 0.25, 1e-12, "prior 1 = 0.25")              # 47


def test_gaussian_log_likelihood() raises:
    print("  gaussian_log_likelihood...")
    var ll = gaussian_log_likelihood(0.0, 0.0, 1.0)
    _assert(ll > -10.0 and ll < 0.0, "log-lik finite and negative")       # 48
    # At mean, likelihood is maximized
    var ll_at_mean = gaussian_log_likelihood(5.0, 5.0, 1.0)
    var ll_away = gaussian_log_likelihood(10.0, 5.0, 1.0)
    _assert(ll_at_mean > ll_away, "log-lik higher at mean")               # 49


def test_nb_fit_predict() raises:
    print("  gaussian_nb_fit / predict...")
    # Simple 2-class, 2-feature dataset
    var X = List[List[Float64]]()
    # Class 0: features around (1, 1)
    var r0a = List[Float64]()
    r0a.append(1.0)
    r0a.append(1.0)
    X.append(r0a^)
    var r0b = List[Float64]()
    r0b.append(1.2)
    r0b.append(0.8)
    X.append(r0b^)
    var r0c = List[Float64]()
    r0c.append(0.9)
    r0c.append(1.1)
    X.append(r0c^)
    var r0d = List[Float64]()
    r0d.append(1.1)
    r0d.append(0.9)
    X.append(r0d^)
    # Class 1: features around (5, 5)
    var r1a = List[Float64]()
    r1a.append(5.0)
    r1a.append(5.0)
    X.append(r1a^)
    var r1b = List[Float64]()
    r1b.append(5.2)
    r1b.append(4.8)
    X.append(r1b^)
    var r1c = List[Float64]()
    r1c.append(4.9)
    r1c.append(5.1)
    X.append(r1c^)
    var r1d = List[Float64]()
    r1d.append(5.1)
    r1d.append(4.9)
    X.append(r1d^)

    var y = List[Int]()
    y.append(0)
    y.append(0)
    y.append(0)
    y.append(0)
    y.append(1)
    y.append(1)
    y.append(1)
    y.append(1)

    var params = gaussian_nb_fit(X, y, 2)
    _assert(len(params) == 2, "2 classes in params")                       # 50
    _assert(len(params[0]) == 4, "2 features * 2 (mean,std) = 4")         # 51

    var priors = compute_priors(y, 2)

    # Predict a point near class 0
    var test0 = List[Float64]()
    test0.append(1.0)
    test0.append(1.0)
    _assert(
        gaussian_nb_predict(params, priors, test0) == 0,
        "predict (1,1) → class 0",
    )                                                                       # 52

    # Predict a point near class 1
    var test1 = List[Float64]()
    test1.append(5.0)
    test1.append(5.0)
    _assert(
        gaussian_nb_predict(params, priors, test1) == 1,
        "predict (5,5) → class 1",
    )                                                                       # 53

    # Batch predict on training data
    var preds = gaussian_nb_predict_batch(params, priors, X)
    _assert(len(preds) == 8, "batch predict 8 samples")                    # 54
    var acc = accuracy(preds, y)
    _assert(acc >= 0.75, "training accuracy >= 75%")                       # 55


def test_accuracy_fn() raises:
    print("  accuracy...")
    var p = List[Int]()
    p.append(1)
    p.append(1)
    p.append(0)
    p.append(0)
    var a = List[Int]()
    a.append(1)
    a.append(1)
    a.append(0)
    a.append(1)
    _assert_close(accuracy(p, a), 0.75, 1e-12, "accuracy 0.75")           # 56


def test_confusion_matrix() raises:
    print("  confusion_matrix...")
    var p = List[Int]()
    p.append(0)
    p.append(0)
    p.append(1)
    p.append(1)
    var a = List[Int]()
    a.append(0)
    a.append(1)
    a.append(0)
    a.append(1)
    var cm = confusion_matrix(p, a, 2)
    _assert(len(cm) == 2, "cm 2 rows")                                    # 57
    _assert(len(cm[0]) == 2, "cm 2 cols")                                 # 58
    # Sum should be 4
    var total = cm[0][0] + cm[0][1] + cm[1][0] + cm[1][1]
    _assert(total == 4, "cm sums to n_samples")                           # 59
    _assert(cm[0][0] == 1, "TN=1")                                        # 60
    _assert(cm[1][1] == 1, "TP=1")                                        # 61


def test_precision_recall() raises:
    print("  precision_recall...")
    var p = List[Int]()
    p.append(1)
    p.append(1)
    p.append(0)
    p.append(0)
    var a = List[Int]()
    a.append(1)
    a.append(0)
    a.append(0)
    a.append(1)
    var pr = precision_recall(p, a, 1)
    _assert(len(pr) == 3, "pr has 3 elements")                            # 62
    _assert(pr[0] >= 0.0 and pr[0] <= 1.0, "precision in [0,1]")          # 63
    _assert(pr[1] >= 0.0 and pr[1] <= 1.0, "recall in [0,1]")            # 64
    _assert(pr[2] >= 0.0 and pr[2] <= 1.0, "f1 in [0,1]")                # 65
    _assert_close(pr[0], 0.5, 1e-12, "precision=0.5 (1TP/2pred)")        # 66
    _assert_close(pr[1], 0.5, 1e-12, "recall=0.5 (1TP/2actual)")         # 67


# ── Tokenizer Tests ───────────────────────────────────────────────────────────


def test_word_tokenize() raises:
    print("  word_tokenize...")
    var tokens = word_tokenize("Hello, world!")
    _assert(len(tokens) == 2, "2 word tokens")                            # 68
    _assert(tokens[0] == "hello", "lowercase hello")                      # 69
    _assert(tokens[1] == "world", "lowercase world")                      # 70

    var tokens2 = word_tokenize("  foo  bar  baz  ")
    _assert(len(tokens2) == 3, "3 tokens with extra spaces")              # 71

    var tokens3 = word_tokenize("test")
    _assert(len(tokens3) == 1, "single plain token stays single")         # 71b
    _assert(tokens3[0] == "test", "plain token remains unchanged")        # 71c


def test_sentence_tokenize() raises:
    print("  sentence_tokenize...")
    var sents = sentence_tokenize("Hello. World!")
    _assert(len(sents) == 2, "2 sentences")                               # 72
    _assert(sents[0] == "Hello.", "first sentence")                       # 73
    _assert(sents[1] == "World!", "second sentence")                      # 74

    var sents2 = sentence_tokenize("One? Two. Three!")
    _assert(len(sents2) == 3, "3 sentences")                              # 75


def test_char_ngrams() raises:
    print("  char_ngrams...")
    var ng = char_ngrams("abc", 2)
    _assert(len(ng) == 2, "2 bigrams from abc")                           # 76
    _assert(ng[0] == "ab", "first bigram ab")                             # 77
    _assert(ng[1] == "bc", "second bigram bc")                            # 78

    var ng3 = char_ngrams("hello", 3)
    _assert(len(ng3) == 3, "3 trigrams from hello")                       # 79


def test_word_ngrams() raises:
    print("  word_ngrams...")
    var toks = List[String]()
    toks.append("a")
    toks.append("b")
    toks.append("c")
    var wn = word_ngrams(toks, 2)
    _assert(len(wn) == 2, "2 bigrams")                                    # 80
    _assert(wn[0] == "a_b", "first word bigram")                          # 81
    _assert(wn[1] == "b_c", "second word bigram")                         # 82

    var wn_exact = word_ngrams(toks, 3)
    _assert(len(wn_exact) == 1, "exact-length ngram yields one gram")     # 82b
    _assert(wn_exact[0] == "a_b_c", "exact-length gram joined once")      # 82c


def test_stopwords() raises:
    print("  remove_stopwords / is_stopword...")
    var toks = List[String]()
    toks.append("the")
    toks.append("cat")
    toks.append("is")
    toks.append("big")
    var filtered = remove_stopwords(toks)
    _assert(len(filtered) == 2, "2 tokens after stopword removal")        # 83
    _assert(filtered[0] == "cat", "cat remains")                          # 84
    _assert(filtered[1] == "big", "big remains")                          # 85
    _assert(is_stopword("the"), "the is stopword")                        # 86
    _assert(is_stopword("is"), "is is stopword")                          # 87
    _assert(not is_stopword("algorithm"), "algorithm not stopword")        # 88
    _assert(not is_stopword("cat"), "cat not stopword")                    # 89


def test_stem_simple() raises:
    print("  stem_simple...")
    _assert(stem_simple("running") == "runn", "running→runn")             # 90
    _assert(stem_simple("walked") == "walk", "walked→walk")               # 91
    _assert(stem_simple("quickly") == "quick", "quickly→quick")           # 92
    _assert(stem_simple("cats") == "cat", "cats→cat")                     # 93
    _assert(stem_simple("hi") == "hi", "short word unchanged")            # 94


def test_vocabulary_size() raises:
    print("  vocabulary_size...")
    var toks = List[String]()
    toks.append("a")
    toks.append("b")
    toks.append("a")
    toks.append("c")
    _assert(vocabulary_size(toks) == 3, "3 unique tokens")                 # 95


def test_token_frequency() raises:
    print("  token_frequency...")
    var toks = List[String]()
    toks.append("a")
    toks.append("b")
    toks.append("a")
    toks.append("c")
    toks.append("a")
    var freq = token_frequency(toks)
    _assert(len(freq) == 3, "3 unique tokens in freq")                    # 96
    _assert(freq[0][0] == "a", "most frequent is 'a'")                    # 97
    _assert(freq[0][1] == "3", "a count is 3")                            # 98

    var toks2 = List[String]()
    toks2.append("b")
    toks2.append("a")
    toks2.append("c")
    var freq2 = token_frequency(toks2)
    _assert(freq2[0][0] == "b", "stable tie order keeps first token")     # 98b
    _assert(freq2[1][0] == "a", "stable tie order keeps second token")    # 98c
    _assert(freq2[2][0] == "c", "stable tie order keeps third token")     # 98d


def test_pad_sequence() raises:
    print("  pad_sequence...")
    var toks = List[String]()
    toks.append("a")
    toks.append("b")
    var padded = pad_sequence(toks, 4, "<pad>")
    _assert(len(padded) == 4, "padded to length 4")                       # 99
    _assert(padded[0] == "a", "padded[0] == a")                           # 100
    _assert(padded[2] == "<pad>", "padded[2] == <pad>")                   # 101
    _assert(padded[3] == "<pad>", "padded[3] == <pad>")                   # 102

    var long_toks = List[String]()
    long_toks.append("a")
    long_toks.append("b")
    long_toks.append("c")
    var truncated = pad_sequence(long_toks, 2, "<pad>")
    _assert(len(truncated) == 2, "truncated to length 2")
    _assert(truncated[0] == "a", "truncated[0] == a")
    _assert(truncated[1] == "b", "truncated[1] == b")

    var exact = pad_sequence(long_toks, 3, "<pad>")
    _assert(len(exact) == 3, "exact length remains length 3")
    _assert(exact[0] == "a", "exact[0] == a")
    _assert(exact[2] == "c", "exact[2] == c")

    # Truncation
    var toks2 = List[String]()
    toks2.append("x")
    toks2.append("y")
    toks2.append("z")
    var trunc = pad_sequence(toks2, 2, "<pad>")
    _assert(len(trunc) == 2, "truncated to 2")                            # 103


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 53 Tests ===")

    # Network Protocol
    print("Network Protocol:")
    test_http_status_text()
    test_status_classification()
    test_mime_types()
    test_content_type_parsing()
    test_query_string()

    # Naive Bayes
    print("Naive Bayes:")
    test_compute_priors()
    test_gaussian_log_likelihood()
    test_nb_fit_predict()
    test_accuracy_fn()
    test_confusion_matrix()
    test_precision_recall()

    # Tokenizer
    print("Tokenizer:")
    test_word_tokenize()
    test_sentence_tokenize()
    test_char_ngrams()
    test_word_ngrams()
    test_stopwords()
    test_stem_simple()
    test_vocabulary_size()
    test_token_frequency()
    test_pad_sequence()

    print("All 103 assertions passed! ✓")
