"""Python equivalent of mojo/engine/trie.mojo (auto-generated)."""
import math
import random as _rng

class Trie:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('nodes_char')
        self.nodes_char = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('nodes_parent')
        self.nodes_parent = _v1 if _v1 is not None else []
        _v2 = args[2] if 2 < len(args) else kwargs.get('nodes_end')
        self.nodes_end = _v2 if _v2 is not None else []
        _v3 = args[3] if 3 < len(args) else kwargs.get('nodes_first_child')
        self.nodes_first_child = _v3 if _v3 is not None else []
        _v4 = args[4] if 4 < len(args) else kwargs.get('nodes_next_sibling')
        self.nodes_next_sibling = _v4 if _v4 is not None else []
    def __repr__(self):
        return f'Trie({vars(self)})'

def random_float64(lo=0.0, hi=1.0): return _rng.uniform(lo, hi)
def random_si64(): return _rng.randint(-2**31, 2**31)
def random_ui64(): return _rng.randint(0, 2**32)

def _add_node(t, char_val, parent_idx, is_end):
    idx = len(t.nodes_char)
    t.nodes_char.append(char_val)
    t.nodes_parent.append(parent_idx)
    t.nodes_end.append(is_end)
    t.nodes_first_child.append(-1)
    t.nodes_next_sibling.append(-1)
    return idx



def _find_child(t, node_idx, char_val):
    child = t.nodes_first_child[node_idx]
    while child != -1:
        if t.nodes_char[child] == char_val:
            return child
        child = t.nodes_next_sibling[child]
    return -1



def _add_child(t, parent_idx, char_val):
    new_idx = _add_node(t, char_val, parent_idx, 0)

    t.nodes_next_sibling[new_idx] = t.nodes_first_child[parent_idx]
    t.nodes_first_child[parent_idx] = new_idx
    return new_idx






def _build_word(t, node_idx):
    chars = []
    idx = node_idx
    while idx > 0:
        chars.append(t.nodes_char[idx])
        idx = t.nodes_parent[idx]

    result = str("")
    for i in range(len(chars) - 1, -1, -1):
        result += chr(chars[i])
    return result



def _dfs_collect(t, node_idx, words):

    if t.nodes_end[node_idx] == 1:
        words.append(_build_word(t, node_idx))
    child = t.nodes_first_child[node_idx]
    while child != -1:
        _dfs_collect(t, child, words)
        child = t.nodes_next_sibling[child]



def _count_words_subtree(t, node_idx):
    count = 0
    if t.nodes_end[node_idx] == 1:
        count = 1
    child = t.nodes_first_child[node_idx]
    while child != -1:
        count += _count_words_subtree(t, child)
        child = t.nodes_next_sibling[child]
    return count



def trie_count_words(t):
    count = 0
    for i in range(len(t.nodes_end)):
        if t.nodes_end[i] == 1:
            count += 1
    return count



def trie_count_nodes(t):
    return len(t.nodes_char)



def trie_word_list(t):
    words = []
    _dfs_collect(t, 0, words)
    return words


