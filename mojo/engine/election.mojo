"""
election.mojo — Voting/Election methods. Zero Python imports.

Replaces custom election/voting code with pure Mojo implementations of
plurality, Borda count, Condorcet, instant runoff, approval, and Copeland.

Ballots as List[List[Int]] where each ballot is a ranked list of candidate
indices (most preferred first).

Public API:
  plurality        — winner by most first-place votes
  borda_count      — Borda count scores
  borda_winner     — winner by Borda count
  condorcet_winner — Condorcet winner or -1
  pairwise_matrix  — NxN pairwise preference matrix
  instant_runoff   — IRV/ranked-choice voting winner
  approval_voting  — approval voting winner
  copeland_scores  — Copeland method scores
"""


fn _ballots_valid(ballots: List[List[Int]], n_candidates: Int) -> Bool:
    """True when n_candidates > 0 and every ballot entry lies in [0, n_candidates).

    Ballot entries are used directly as indices into count/score/matrix lists;
    an out-of-range one is an uncatchable out-of-bounds abort.
    """
    if n_candidates <= 0:
        return False
    for b in range(len(ballots)):
        for i in range(len(ballots[b])):
            var c = ballots[b][i]
            if c < 0 or c >= n_candidates:
                return False
    return True


# ── pairwise_matrix ──────────────────────────────────────────────────────────


fn pairwise_matrix(
    ballots: List[List[Int]], n_candidates: Int
) -> List[List[Int]]:
    """NxN matrix where [i][j] = number of ballots preferring i over j."""
    if not _ballots_valid(ballots, n_candidates):
        return List[List[Int]]()
    var matrix = List[List[Int]]()
    for i in range(n_candidates):
        var row = List[Int]()
        for j in range(n_candidates):
            row.append(0)
        matrix.append(row^)
    var nb = len(ballots)
    for b in range(nb):
        var ballot = ballots[b].copy()
        var blen = len(ballot)
        # For each pair, the one appearing earlier is preferred
        for i in range(blen):
            for j in range(i + 1, blen):
                var ci = ballot[i]
                var cj = ballot[j]
                var row = matrix[ci].copy()
                row[cj] += 1
                matrix[ci] = row^
    return matrix^


# ── plurality ────────────────────────────────────────────────────────────────


fn plurality(ballots: List[List[Int]], n_candidates: Int) -> Int:
    """Plurality voting: winner is candidate with most first-place votes."""
    if not _ballots_valid(ballots, n_candidates):
        return -1
    var counts = List[Int]()
    for _ in range(n_candidates):
        counts.append(0)
    var nb = len(ballots)
    for b in range(nb):
        var ballot = ballots[b].copy()
        if len(ballot) > 0:
            counts[ballot[0]] += 1
    var best = -1
    var best_count = -1
    for i in range(n_candidates):
        if counts[i] > best_count:
            best_count = counts[i]
            best = i
    return best


# ── borda_count ──────────────────────────────────────────────────────────────


fn borda_count(
    ballots: List[List[Int]], n_candidates: Int
) -> List[Float64]:
    """Borda count scores. Last place = 0, first = n-1 points."""
    if not _ballots_valid(ballots, n_candidates):
        return List[Float64]()
    var scores = List[Float64]()
    for _ in range(n_candidates):
        scores.append(0.0)
    var nb = len(ballots)
    for b in range(nb):
        var ballot = ballots[b].copy()
        var blen = len(ballot)
        for rank in range(blen):
            # First place gets n_candidates - 1 points, etc.
            var points = Float64(n_candidates - 1 - rank)
            scores[ballot[rank]] += points
    return scores^


# ── borda_winner ─────────────────────────────────────────────────────────────


fn borda_winner(ballots: List[List[Int]], n_candidates: Int) -> Int:
    """Winner by Borda count."""
    if not _ballots_valid(ballots, n_candidates):
        return -1
    var scores = borda_count(ballots, n_candidates)
    var best = -1
    var best_score: Float64 = -1.0
    for i in range(n_candidates):
        if scores[i] > best_score:
            best_score = scores[i]
            best = i
    return best


# ── condorcet_winner ─────────────────────────────────────────────────────────


fn condorcet_winner(ballots: List[List[Int]], n_candidates: Int) -> Int:
    """Condorcet winner (beats all others pairwise). Returns -1 if none."""
    if not _ballots_valid(ballots, n_candidates):
        return -1
    var matrix = pairwise_matrix(ballots, n_candidates)
    for i in range(n_candidates):
        var wins_all = True
        var row_i = matrix[i].copy()
        for j in range(n_candidates):
            if i != j:
                var row_j = matrix[j].copy()
                if row_i[j] <= row_j[i]:
                    wins_all = False
                    break
        if wins_all:
            return i
    return -1


# ── instant_runoff ───────────────────────────────────────────────────────────


fn instant_runoff(ballots: List[List[Int]], n_candidates: Int) -> Int:
    """Instant runoff voting (IRV/ranked choice).

    Eliminate candidate with fewest first-place votes, redistribute, repeat.
    """
    if not _ballots_valid(ballots, n_candidates):
        return -1
    # Track which candidates are eliminated
    var eliminated = List[Bool]()
    for _ in range(n_candidates):
        eliminated.append(False)

    var n_active = n_candidates
    var nb = len(ballots)

    while n_active > 1:
        # Count first-place votes among non-eliminated candidates
        var counts = List[Int]()
        for _ in range(n_candidates):
            counts.append(0)
        for b in range(nb):
            var ballot = ballots[b].copy()
            var blen = len(ballot)
            for r in range(blen):
                if not eliminated[ballot[r]]:
                    counts[ballot[r]] += 1
                    break

        # Check for majority
        var total_votes = 0
        for i in range(n_candidates):
            if not eliminated[i]:
                total_votes += counts[i]
        for i in range(n_candidates):
            if not eliminated[i] and counts[i] * 2 > total_votes:
                return i

        # Find minimum count among active candidates
        var min_count = total_votes + 1
        for i in range(n_candidates):
            if not eliminated[i] and counts[i] < min_count:
                min_count = counts[i]

        # Eliminate candidate(s) with min count
        for i in range(n_candidates):
            if not eliminated[i] and counts[i] == min_count:
                eliminated[i] = True
                n_active -= 1
                if n_active <= 1:
                    break

    # Return the last standing candidate
    for i in range(n_candidates):
        if not eliminated[i]:
            return i
    return -1


# ── approval_voting ──────────────────────────────────────────────────────────


fn approval_voting(approvals: List[List[Int]], n_candidates: Int) -> Int:
    """Approval voting: each ballot lists approved candidates.

    Winner = most approvals.
    """
    if not _ballots_valid(approvals, n_candidates):
        return -1
    var counts = List[Int]()
    for _ in range(n_candidates):
        counts.append(0)
    var nb = len(approvals)
    for b in range(nb):
        var ballot = approvals[b].copy()
        var blen = len(ballot)
        for i in range(blen):
            counts[ballot[i]] += 1
    var best = -1
    var best_count = -1
    for i in range(n_candidates):
        if counts[i] > best_count:
            best_count = counts[i]
            best = i
    return best


# ── copeland_scores ──────────────────────────────────────────────────────────


fn copeland_scores(
    ballots: List[List[Int]], n_candidates: Int
) -> List[Float64]:
    """Copeland method: +1 for pairwise win, +0.5 for tie, 0 for loss."""
    if not _ballots_valid(ballots, n_candidates):
        return List[Float64]()
    var matrix = pairwise_matrix(ballots, n_candidates)
    var scores = List[Float64]()
    for _ in range(n_candidates):
        scores.append(0.0)
    for i in range(n_candidates):
        var row_i = matrix[i].copy()
        for j in range(i + 1, n_candidates):
            var row_j = matrix[j].copy()
            if row_i[j] > row_j[i]:
                scores[i] += 1.0
            elif row_i[j] < row_j[i]:
                scores[j] += 1.0
            else:
                scores[i] += 0.5
                scores[j] += 0.5
    return scores^
