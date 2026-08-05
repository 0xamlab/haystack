"""
trie.mojo — Trie data structure for prefix-based string operations.

Replaces Python's pygtrie with a pure Mojo implementation using flat
parallel arrays with first-child/next-sibling tree representation.

Public API:
  Trie              — Struct holding trie node data in parallel arrays
  trie_create        — Create empty trie with root node
  trie_insert        — Insert a word into the trie
  trie_search        — Exact word search
  trie_starts_with   — Check if any word starts with prefix
  trie_count_words   — Count total words stored
  trie_count_nodes   — Count total nodes
  trie_word_list     — Get all words via DFS traversal
  trie_prefix_count  — Count words starting with a given prefix
"""


# ── Trie struct ───────────────────────────────────────────────────────────────


@fieldwise_init
struct Trie:
    """Trie stored as flat parallel arrays.

    Uses first-child / next-sibling representation to avoid nested lists.
    """

    var nodes_char: List[Int]
    var nodes_parent: List[Int]
    var nodes_end: List[Int]
    var nodes_first_child: List[Int]
    var nodes_next_sibling: List[Int]

    fn __init__(out self):
        self.nodes_char = List[Int]()
        self.nodes_parent = List[Int]()
        self.nodes_end = List[Int]()
        self.nodes_first_child = List[Int]()
        self.nodes_next_sibling = List[Int]()


# ── Helpers ───────────────────────────────────────────────────────────────────


fn _valid_node(t: Trie, idx: Int) -> Bool:
    """True if idx is a readable index in every parallel node list."""
    return idx >= 0 and idx < len(t.nodes_char) and idx < len(t.nodes_parent) and idx < len(t.nodes_end) and idx < len(t.nodes_first_child) and idx < len(t.nodes_next_sibling)


fn _pool_consistent(t: Trie) -> Bool:
    """True if all parallel node lists have the same length."""
    var n = len(t.nodes_char)
    return len(t.nodes_parent) == n and len(t.nodes_end) == n and len(t.nodes_first_child) == n and len(t.nodes_next_sibling) == n


fn _add_node(mut t: Trie, char_val: Int, parent_idx: Int, is_end: Int) -> Int:
    """Add a new node and return its index."""
    var idx = len(t.nodes_char)
    t.nodes_char.append(char_val)
    t.nodes_parent.append(parent_idx)
    t.nodes_end.append(is_end)
    t.nodes_first_child.append(-1)
    t.nodes_next_sibling.append(-1)
    return idx


fn _find_child(t: Trie, node_idx: Int, char_val: Int) -> Int:
    """Find child of node_idx with given char. Returns -1 if not found."""
    if not _valid_node(t, node_idx):
        return -1
    var child = t.nodes_first_child[node_idx]
    while child != -1:
        if not _valid_node(t, child):
            return -1
        if t.nodes_char[child] == char_val:
            return child
        child = t.nodes_next_sibling[child]
    return -1


fn _add_child(mut t: Trie, parent_idx: Int, char_val: Int) -> Int:
    """Add a child node to parent and return the new node's index."""
    # Refuse absent/ragged pools: the appended index must be valid in every list.
    if not _pool_consistent(t) or not _valid_node(t, parent_idx):
        return -1
    var new_idx = _add_node(t, char_val, parent_idx, 0)
    # Prepend to sibling list (O(1))
    t.nodes_next_sibling[new_idx] = t.nodes_first_child[parent_idx]
    t.nodes_first_child[parent_idx] = new_idx
    return new_idx


# ── Public API ────────────────────────────────────────────────────────────────


fn trie_create(out t: Trie):
    """Create an empty trie with a root node (char=0, no parent)."""
    t = Trie()
    _ = _add_node(t, 0, -1, 0)  # root node at index 0


fn trie_insert(mut t: Trie, word: String):
    """Insert a word into the trie."""
    var current: Int = 0  # start at root
    var bytes_val = word.as_bytes()
    for i in range(len(word)):
        var ch = Int(bytes_val[i])
        var child = _find_child(t, current, ch)
        if child == -1:
            current = _add_child(t, current, ch)
        else:
            current = child
    if _valid_node(t, current):
        t.nodes_end[current] = 1


fn trie_search(t: Trie, word: String) -> Bool:
    """Exact word search. Returns True if word is in trie."""
    if not _valid_node(t, 0):
        return False
    var current: Int = 0
    var bytes_val = word.as_bytes()
    for i in range(len(word)):
        var ch = Int(bytes_val[i])
        var child = _find_child(t, current, ch)
        if child == -1:
            return False
        current = child
    return t.nodes_end[current] == 1


fn trie_starts_with(t: Trie, prefix: String) -> Bool:
    """Check if any word in the trie starts with given prefix."""
    var current: Int = 0
    var bytes_val = prefix.as_bytes()
    for i in range(len(prefix)):
        var ch = Int(bytes_val[i])
        var child = _find_child(t, current, ch)
        if child == -1:
            return False
        current = child
    return True


fn trie_count_words(t: Trie) -> Int:
    """Count total words stored in trie."""
    var count: Int = 0
    for i in range(len(t.nodes_end)):
        if t.nodes_end[i] == 1:
            count += 1
    return count


fn trie_count_nodes(t: Trie) -> Int:
    """Count total nodes in trie (including root)."""
    return len(t.nodes_char)


fn _build_word(t: Trie, node_idx: Int) -> String:
    """Build word by tracing from node back to root."""
    var chars = List[Int]()
    var idx = node_idx
    while idx > 0:
        # Bounds-check the pool read; the step bound stops parent-pointer cycles.
        if not _valid_node(t, idx) or len(chars) >= len(t.nodes_char):
            break
        chars.append(t.nodes_char[idx])
        idx = t.nodes_parent[idx]
    # Reverse to get correct order
    var result = String("")
    for i in range(len(chars) - 1, -1, -1):
        result += chr(chars[i])
    return result


fn _dfs_collect(t: Trie, node_idx: Int, mut words: List[String]):
    """DFS to collect all words from a subtree using iterative stack."""
    # Use an iterative approach with a manual stack to avoid passing List[String]
    if not _valid_node(t, node_idx):
        return
    if t.nodes_end[node_idx] == 1:
        words.append(_build_word(t, node_idx))
    var child = t.nodes_first_child[node_idx]
    while child != -1:
        if not _valid_node(t, child):
            return
        _dfs_collect(t, child, words)
        child = t.nodes_next_sibling[child]


fn trie_word_list(t: Trie) -> List[String]:
    """Get all words in the trie via DFS traversal."""
    var words = List[String]()
    if not _valid_node(t, 0):
        return words^
    _dfs_collect(t, 0, words)
    return words^


fn _count_words_subtree(t: Trie, node_idx: Int) -> Int:
    """Count words in the subtree rooted at node_idx."""
    var count: Int = 0
    if not _valid_node(t, node_idx):
        return 0
    if t.nodes_end[node_idx] == 1:
        count = 1
    var child = t.nodes_first_child[node_idx]
    while child != -1:
        if not _valid_node(t, child):
            return count
        count += _count_words_subtree(t, child)
        child = t.nodes_next_sibling[child]
    return count


fn trie_prefix_count(t: Trie, prefix: String) -> Int:
    """Count words starting with the given prefix."""
    var current: Int = 0
    var bytes_val = prefix.as_bytes()
    for i in range(len(prefix)):
        var ch = Int(bytes_val[i])
        var child = _find_child(t, current, ch)
        if child == -1:
            return 0
        current = child
    return _count_words_subtree(t, current)
