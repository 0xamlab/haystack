"""
voting.mojo — Voting Theory & Social Choice Library. Zero Python imports.

Implements plurality, Borda, Condorcet, approval voting, majority/quota
thresholds, seat-allocation divisors, and power indices.

Public API:
  plurality_winner          — Candidate with most first-place votes
  borda_score               — Borda count for a candidate
  condorcet_pairwise        — Pairwise comparison result
  approval_score            — Count of approvals
  majority_threshold        — Floor(n/2) + 1
  quota_droop               — Droop quota
  quota_hare                — Hare quota
  dhondt_divisor            — D'Hondt divisor
  sainte_lague_divisor      — Sainte-Laguë divisor
  power_index_banzhaf       — Banzhaf power index
  spoiler_effect            — Spoiler effect detection
"""


# ── plurality_winner ──────────────────────────────────────────────────────────


fn plurality_winner(votes: List[Int], n_candidates: Int) -> Int:
    """Return index of candidate with the most first-place votes.

    `votes` contains first-choice candidate index per voter.
    Returns the candidate index with maximum tally.
    """
    var tallies = List[Int]()
    for _i in range(n_candidates):
        tallies.append(0)
    for i in range(len(votes)):
        var c = votes[i]
        if c >= 0 and c < n_candidates:
            tallies[c] = tallies[c] + 1
    var best = 0
    var best_count = tallies[0]
    for i in range(1, n_candidates):
        if tallies[i] > best_count:
            best = i
            best_count = tallies[i]
    return best


# ── borda_score ───────────────────────────────────────────────────────────────


fn borda_score(ranks: List[Int], n_candidates: Int, candidate_idx: Int) -> Int:
    """Borda count for `candidate_idx`.

    `ranks` is a flat list of rankings: for each voter, n_candidates entries
    giving the rank (0-based position) of each candidate.
    Points = (n_candidates - 1) - rank.
    """
    var n_voters = len(ranks) // n_candidates
    var score = 0
    for v in range(n_voters):
        var rank_val = ranks[v * n_candidates + candidate_idx]
        score += (n_candidates - 1) - rank_val
    return score


# ── condorcet_pairwise ────────────────────────────────────────────────────────


fn condorcet_pairwise(a_votes: Int, b_votes: Int) -> Int:
    """Return 1 if a wins, -1 if b wins, 0 if tie."""
    if a_votes > b_votes:
        return 1
    elif b_votes > a_votes:
        return -1
    return 0


# ── approval_score ────────────────────────────────────────────────────────────


fn approval_score(approvals: List[Int], n_voters: Int) -> Int:
    """Count of approvals for a candidate.

    `approvals` contains 1 or 0 per voter (whether they approve).
    """
    var count = 0
    for i in range(n_voters):
        if approvals[i] == 1:
            count += 1
    return count


# ── majority_threshold ────────────────────────────────────────────────────────


fn majority_threshold(n_voters: Int) -> Int:
    """Floor(n/2) + 1 — minimum votes for a strict majority."""
    return n_voters // 2 + 1


# ── quota_droop ───────────────────────────────────────────────────────────────


fn quota_droop(n_votes: Int, n_seats: Int) -> Int:
    """Droop quota = floor(votes / (seats + 1)) + 1."""
    return n_votes // (n_seats + 1) + 1


# ── quota_hare ────────────────────────────────────────────────────────────────


fn quota_hare(n_votes: Int, n_seats: Int) -> Float64:
    """Hare quota = votes / seats."""
    return Float64(n_votes) / Float64(n_seats)


# ── dhondt_divisor ────────────────────────────────────────────────────────────


fn dhondt_divisor(seats_won: Int) -> Int:
    """D'Hondt divisor = seats_won + 1."""
    return seats_won + 1


# ── sainte_lague_divisor ──────────────────────────────────────────────────────


fn sainte_lague_divisor(seats_won: Int) -> Int:
    """Sainte-Laguë divisor = 2 * seats_won + 1."""
    return 2 * seats_won + 1


# ── power_index_banzhaf ──────────────────────────────────────────────────────


fn power_index_banzhaf(
    wins_with: Int, wins_without: Int, total_coalitions: Int,
) -> Float64:
    """Banzhaf power = (wins_with - wins_without) / total_coalitions."""
    return Float64(wins_with - wins_without) / Float64(total_coalitions)


# ── spoiler_effect ────────────────────────────────────────────────────────────


fn spoiler_effect(winner_with: Int, winner_without: Int) -> Bool:
    """Check if removing a candidate changes the winner (spoiler effect)."""
    return winner_with != winner_without
