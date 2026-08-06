"""Tests for Wave 25 — Bayesian Inference, AES S-Box, NLP Utilities."""

from bayesian import (
    beta_posterior,
    beta_mean,
    beta_variance,
    beta_credible_interval,
    normal_posterior,
    poisson_posterior,
    bayes_factor,
    posterior_predictive_beta,
    hpd_interval_normal,
    bayesian_ab_test,
)
from crypto.aes_sbox import (
    aes_sbox,
    aes_inv_sbox,
    sub_bytes,
    inv_sub_bytes,
    shift_rows,
    inv_shift_rows,
    xor_bytes,
    add_round_key,
)
from nlp import (
    tokenize,
    ngrams,
    term_frequency,
    tf,
    idf,
    tfidf,
    cosine_similarity_vec,
    jaccard_similarity,
    word_count,
    char_count,
    unique_tokens,
)
from std.math import abs as fabs


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


def _assert_eq(a: Int, b: Int, msg: String) raises:
    if a != b:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_state() -> List[Int]:
    """Create a 16-byte test state: 0x00..0x0F."""
    var s = List[Int]()
    for i in range(16):
        s.append(i)
    return s^


def _f2(a: Float64, b: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a)
    r.append(b)
    return r^


def _s_list2(a: String, b: String) -> List[String]:
    var r = List[String]()
    r.append(a)
    r.append(b)
    return r^


def _s_list3(a: String, b: String, c: String) -> List[String]:
    var r = List[String]()
    r.append(a)
    r.append(b)
    r.append(c)
    return r^


def _int3(a: Int, b: Int, c: Int) -> List[Int]:
    var r = List[Int]()
    r.append(a)
    r.append(b)
    r.append(c)
    return r^


# ── Bayesian Tests ───────────────────────────────────────────────────────────


def test_bayesian() raises:
    print("── Bayesian tests ──")

    # 1. beta_posterior(1,1, 7,3) → [8, 4]
    var bp = beta_posterior(1.0, 1.0, 7, 3)
    _assert_close(bp[0], 8.0, 1e-10, "beta_posterior alpha")
    _assert_close(bp[1], 4.0, 1e-10, "beta_posterior beta")

    # 2. beta_mean(8,4) ≈ 0.667
    var bm = beta_mean(8.0, 4.0)
    _assert_close(bm, 0.6666666666666666, 0.01, "beta_mean(8,4)")

    # 3. beta_variance > 0
    var bv = beta_variance(8.0, 4.0)
    _assert(bv > 0.0, "beta_variance > 0")

    # 4. beta_variance correctness: 8*4 / (12^2 * 13) = 32/1872
    _assert_close(bv, 32.0 / 1872.0, 1e-10, "beta_variance value")

    # 5. beta_credible_interval: lower < mean < upper
    var ci = beta_credible_interval(8.0, 4.0)
    _assert(ci[0] < bm, "beta_ci lower < mean")
    _assert(bm < ci[1], "beta_ci mean < upper")

    # 6. beta_credible_interval bounds in [0,1]
    _assert(ci[0] >= 0.0, "beta_ci lower >= 0")
    _assert(ci[1] <= 1.0, "beta_ci upper <= 1")

    # 7. normal_posterior — posterior mean between prior and data mean
    var np_ = normal_posterior(0.0, 1.0, 5.0, 2.0, 10)
    _assert(np_[0] > 0.0, "normal_post mean > prior")
    _assert(np_[0] < 5.0, "normal_post mean < data")

    # 8. normal_posterior — posterior variance < min(prior_var, data_var/n)
    var min_var = 1.0
    var data_var_over_n = 2.0 / 10.0
    if data_var_over_n < min_var:
        min_var = data_var_over_n
    _assert(np_[1] < min_var, "normal_post var < min(prior_var, data_var/n)")

    # 9. poisson_posterior(1,1, 10,5) → [11, 6]
    var pp = poisson_posterior(1.0, 1.0, 10, 5)
    _assert_close(pp[0], 11.0, 1e-10, "poisson_posterior alpha")
    _assert_close(pp[1], 6.0, 1e-10, "poisson_posterior beta")

    # 10. bayes_factor(0.8, 0.2) == 4.0
    var bf = bayes_factor(0.8, 0.2)
    _assert_close(bf, 4.0, 1e-10, "bayes_factor(0.8,0.2)")

    # 11. posterior_predictive_beta(8,4) ≈ 0.667
    var ppb = posterior_predictive_beta(8.0, 4.0)
    _assert_close(ppb, 0.6666666666666666, 0.01, "posterior_predictive_beta")

    # 12. hpd_interval_normal(0,1,0.95) ≈ [-1.96, 1.96]
    var hpd = hpd_interval_normal(0.0, 1.0, 0.95)
    _assert_close(hpd[0], -1.96, 0.05, "hpd lower ≈ -1.96")
    _assert_close(hpd[1], 1.96, 0.05, "hpd upper ≈ 1.96")

    # 13. hpd symmetry around mean
    _assert_close(hpd[0] + hpd[1], 0.0, 0.01, "hpd symmetric around 0")

    # 14. bayesian_ab_test with clearly better B → P > 0.5
    var p_b_better = bayesian_ab_test(10, 100, 50, 100, 5000)
    _assert(p_b_better > 0.5, "bayesian_ab_test B clearly better → P > 0.5")

    # 15. bayesian_ab_test result in [0, 1]
    _assert(p_b_better >= 0.0 and p_b_better <= 1.0, "ab_test result in [0,1]")

    print("  ✓ 15 Bayesian assertions passed")


# ── AES S-Box Tests ──────────────────────────────────────────────────────────


def test_aes_sbox() raises:
    print("── AES S-Box tests ──")

    # 16. aes_sbox(0x00) == 0x63
    _assert_eq(aes_sbox(0x00), 0x63, "sbox(0x00)==0x63")

    # 17. aes_sbox(0x53) == 0xED
    _assert_eq(aes_sbox(0x53), 0xED, "sbox(0x53)==0xED")

    # 18. aes_sbox(0xFF) == 0x16
    _assert_eq(aes_sbox(0xFF), 0x16, "sbox(0xFF)==0x16")

    # 19. inv_sbox roundtrip: inv(sbox(0x00)) == 0x00
    _assert_eq(aes_inv_sbox(aes_sbox(0x00)), 0x00, "roundtrip 0x00")

    # 20. inv_sbox roundtrip: inv(sbox(0x53)) == 0x53
    _assert_eq(aes_inv_sbox(aes_sbox(0x53)), 0x53, "roundtrip 0x53")

    # 21. inv_sbox roundtrip: inv(sbox(0xAB)) == 0xAB
    _assert_eq(aes_inv_sbox(aes_sbox(0xAB)), 0xAB, "roundtrip 0xAB")

    # 22. inv_sbox roundtrip: inv(sbox(0xFF)) == 0xFF
    _assert_eq(aes_inv_sbox(aes_sbox(0xFF)), 0xFF, "roundtrip 0xFF")

    # 23-24. sub_bytes then inv_sub_bytes == identity
    var state = _make_state()
    var sb = sub_bytes(state)
    var isb = inv_sub_bytes(sb)
    var identity_ok = True
    for i in range(16):
        if isb[i] != state[i]:
            identity_ok = False
            break
    _assert(identity_ok, "sub_bytes ∘ inv_sub_bytes == identity")

    # 24. sub_bytes output != input (bytes do change)
    var changed = False
    for i in range(16):
        if sb[i] != state[i]:
            changed = True
            break
    _assert(changed, "sub_bytes output != input")

    # 25-26. shift_rows then inv_shift_rows == identity
    var sr = shift_rows(state)
    var isr = inv_shift_rows(sr)
    var sr_identity = True
    for i in range(16):
        if isr[i] != state[i]:
            sr_identity = False
            break
    _assert(sr_identity, "shift_rows ∘ inv_shift_rows == identity")

    # 26. shift_rows actually changes the state
    var sr_changed = False
    for i in range(16):
        if sr[i] != state[i]:
            sr_changed = True
            break
    _assert(sr_changed, "shift_rows changes state")

    # 27. xor_bytes([1,2,3], [3,2,1]) == [2,0,2]
    var xa = _int3(1, 2, 3)
    var xb = _int3(3, 2, 1)
    var xr = xor_bytes(xa, xb)
    _assert_eq(xr[0], 2, "xor[0]==2")
    _assert_eq(xr[1], 0, "xor[1]==0")
    _assert_eq(xr[2], 2, "xor[2]==2")

    # 28-29. add_round_key double application == identity
    var key = List[Int]()
    for i in range(16):
        key.append(i * 17)  # some key bytes
    var ark1 = add_round_key(state, key)
    var ark2 = add_round_key(ark1, key)
    var ark_identity = True
    for i in range(16):
        if ark2[i] != state[i]:
            ark_identity = False
            break
    _assert(ark_identity, "add_round_key double == identity")

    # 29. first add_round_key actually changes state
    var ark_changed = False
    for i in range(16):
        if ark1[i] != state[i]:
            ark_changed = True
            break
    _assert(ark_changed, "add_round_key changes state")

    # 30. sbox(0x01) == 0x7C
    _assert_eq(aes_sbox(0x01), 0x7C, "sbox(0x01)==0x7C")

    print("  ✓ 15 AES S-Box assertions passed")


# ── NLP Tests ────────────────────────────────────────────────────────────────


def test_nlp() raises:
    print("── NLP tests ──")

    # 31. tokenize("Hello World!") → ["hello", "world"]
    var toks = tokenize("Hello World!")
    _assert_eq(len(toks), 2, "tokenize length")
    _assert(toks[0] == "hello", "tokenize[0]=='hello'")
    _assert(toks[1] == "world", "tokenize[1]=='world'")

    # 32. word_count("one two three") == 3
    _assert_eq(word_count("one two three"), 3, "word_count==3")

    # 33. char_count("ab cd") == 4
    _assert_eq(char_count("ab cd"), 4, "char_count==4")

    # 34. ngrams(["a","b","c"], 2) → ["a_b", "b_c"]
    var ng = ngrams(_s_list3("a", "b", "c"), 2)
    _assert_eq(len(ng), 2, "ngrams length")
    _assert(ng[0] == "a_b", "ngrams[0]=='a_b'")
    _assert(ng[1] == "b_c", "ngrams[1]=='b_c'")

    # 35. tf("the", ["the","cat","the"]) ≈ 0.667
    var tf_val = tf("the", _s_list3("the", "cat", "the"))
    _assert_close(tf_val, 0.6666666666666666, 0.01, "tf('the')")

    # 36-37. idf on known corpus — rare term has higher IDF
    var doc1 = _s_list3("the", "cat", "sat")
    var doc2 = _s_list3("the", "dog", "ran")
    var doc3 = _s_list3("the", "bird", "flew")
    var corpus = List[List[String]]()
    corpus.append(doc1.copy())
    corpus.append(doc2.copy())
    corpus.append(doc3.copy())
    var idf_the = idf("the", corpus)   # in all 3 docs
    var idf_cat = idf("cat", corpus)   # in 1 doc
    _assert(idf_cat > idf_the, "rare term 'cat' has higher IDF than 'the'")

    # 37. idf("the") for 3 docs all containing it: log(3/4) < 0
    _assert(idf_the < idf_cat, "idf_the < idf_cat")

    # 38. tfidf > 0 for term present in doc
    var tfidf_val = tfidf("cat", doc1, corpus)
    _assert(tfidf_val > 0.0, "tfidf > 0 for present term")

    # 39. cosine_similarity_vec([1,0], [1,0]) ≈ 1.0
    var cos_same = cosine_similarity_vec(_f2(1.0, 0.0), _f2(1.0, 0.0))
    _assert_close(cos_same, 1.0, 0.001, "cosine([1,0],[1,0])≈1")

    # 40. cosine_similarity_vec([1,0], [0,1]) ≈ 0.0
    var cos_orth = cosine_similarity_vec(_f2(1.0, 0.0), _f2(0.0, 1.0))
    _assert_close(cos_orth, 0.0, 0.001, "cosine([1,0],[0,1])≈0")

    # 41. jaccard_similarity(["a","b"], ["b","c"]) ≈ 0.333
    var jacc = jaccard_similarity(_s_list2("a", "b"), _s_list2("b", "c"))
    _assert_close(jacc, 0.3333333333333333, 0.01, "jaccard≈0.333")

    # 42. unique_tokens — no duplicates
    var dup_toks = List[String]()
    dup_toks.append("a"); dup_toks.append("b"); dup_toks.append("a"); dup_toks.append("c")
    var uniq = unique_tokens(dup_toks)
    _assert_eq(len(uniq), 3, "unique_tokens length==3")
    _assert(uniq[0] == "a", "unique[0]=='a'")
    _assert(uniq[1] == "b", "unique[1]=='b'")
    _assert(uniq[2] == "c", "unique[2]=='c'")

    # 43. term_frequency returns sorted pairs
    var tf_pairs = term_frequency(_s_list3("the", "cat", "the"))
    _assert(tf_pairs[0][0] == "the", "term_freq first is 'the'")
    _assert(tf_pairs[0][1] == "2", "term_freq 'the' count==2")

    # 44. word_count empty string
    _assert_eq(word_count(""), 0, "word_count('')==0")

    # 45. tokenize strips punctuation
    var toks2 = tokenize("hello, world. test!")
    _assert_eq(len(toks2), 3, "tokenize punctuation strips")
    _assert(toks2[0] == "hello", "tokenize punct[0]")
    _assert(toks2[1] == "world", "tokenize punct[1]")
    _assert(toks2[2] == "test", "tokenize punct[2]")

    # 46. ngrams with n=1 returns individual tokens
    var ng1 = ngrams(_s_list2("x", "y"), 1)
    _assert_eq(len(ng1), 2, "unigrams length")
    _assert(ng1[0] == "x", "unigram[0]")

    # 47. cosine_similarity_vec with parallel vectors
    var cos_par = cosine_similarity_vec(_f2(3.0, 4.0), _f2(6.0, 8.0))
    _assert_close(cos_par, 1.0, 0.001, "cosine parallel≈1")

    print("  ✓ 17 NLP assertions passed")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 25 Tests ===")
    test_bayesian()
    test_aes_sbox()
    test_nlp()
    print("=== All Wave 25 tests passed (47 assertions) ===")
