"""
auction.mojo — Auction & Mechanism Design Library. Zero Python imports.

Pure Mojo implementations for sealed-bid auctions, English/Dutch/all-pay
revenue, VCG payments, reserve pricing, bid shading, and winner's curse.

Public API:
  first_price_sealed          — Winner pays their bid
  second_price_sealed         — Vickrey auction; winner pays 2nd-highest
  english_auction_revenue     — Revenue from ascending auction
  dutch_auction_revenue       — Revenue from descending auction
  all_pay_revenue             — Total revenue from all-pay auction
  revenue_equivalence_check   — Check if expected revenues approx equal
  vcg_payment                 — VCG mechanism payment for single item
  reserve_price_filter        — Count/sum of bids above reserve
  bid_shading_optimal         — Optimal bid in first-price auction
  expected_revenue_uniform    — Expected revenue with n uniform bidders
  winners_curse_adjustment    — Shade estimate for common value
"""
from std.math import abs as fabs


# ── first_price_sealed ───────────────────────────────────────────────────────


fn first_price_sealed(bids: List[Float64], n: Int) -> List[Float64]:
    """First-price sealed-bid auction. Winner pays their own bid.
    Returns [winner_idx, price]. If n<=0, returns [-1, 0]."""
    if n <= 0:
        var r = List[Float64]()
        r.append(-1.0)
        r.append(0.0)
        return r^
    var best_idx: Int = 0
    var best_val: Float64 = bids[0]
    for i in range(1, n):
        if bids[i] > best_val:
            best_val = bids[i]
            best_idx = i
    var result = List[Float64]()
    result.append(Float64(best_idx))
    result.append(best_val)
    return result^


# ── second_price_sealed ──────────────────────────────────────────────────────


fn second_price_sealed(bids: List[Float64], n: Int) -> List[Float64]:
    """Vickrey (second-price sealed-bid) auction. Winner pays 2nd-highest bid.
    Returns [winner_idx, price]. If n<=1, winner pays 0."""
    if n <= 0:
        var r = List[Float64]()
        r.append(-1.0)
        r.append(0.0)
        return r^
    var best_idx: Int = 0
    var best_val: Float64 = bids[0]
    var second_val: Float64 = 0.0
    for i in range(1, n):
        if bids[i] > best_val:
            second_val = best_val
            best_val = bids[i]
            best_idx = i
        elif bids[i] > second_val:
            second_val = bids[i]
    var result = List[Float64]()
    result.append(Float64(best_idx))
    result.append(second_val)
    return result^


# ── english_auction_revenue ──────────────────────────────────────────────────


fn english_auction_revenue(bids: List[Float64], n: Int) -> Float64:
    """Revenue from ascending (English) auction = second-highest bid."""
    if n <= 0:
        return 0.0
    if n == 1:
        return bids[0]
    var best: Float64 = bids[0]
    var second: Float64 = 0.0
    for i in range(1, n):
        if bids[i] > best:
            second = best
            best = bids[i]
        elif bids[i] > second:
            second = bids[i]
    return second


# ── dutch_auction_revenue ────────────────────────────────────────────────────


fn dutch_auction_revenue(bids: List[Float64], n: Int) -> Float64:
    """Revenue from descending (Dutch) auction = highest bid."""
    if n <= 0:
        return 0.0
    var best: Float64 = bids[0]
    for i in range(1, n):
        if bids[i] > best:
            best = bids[i]
    return best


# ── all_pay_revenue ──────────────────────────────────────────────────────────


fn all_pay_revenue(bids: List[Float64], n: Int) -> Float64:
    """All-pay auction total revenue = sum of all bids."""
    var total: Float64 = 0.0
    for i in range(n):
        total += bids[i]
    return total


# ── revenue_equivalence_check ────────────────────────────────────────────────


fn revenue_equivalence_check(bids: List[Float64], n: Int) -> Bool:
    """Check revenue equivalence: for uniform IPV, first-price and second-price
    expected revenues should be approximately equal. Returns True if within 20%
    or both revenues are near zero."""
    var fp = dutch_auction_revenue(bids, n)  # first-price = highest bid
    var sp = english_auction_revenue(bids, n)  # second-price = second highest
    if fabs(fp) < 1e-12 and fabs(sp) < 1e-12:
        return True
    var avg = (fp + sp) / 2.0
    if fabs(avg) < 1e-12:
        return True
    return fabs(fp - sp) / avg < 0.2


# ── vcg_payment ──────────────────────────────────────────────────────────────


fn vcg_payment(values: List[Float64], n: Int, winner_idx: Int) -> Float64:
    """VCG mechanism payment for single item auction.
    Payment = max value of others (externality imposed by winner)."""
    var max_other: Float64 = 0.0
    for i in range(n):
        if i != winner_idx and values[i] > max_other:
            max_other = values[i]
    return max_other


# ── reserve_price_filter ─────────────────────────────────────────────────────


fn reserve_price_filter(bids: List[Float64], n: Int, reserve: Float64) -> List[Float64]:
    """Filter bids above reserve price. Returns [count_above, sum_above]."""
    var count: Float64 = 0.0
    var total: Float64 = 0.0
    for i in range(n):
        if bids[i] >= reserve:
            count += 1.0
            total += bids[i]
    var result = List[Float64]()
    result.append(count)
    result.append(total)
    return result^


# ── bid_shading_optimal ──────────────────────────────────────────────────────


fn bid_shading_optimal(value: Float64, n_bidders: Int) -> Float64:
    """Optimal bid in first-price auction with n bidders (uniform IPV).
    Bid = value * (n-1)/n."""
    if n_bidders <= 1:
        return 0.0
    return value * Float64(n_bidders - 1) / Float64(n_bidders)


# ── expected_revenue_uniform ─────────────────────────────────────────────────


fn expected_revenue_uniform(n_bidders: Int, max_val: Float64) -> Float64:
    """Expected revenue with n uniform bidders on [0, max_val].
    E[revenue] = (n-1)/(n+1) * max_val."""
    if n_bidders <= 0:
        return 0.0
    return Float64(n_bidders - 1) / Float64(n_bidders + 1) * max_val


# ── winners_curse_adjustment ─────────────────────────────────────────────────


fn winners_curse_adjustment(estimate: Float64, n_bidders: Int) -> Float64:
    """Shade estimate for common-value auction to avoid winner's curse.
    Adjusted = estimate * (n-1)/n."""
    if n_bidders <= 1:
        return estimate
    return estimate * Float64(n_bidders - 1) / Float64(n_bidders)
