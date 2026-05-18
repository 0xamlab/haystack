"""
encoding.mojo — Data encoding utilities. Zero Python imports.

Replaces sklearn.preprocessing: LabelEncoder, OneHotEncoder, OrdinalEncoder,
and custom binary/frequency encoding utilities.

Public API:
  label_encode       — Map string labels to integers by first-appearance order
  label_decode       — Reverse of label_encode using a vocabulary
  one_hot_encode     — Convert integer labels to one-hot vectors
  ordinal_encode     — Encode based on a specified ordering
  binary_encode      — Encode integer as binary digits (MSB first)
  frequency_encode   — Encode each label with its frequency (count/total)
  build_vocabulary   — Extract unique labels in order of first appearance
"""


# ── build_vocabulary ──────────────────────────────────────────────────────────


fn build_vocabulary(labels: List[String]) -> List[String]:
    """Extract unique labels in order of first appearance."""
    var vocab = List[String]()
    for i in range(len(labels)):
        var found = False
        for j in range(len(vocab)):
            if vocab[j] == labels[i]:
                found = True
                break
        if not found:
            vocab.append(labels[i])
    return vocab^


# ── label_encode ──────────────────────────────────────────────────────────────


fn label_encode(labels: List[String]) -> List[Int]:
    """Map unique string labels to integers 0, 1, 2, ... in order of first
    appearance.

    Example: ["cat", "dog", "cat", "bird"] -> [0, 1, 0, 2]
    """
    var vocab = build_vocabulary(labels)
    var result = List[Int]()
    for i in range(len(labels)):
        for j in range(len(vocab)):
            if vocab[j] == labels[i]:
                result.append(j)
                break
    return result^


# ── label_decode ──────────────────────────────────────────────────────────────


fn label_decode(encoded: List[Int], vocabulary: List[String]) -> List[String]:
    """Reverse of label_encode using given vocabulary.

    Maps each integer index back to its string label.
    Out-of-range indices produce "?".
    """
    var result = List[String]()
    for i in range(len(encoded)):
        var idx = encoded[i]
        if idx >= 0 and idx < len(vocabulary):
            result.append(vocabulary[idx])
        else:
            result.append(String("?"))
    return result^


# ── one_hot_encode ────────────────────────────────────────────────────────────


fn one_hot_encode(labels: List[Int], n_classes: Int) -> List[List[Float64]]:
    """Convert integer labels to one-hot vectors.

    Each output is a List[Float64] of length n_classes with 1.0 at the label
    index and 0.0 elsewhere.
    """
    var result = List[List[Float64]]()
    for i in range(len(labels)):
        var row = List[Float64]()
        for j in range(n_classes):
            if j == labels[i]:
                row.append(1.0)
            else:
                row.append(0.0)
        result.append(row^)
    return result^


# ── ordinal_encode ────────────────────────────────────────────────────────────


fn ordinal_encode(data: List[String], order: List[String]) -> List[Int]:
    """Encode based on a specified ordering.

    Each element in data is mapped to its index in order.
    Items not found in order get -1.

    Example: data=["low","high","med"], order=["low","med","high"] -> [0, 2, 1]
    """
    var result = List[Int]()
    for i in range(len(data)):
        var found = False
        for j in range(len(order)):
            if order[j] == data[i]:
                result.append(j)
                found = True
                break
        if not found:
            result.append(-1)
    return result^


# ── binary_encode ─────────────────────────────────────────────────────────────


fn binary_encode(value: Int, n_bits: Int) -> List[Int]:
    """Encode integer as binary digits (MSB first).

    Example: binary_encode(5, 4) -> [0, 1, 0, 1]
    """
    var result = List[Int]()
    for _ in range(n_bits):
        result.append(0)

    var v = value
    for i in range(n_bits):
        var bit_pos = n_bits - 1 - i
        if v & (1 << bit_pos) != 0:
            result[i] = 1
    return result^


# ── frequency_encode ──────────────────────────────────────────────────────────


fn frequency_encode(labels: List[String]) -> List[Float64]:
    """Encode each label with its frequency (count/total) in the dataset.

    Example: ["a","a","b","a","b"] -> [0.6, 0.6, 0.4, 0.6, 0.4]
    """
    var n = len(labels)
    var result = List[Float64]()
    if n == 0:
        return result^

    var vocab = build_vocabulary(labels)
    var counts = List[Int]()
    for _ in range(len(vocab)):
        counts.append(0)

    for i in range(n):
        for j in range(len(vocab)):
            if vocab[j] == labels[i]:
                counts[j] = counts[j] + 1
                break

    var total = Float64(n)
    for i in range(n):
        for j in range(len(vocab)):
            if vocab[j] == labels[i]:
                result.append(Float64(counts[j]) / total)
                break

    return result^
