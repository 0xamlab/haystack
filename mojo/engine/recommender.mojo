"""
recommender.mojo — Recommendation systems. Zero Python imports.

Replaces surprise / implicit with pure Mojo implementations for
collaborative filtering, popularity ranking, KNN prediction, and
evaluation metrics.

Public API:
  cosine_sim_users      — Cosine similarity between two users
  predict_rating        — KNN collaborative filter prediction
  popularity_ranking    — Rank items by number of ratings (desc)
  mean_rating_per_item  — Average rating per item (excl. zeros)
  mean_rating_per_user  — Average rating per user (excl. zeros)
  top_n_items           — Indices of top-n scored items
  item_overlap          — Count items rated by both users
  cold_start_recommend  — Recommend top-n most popular items
  rmse_ratings          — RMSE on non-zero actuals
"""
from std.math import sqrt


# ── cosine_sim_users ──────────────────────────────────────────────────────────


fn cosine_sim_users(
    ratings: List[List[Float64]], u1: Int, u2: Int
) -> Float64:
    """Cosine similarity between two users on co-rated items."""
    var n_items = len(ratings[u1])
    var dot: Float64 = 0.0
    var norm1: Float64 = 0.0
    var norm2: Float64 = 0.0
    for j in range(n_items):
        var r1 = ratings[u1][j]
        var r2 = ratings[u2][j]
        if r1 != 0.0 and r2 != 0.0:
            dot += r1 * r2
            norm1 += r1 * r1
            norm2 += r2 * r2
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (sqrt(norm1) * sqrt(norm2))


# ── predict_rating ────────────────────────────────────────────────────────────


fn predict_rating(
    ratings: List[List[Float64]], user: Int, item: Int, k: Int
) -> Float64:
    """KNN collaborative filter: weighted average of k most similar users."""
    var n_users = len(ratings)
    # Collect (similarity, rating) for users who rated this item
    var sims = List[Float64]()
    var rats = List[Float64]()
    for u in range(n_users):
        if u == user:
            continue
        if ratings[u][item] == 0.0:
            continue
        var s = cosine_sim_users(ratings, user, u)
        if s > 0.0:
            sims.append(s)
            rats.append(ratings[u][item])
    # Select top-k by similarity (insertion sort on sims desc)
    var n = len(sims)
    for i in range(1, n):
        var ks = sims[i]
        var kr = rats[i]
        var j = i - 1
        while j >= 0 and sims[j] < ks:
            sims[j + 1] = sims[j]
            rats[j + 1] = rats[j]
            j -= 1
        sims[j + 1] = ks
        rats[j + 1] = kr
    var top = k if k < n else n
    var wsum: Float64 = 0.0
    var wdenom: Float64 = 0.0
    for i in range(top):
        wsum += sims[i] * rats[i]
        wdenom += sims[i]
    if wdenom == 0.0:
        return 0.0
    return wsum / wdenom


# ── popularity_ranking ────────────────────────────────────────────────────────


fn popularity_ranking(ratings: List[List[Float64]]) -> List[Int]:
    """Rank items by number of ratings (descending)."""
    var n_users = len(ratings)
    if n_users == 0:
        return List[Int]()
    var n_items = len(ratings[0])
    var counts = List[Int]()
    var indices = List[Int]()
    for j in range(n_items):
        var c = 0
        for u in range(n_users):
            if ratings[u][j] != 0.0:
                c += 1
        counts.append(c)
        indices.append(j)
    # Insertion sort descending by count
    for i in range(1, n_items):
        var kc = counts[i]
        var ki = indices[i]
        var j = i - 1
        while j >= 0 and counts[j] < kc:
            counts[j + 1] = counts[j]
            indices[j + 1] = indices[j]
            j -= 1
        counts[j + 1] = kc
        indices[j + 1] = ki
    return indices^


# ── mean_rating_per_item ──────────────────────────────────────────────────────


fn mean_rating_per_item(ratings: List[List[Float64]]) -> List[Float64]:
    """Average rating for each item (excluding 0s)."""
    var n_users = len(ratings)
    if n_users == 0:
        return List[Float64]()
    var n_items = len(ratings[0])
    var result = List[Float64]()
    for j in range(n_items):
        var s: Float64 = 0.0
        var c = 0
        for u in range(n_users):
            if ratings[u][j] != 0.0:
                s += ratings[u][j]
                c += 1
        if c == 0:
            result.append(0.0)
        else:
            result.append(s / Float64(c))
    return result^


# ── mean_rating_per_user ──────────────────────────────────────────────────────


fn mean_rating_per_user(ratings: List[List[Float64]]) -> List[Float64]:
    """Average rating per user (excluding 0s)."""
    var n_users = len(ratings)
    var result = List[Float64]()
    for u in range(n_users):
        var s: Float64 = 0.0
        var c = 0
        var n_items = len(ratings[u])
        for j in range(n_items):
            if ratings[u][j] != 0.0:
                s += ratings[u][j]
                c += 1
        if c == 0:
            result.append(0.0)
        else:
            result.append(s / Float64(c))
    return result^


# ── top_n_items ───────────────────────────────────────────────────────────────


fn top_n_items(item_scores: List[Float64], n: Int) -> List[Int]:
    """Indices of top-n scored items."""
    var m = len(item_scores)
    var scores = List[Float64]()
    var indices = List[Int]()
    for i in range(m):
        scores.append(item_scores[i])
        indices.append(i)
    # Insertion sort descending
    for i in range(1, m):
        var ks = scores[i]
        var ki = indices[i]
        var j = i - 1
        while j >= 0 and scores[j] < ks:
            scores[j + 1] = scores[j]
            indices[j + 1] = indices[j]
            j -= 1
        scores[j + 1] = ks
        indices[j + 1] = ki
    var top = n if n < m else m
    var result = List[Int]()
    for i in range(top):
        result.append(indices[i])
    return result^


# ── item_overlap ──────────────────────────────────────────────────────────────


fn item_overlap(
    ratings: List[List[Float64]], u1: Int, u2: Int
) -> Int:
    """Count items rated by both users."""
    var n_items = len(ratings[u1])
    var count = 0
    for j in range(n_items):
        if ratings[u1][j] != 0.0 and ratings[u2][j] != 0.0:
            count += 1
    return count


# ── cold_start_recommend ──────────────────────────────────────────────────────


fn cold_start_recommend(
    ratings: List[List[Float64]], n: Int
) -> List[Int]:
    """Recommend top-n most popular items (cold start strategy)."""
    var ranked = popularity_ranking(ratings)
    var top = n if n < len(ranked) else len(ranked)
    var result = List[Int]()
    for i in range(top):
        result.append(ranked[i])
    return result^


# ── rmse_ratings ──────────────────────────────────────────────────────────────


fn rmse_ratings(
    predicted: List[Float64], actual: List[Float64]
) -> Float64:
    """RMSE on non-zero actuals."""
    var n = len(actual)
    var sse: Float64 = 0.0
    var count = 0
    for i in range(n):
        if actual[i] != 0.0:
            var diff = predicted[i] - actual[i]
            sse += diff * diff
            count += 1
    if count == 0:
        return 0.0
    return sqrt(sse / Float64(count))
