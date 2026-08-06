"""
huffman.mojo — Huffman coding compression. Zero Python imports.

Replaces dahuffman with pure Mojo implementations of frequency counting,
Huffman tree building, code generation, encoding, decoding, compression
ratio calculation, and average code length.

Public API:
  HuffmanNode              — Node struct (symbol, freq, left, right)
  frequency_count          — Count byte frequencies
  build_huffman_tree       — Build Huffman tree from frequencies
  generate_codes           — Generate code lengths from tree
  huffman_encode           — Encode data to bits
  huffman_decode           — Decode bits back to data
  compression_ratio_huffman — Compute compression ratio
  avg_code_length          — Weighted average code length
"""


# ── HuffmanNode ───────────────────────────────────────────────────────────────


struct HuffmanNode(Copyable, Movable):
    """Node in a Huffman tree.

    symbol=-1 for internal nodes. left/right are indices into the node
    array, or -1 if absent.
    """

    var symbol: Int
    var freq: Int
    var left: Int
    var right: Int

    def __init__(out self, symbol: Int, freq: Int, left: Int, right: Int):
        self.symbol = symbol
        self.freq = freq
        self.left = left
        self.right = right


# ── frequency_count ───────────────────────────────────────────────────────────


def frequency_count(data: List[Int]) -> List[List[Int]]:
    """Count frequency of each value in data.

    Args:
        data: List of integer values (byte-range).

    Returns:
        [[symbol, count], ...] sorted by count ascending.
    """
    # Find unique symbols and their counts using a simple approach
    var symbols = List[Int]()
    var counts = List[Int]()
    var n = len(data)

    for i in range(n):
        var val = data[i]
        var found = False
        for j in range(len(symbols)):
            if symbols[j] == val:
                counts[j] = counts[j] + 1
                found = True
                break
        if not found:
            symbols.append(val)
            counts.append(1)

    # Sort by count ascending (simple insertion sort)
    var m = len(symbols)
    for i in range(1, m):
        var key_sym = symbols[i]
        var key_cnt = counts[i]
        var j = i - 1
        while j >= 0 and counts[j] > key_cnt:
            symbols[j + 1] = symbols[j]
            counts[j + 1] = counts[j]
            j -= 1
        symbols[j + 1] = key_sym
        counts[j + 1] = key_cnt

    var result = List[List[Int]]()
    for i in range(m):
        var pair = List[Int]()
        pair.append(symbols[i])
        pair.append(counts[i])
        result.append(pair^)
    return result^


# ── build_huffman_tree ────────────────────────────────────────────────────────


def build_huffman_tree(freqs: List[List[Int]]) -> List[HuffmanNode]:
    """Build Huffman tree from frequency list.

    Uses an array-based approach: leaf nodes first, then internal nodes
    are appended. A simple priority-queue simulation finds the two
    lowest-frequency unused nodes each step.

    Args:
        freqs: [[symbol, count], ...] from frequency_count.

    Returns:
        List of HuffmanNode. Last element is the root.
    """
    var nodes = List[HuffmanNode]()
    var num_leaves = len(freqs)
    if num_leaves == 0:
        return nodes^

    if num_leaves == 1:
        # Single symbol: create leaf and a root pointing to it
        nodes.append(HuffmanNode(freqs[0][0], freqs[0][1], -1, -1))
        nodes.append(HuffmanNode(-1, freqs[0][1], 0, -1))
        return nodes^

    # Create leaf nodes
    for i in range(num_leaves):
        nodes.append(HuffmanNode(freqs[i][0], freqs[i][1], -1, -1))

    # Track which nodes are available (not yet merged)
    var available = List[Bool]()
    for i in range(num_leaves):
        available.append(True)

    # Build tree: merge two smallest nodes repeatedly
    for _ in range(num_leaves - 1):
        # Find two smallest available nodes
        var min1_idx = -1
        var min2_idx = -1
        var min1_freq = 2147483647  # large int
        var min2_freq = 2147483647

        var total = len(nodes)
        for i in range(total):
            if i < len(available) and available[i]:
                if nodes[i].freq < min1_freq:
                    min2_freq = min1_freq
                    min2_idx = min1_idx
                    min1_freq = nodes[i].freq
                    min1_idx = i
                elif nodes[i].freq < min2_freq:
                    min2_freq = nodes[i].freq
                    min2_idx = i

        if min1_idx == -1 or min2_idx == -1:
            break

        # Mark as used
        available[min1_idx] = False
        available[min2_idx] = False

        # Create internal node
        var new_freq = nodes[min1_idx].freq + nodes[min2_idx].freq
        nodes.append(HuffmanNode(-1, new_freq, min1_idx, min2_idx))
        available.append(True)

    return nodes^


# ── generate_codes ────────────────────────────────────────────────────────────


def generate_codes(tree: List[HuffmanNode]) -> List[List[Int]]:
    """Generate Huffman codes (as lengths) from tree.

    Uses iterative depth computation via a stack.

    Args:
        tree: Huffman tree from build_huffman_tree.

    Returns:
        [[symbol, code_length], ...] for each leaf node.
    """
    var result = List[List[Int]]()
    var n = len(tree)
    if n == 0:
        return result^

    # Compute depth of each node using a stack
    var depths = List[Int]()
    for i in range(n):
        depths.append(0)

    # Stack-based traversal from root (last node)
    var stack_node = List[Int]()
    var stack_depth = List[Int]()
    stack_node.append(n - 1)
    stack_depth.append(0)

    while len(stack_node) > 0:
        var sn_len = len(stack_node)
        var idx = stack_node[sn_len - 1]
        var depth = stack_depth[sn_len - 1]
        _ = stack_node.pop()
        _ = stack_depth.pop()

        if idx < 0 or idx >= n:
            continue

        depths[idx] = depth

        if tree[idx].left >= 0:
            stack_node.append(tree[idx].left)
            stack_depth.append(depth + 1)
        if tree[idx].right >= 0:
            stack_node.append(tree[idx].right)
            stack_depth.append(depth + 1)

    # Collect leaf nodes
    for i in range(n):
        if tree[i].symbol >= 0:
            var pair = List[Int]()
            pair.append(tree[i].symbol)
            var d = depths[i]
            if d == 0 and n > 1:
                d = 1  # single-symbol edge case
            pair.append(d)
            result.append(pair^)

    return result^


# ── _build_code_table ─────────────────────────────────────────────────────────


def _build_code_table(tree: List[HuffmanNode]) -> List[List[Int]]:
    """Build actual bit codes for each symbol via DFS.

    Returns [[symbol, bit0, bit1, ...], ...] for each leaf.
    """
    var result = List[List[Int]]()
    var n = len(tree)
    if n == 0:
        return result^

    # Stack: (node_index, code_bits_as_list_of_ints)
    var stack_idx = List[Int]()
    var stack_code_len = List[Int]()
    # Store codes in a flat list with delimiters
    var code_store = List[List[Int]]()

    stack_idx.append(n - 1)
    var empty_code = List[Int]()
    code_store.append(empty_code^)
    stack_code_len.append(0)  # index into code_store

    while len(stack_idx) > 0:
        var pos = len(stack_idx) - 1
        var idx = stack_idx[pos]
        var code_idx = stack_code_len[pos]
        _ = stack_idx.pop()
        _ = stack_code_len.pop()

        if idx < 0 or idx >= n:
            continue

        var current_code = code_store[code_idx].copy()

        if tree[idx].symbol >= 0:
            # Leaf node
            var entry = List[Int]()
            entry.append(tree[idx].symbol)
            if len(current_code) == 0:
                entry.append(0)  # single symbol gets code "0"
            else:
                for b in range(len(current_code)):
                    entry.append(current_code[b])
            result.append(entry^)
        else:
            # Internal node - push children
            if tree[idx].left >= 0:
                var left_code = List[Int]()
                for b in range(len(current_code)):
                    left_code.append(current_code[b])
                left_code.append(0)
                stack_idx.append(tree[idx].left)
                stack_code_len.append(len(code_store))
                code_store.append(left_code^)

            if tree[idx].right >= 0:
                var right_code = List[Int]()
                for b in range(len(current_code)):
                    right_code.append(current_code[b])
                right_code.append(1)
                stack_idx.append(tree[idx].right)
                stack_code_len.append(len(code_store))
                code_store.append(right_code^)

    return result^


# ── huffman_encode ────────────────────────────────────────────────────────────


def huffman_encode(data: List[Int]) -> List[Int]:
    """Encode data using Huffman coding.

    Args:
        data: List of integer symbols.

    Returns:
        Encoded bit sequence as List[Int] of 0s and 1s.
    """
    var freqs = frequency_count(data)
    var tree = build_huffman_tree(freqs)
    var codes = _build_code_table(tree)

    var result = List[Int]()
    var n = len(data)
    for i in range(n):
        var sym = data[i]
        # Find code for this symbol
        for c in range(len(codes)):
            if codes[c][0] == sym:
                for b in range(1, len(codes[c])):
                    result.append(codes[c][b])
                break
    return result^


# ── huffman_decode ────────────────────────────────────────────────────────────


def huffman_decode(bits: List[Int], tree: List[HuffmanNode]) -> List[Int]:
    """Decode bit sequence back to original data.

    Args:
        bits: List of 0s and 1s.
        tree: Huffman tree used for encoding.

    Returns:
        Decoded symbol list.
    """
    var result = List[Int]()
    var n = len(tree)
    if n == 0:
        return result^

    var root = n - 1
    var current = root
    var num_bits = len(bits)

    # Handle single-symbol tree
    if n <= 2 and tree[0].symbol >= 0:
        for i in range(num_bits):
            result.append(tree[0].symbol)
        return result^

    for i in range(num_bits):
        if bits[i] == 0:
            current = tree[current].left
        else:
            current = tree[current].right

        if current < 0 or current >= n:
            break

        if tree[current].symbol >= 0:
            result.append(tree[current].symbol)
            current = root

    return result^


# ── compression_ratio_huffman ─────────────────────────────────────────────────


def compression_ratio_huffman(original_size: Int, encoded_bits: Int) -> Float64:
    """Compression ratio: original_size * 8 / encoded_bits.

    Args:
        original_size: Number of original symbols (bytes).
        encoded_bits: Number of bits in encoded output.

    Returns:
        Compression ratio. Higher means better compression.
    """
    if encoded_bits == 0:
        return 0.0
    return Float64(original_size * 8) / Float64(encoded_bits)


# ── avg_code_length ───────────────────────────────────────────────────────────


def avg_code_length(freqs: List[List[Int]], codes: List[List[Int]]) -> Float64:
    """Weighted average code length.

    Args:
        freqs: [[symbol, count], ...] frequency table.
        codes: [[symbol, code_length], ...] from generate_codes.

    Returns:
        Average code length weighted by frequency.
    """
    var total_freq = 0
    for i in range(len(freqs)):
        total_freq += freqs[i][1]
    if total_freq == 0:
        return 0.0

    var weighted_sum = 0.0
    for i in range(len(codes)):
        var sym = codes[i][0]
        var code_len = codes[i][1]
        # Find frequency
        for j in range(len(freqs)):
            if freqs[j][0] == sym:
                weighted_sum += Float64(code_len) * Float64(freqs[j][1])
                break
    return weighted_sum / Float64(total_freq)
