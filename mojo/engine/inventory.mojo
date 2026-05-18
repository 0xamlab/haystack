"""
inventory.mojo — Inventory Optimization. Zero Python imports.

Replaces custom Python supply chain optimization with pure Mojo
implementations of EOQ, safety stock, newsvendor model, ABC
classification, and inventory performance metrics.

Public API:
  eoq                     — Economic Order Quantity
  reorder_point           — Reorder point calculation
  safety_stock            — Safety stock from z-score
  total_inventory_cost    — Total annual inventory cost
  newsvendor_qty          — Newsvendor critical ratio quantity
  service_level           — Normal CDF approximation from z-score
  abc_classify            — ABC classification by value
  days_of_supply          — Days of supply
  inventory_turnover      — Inventory turnover ratio
  fill_rate               — Order fill rate
  periodic_review_order   — Periodic review order-up-to quantity
"""

from std.math import sqrt, log, abs as fabs, exp


# ── Constants ────────────────────────────────────────────────────────────────


comptime PI: Float64 = 3.141592653589793
comptime SQRT_2: Float64 = 1.4142135623730951


# ── eoq ──────────────────────────────────────────────────────────────────────


fn eoq(demand: Float64, order_cost: Float64, holding_cost: Float64) -> Float64:
    """Economic Order Quantity: sqrt(2*D*S/H)."""
    if holding_cost <= 0.0:
        return 0.0
    return sqrt(2.0 * demand * order_cost / holding_cost)


# ── reorder_point ────────────────────────────────────────────────────────────


fn reorder_point(demand_rate: Float64, lead_time: Float64, safety_stock: Float64) -> Float64:
    """Reorder Point = demand_rate * lead_time + safety_stock."""
    return demand_rate * lead_time + safety_stock


# ── safety_stock ─────────────────────────────────────────────────────────────


fn safety_stock(z_score: Float64, demand_std: Float64, lead_time: Float64) -> Float64:
    """Safety Stock = z * σ_d * sqrt(LT)."""
    return z_score * demand_std * sqrt(lead_time)


# ── total_inventory_cost ─────────────────────────────────────────────────────


fn total_inventory_cost(demand: Float64, order_qty: Float64, order_cost: Float64, holding_cost: Float64) -> Float64:
    """Total Inventory Cost = (D/Q)*S + (Q/2)*H."""
    if order_qty <= 0.0:
        return 0.0
    return (demand / order_qty) * order_cost + (order_qty / 2.0) * holding_cost


# ── _normal_cdf_approx ──────────────────────────────────────────────────────


fn _normal_cdf_approx(z: Float64) -> Float64:
    """Approximate standard normal CDF using Abramowitz & Stegun formula."""
    if z < -8.0:
        return 0.0
    if z > 8.0:
        return 1.0
    var x = z
    var neg = False
    if x < 0.0:
        neg = True
        x = -x
    # Constants for approximation
    var b0: Float64 = 0.2316419
    var b1: Float64 = 0.319381530
    var b2: Float64 = -0.356563782
    var b3: Float64 = 1.781477937
    var b4: Float64 = -1.821255978
    var b5: Float64 = 1.330274429
    var t = 1.0 / (1.0 + b0 * x)
    var pdf = exp(-0.5 * x * x) / sqrt(2.0 * PI)
    var poly = t * (b1 + t * (b2 + t * (b3 + t * (b4 + t * b5))))
    var cdf = 1.0 - pdf * poly
    if neg:
        cdf = 1.0 - cdf
    return cdf


# ── _normal_quantile_approx ─────────────────────────────────────────────────


fn _normal_quantile_approx(p: Float64) -> Float64:
    """Approximate inverse normal CDF (quantile) using rational approx."""
    # Clamp
    var pp = p
    if pp <= 0.0:
        pp = 1e-10
    if pp >= 1.0:
        pp = 1.0 - 1e-10
    # Beasley-Springer-Moro approximation
    var y = pp - 0.5
    if fabs(y) < 0.42:
        var r = y * y
        var x = y * ((((-25.44106049637 * r + 41.39119773534) * r - 18.61500062529) * r + 2.506628277459) /
            ((((3.13082909833 * r - 21.06224101826) * r + 23.08336743743) * r - 8.47351093090) * r + 1.0))
        return x
    else:
        var r: Float64
        if y > 0.0:
            r = 1.0 - pp
        else:
            r = pp
        var s = log(-log(r))
        var x = 0.3374754822726147 + s * (0.9761690190917186 + s * (0.1607979714918209 +
            s * (0.0276438810333863 + s * (0.0038405729373609 + s * (0.0003951896511919 +
            s * (0.0000321767881768 + s * (0.0000002888167364 + s * 0.0000003960315187)))))))
        if y < 0.0:
            x = -x
        return x


# ── newsvendor_qty ───────────────────────────────────────────────────────────


fn newsvendor_qty(mean_demand: Float64, std_demand: Float64, cost_under: Float64, cost_over: Float64) -> Float64:
    """Newsvendor: Q* = mean + z*std where z = Φ^-1(Cu/(Cu+Co)).
    Uses normal CDF inverse approximation.
    """
    var total = cost_under + cost_over
    if total <= 0.0:
        return mean_demand
    var cr = cost_under / total  # Critical ratio
    var z = _normal_quantile_approx(cr)
    return mean_demand + z * std_demand


# ── service_level ────────────────────────────────────────────────────────────


fn service_level(z_score: Float64) -> Float64:
    """Approximate service level from z-score using normal CDF approximation."""
    return _normal_cdf_approx(z_score)


# ── abc_classify ─────────────────────────────────────────────────────────────


fn abc_classify(values: List[Float64]) -> List[Int]:
    """ABC classification: top 20% value → A(0), next 30% → B(1), rest → C(2).
    Sort items by value descending, then assign based on cumulative value share.
    """
    var n = len(values)
    if n == 0:
        return List[Int]()

    # Create index array sorted by value descending
    var idx = List[Int]()
    for i in range(n):
        idx.append(i)
    # Insertion sort descending
    for i in range(1, n):
        var key = idx[i]
        var key_val = values[key]
        var j = i - 1
        while j >= 0 and values[idx[j]] < key_val:
            idx[j + 1] = idx[j]
            j -= 1
        idx[j + 1] = key

    # Compute total value
    var total: Float64 = 0.0
    for i in range(n):
        total += values[i]

    # Assign classes based on cumulative percentage
    var result = List[Int]()
    for _ in range(n):
        result.append(2)  # Default C
    var cumulative: Float64 = 0.0
    for i in range(n):
        var orig_idx = idx[i]
        cumulative += values[orig_idx]
        var pct = cumulative / total if total > 0.0 else 1.0
        if pct <= 0.20:
            result[orig_idx] = 0  # A
        elif pct <= 0.50:
            result[orig_idx] = 1  # B
        else:
            result[orig_idx] = 2  # C
    return result^


# ── days_of_supply ───────────────────────────────────────────────────────────


fn days_of_supply(inventory: Float64, daily_demand: Float64) -> Float64:
    """Days of supply = inventory / daily_demand."""
    if daily_demand <= 0.0:
        return 0.0
    return inventory / daily_demand


# ── inventory_turnover ───────────────────────────────────────────────────────


fn inventory_turnover(cogs: Float64, avg_inventory: Float64) -> Float64:
    """Inventory turnover = COGS / avg_inventory."""
    if avg_inventory <= 0.0:
        return 0.0
    return cogs / avg_inventory


# ── fill_rate ────────────────────────────────────────────────────────────────


fn fill_rate(orders_filled: Int, total_orders: Int) -> Float64:
    """Fill rate = orders_filled / total_orders."""
    if total_orders <= 0:
        return 0.0
    return Float64(orders_filled) / Float64(total_orders)


# ── periodic_review_order ────────────────────────────────────────────────────


fn periodic_review_order(target: Float64, on_hand: Float64, on_order: Float64) -> Float64:
    """Order up to target: max(0, target - on_hand - on_order)."""
    var qty = target - on_hand - on_order
    if qty < 0.0:
        return 0.0
    return qty
