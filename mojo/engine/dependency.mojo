"""
dependency.mojo — Dependency resolution. Zero Python imports.

Replaces pip/poetry resolver basics with pure Mojo implementations for
topological sorting, cycle detection, transitive dependency resolution,
conflict finding, and install planning.

Packages as Int IDs, versions as Int. Dependencies as List[List[Int]]
where each dep is [package_id, depends_on_package].

Public API:
  resolve_order     — Topological sort of package install order
  has_cycle         — Detect dependency cycle
  transitive_deps   — All transitive dependencies of a package
  dependency_depth   — Maximum dependency chain depth
  is_compatible      — Check version within [min, max]
  find_conflicts     — Find conflicting version requirements
  install_plan       — Minimal install plan for a target package
  reverse_deps       — Packages that depend on a given package
"""


# ── resolve_order ─────────────────────────────────────────────────────────────


fn resolve_order(n_packages: Int, dependencies: List[List[Int]]) -> List[Int]:
    """Topological sort (Kahn's algorithm).

    dependencies[i] = [package, depends_on_package].
    Returns install order (deps first) or empty list if cycle exists.
    """
    # Build adjacency list and in-degree
    var in_deg = List[Int]()
    for _ in range(n_packages):
        in_deg.append(0)

    var adj = List[List[Int]]()
    for _ in range(n_packages):
        adj.append(List[Int]())

    for i in range(len(dependencies)):
        if len(dependencies[i]) >= 2:
            var pkg = dependencies[i][0]
            var depends_on = dependencies[i][1]
            if pkg >= 0 and pkg < n_packages and depends_on >= 0 and depends_on < n_packages:
                adj[depends_on].append(pkg)
                in_deg[pkg] += 1

    # Collect nodes with in-degree 0
    var queue = List[Int]()
    for i in range(n_packages):
        if in_deg[i] == 0:
            queue.append(i)

    var result = List[Int]()
    var head = 0
    while head < len(queue):
        var node = queue[head]
        head += 1
        result.append(node)
        for j in range(len(adj[node])):
            var nb = adj[node][j]
            in_deg[nb] -= 1
            if in_deg[nb] == 0:
                queue.append(nb)

    if len(result) != n_packages:
        return List[Int]()  # cycle detected
    return result^


# ── has_cycle ─────────────────────────────────────────────────────────────────


fn has_cycle(n_packages: Int, dependencies: List[List[Int]]) -> Bool:
    """Detect dependency cycle using topological sort."""
    var order = resolve_order(n_packages, dependencies)
    return len(order) == 0


# ── transitive_deps ───────────────────────────────────────────────────────────


fn transitive_deps(package: Int, dependencies: List[List[Int]]) -> List[Int]:
    """All transitive dependencies of a package (BFS)."""
    # Find max id
    var max_id = package + 1
    for i in range(len(dependencies)):
        if len(dependencies[i]) >= 2:
            if dependencies[i][0] + 1 > max_id:
                max_id = dependencies[i][0] + 1
            if dependencies[i][1] + 1 > max_id:
                max_id = dependencies[i][1] + 1

    # Build direct dependency map: package -> list of what it depends on
    var direct = List[List[Int]]()
    for _ in range(max_id):
        direct.append(List[Int]())

    for i in range(len(dependencies)):
        if len(dependencies[i]) >= 2:
            direct[dependencies[i][0]].append(dependencies[i][1])

    # BFS from package
    var visited = List[Bool]()
    for _ in range(max_id):
        visited.append(False)

    var queue = List[Int]()
    var result = List[Int]()

    if package < 0 or package >= max_id:
        return result^

    # Seed with direct deps
    for j in range(len(direct[package])):
        var d = direct[package][j]
        if not visited[d]:
            visited[d] = True
            queue.append(d)
            result.append(d)

    var head = 0
    while head < len(queue):
        var curr = queue[head]
        head += 1
        if curr < max_id:
            for j in range(len(direct[curr])):
                var d = direct[curr][j]
                if not visited[d]:
                    visited[d] = True
                    queue.append(d)
                    result.append(d)

    return result^


# ── dependency_depth ──────────────────────────────────────────────────────────


fn dependency_depth(package: Int, dependencies: List[List[Int]]) -> Int:
    """Maximum dependency chain depth (DFS)."""
    var max_id = package + 1
    for i in range(len(dependencies)):
        if len(dependencies[i]) >= 2:
            if dependencies[i][0] + 1 > max_id:
                max_id = dependencies[i][0] + 1
            if dependencies[i][1] + 1 > max_id:
                max_id = dependencies[i][1] + 1

    var direct = List[List[Int]]()
    for _ in range(max_id):
        direct.append(List[Int]())

    for i in range(len(dependencies)):
        if len(dependencies[i]) >= 2:
            direct[dependencies[i][0]].append(dependencies[i][1])

    if package < 0 or package >= max_id:
        return 0

    # Iterative DFS with depth tracking
    var stack_node = List[Int]()
    var stack_depth = List[Int]()
    stack_node.append(package)
    stack_depth.append(0)
    var max_depth = 0

    while len(stack_node) > 0:
        var node = stack_node.pop()
        var depth = stack_depth.pop()
        if depth > max_depth:
            max_depth = depth
        if node < max_id:
            for j in range(len(direct[node])):
                stack_node.append(direct[node][j])
                stack_depth.append(depth + 1)

    return max_depth


# ── is_compatible ─────────────────────────────────────────────────────────────


fn is_compatible(version: Int, min_ver: Int, max_ver: Int) -> Bool:
    """Check if version is within [min_ver, max_ver]."""
    return version >= min_ver and version <= max_ver


# ── find_conflicts ────────────────────────────────────────────────────────────


fn find_conflicts(requirements: List[List[Int]]) -> List[List[Int]]:
    """Find conflicting requirements.

    Each requirement is [package, min_ver, max_ver].
    Returns pairs of indices that conflict (same package, non-overlapping ranges).
    """
    var conflicts = List[List[Int]]()
    var n = len(requirements)
    for i in range(n):
        if len(requirements[i]) < 3:
            continue
        for j in range(i + 1, n):
            if len(requirements[j]) < 3:
                continue
            # Same package?
            if requirements[i][0] == requirements[j][0]:
                var min_i = requirements[i][1]
                var max_i = requirements[i][2]
                var min_j = requirements[j][1]
                var max_j = requirements[j][2]
                # Non-overlapping ranges
                if max_i < min_j or max_j < min_i:
                    var pair = List[Int]()
                    pair.append(i)
                    pair.append(j)
                    conflicts.append(pair^)
    return conflicts^


# ── install_plan ──────────────────────────────────────────────────────────────


fn install_plan(
    n_packages: Int, deps: List[List[Int]], target: Int
) -> List[Int]:
    """Minimal install plan: packages needed to install target, in order.

    Returns topologically sorted list of packages needed (including target).
    """
    # Get all transitive deps
    var all_deps = transitive_deps(target, deps)

    # Include target
    var needed = List[Bool]()
    for _ in range(n_packages):
        needed.append(False)

    if target >= 0 and target < n_packages:
        needed[target] = True
    for i in range(len(all_deps)):
        var d = all_deps[i]
        if d >= 0 and d < n_packages:
            needed[d] = True

    # Get full topological order and filter
    var full_order = resolve_order(n_packages, deps)
    var plan = List[Int]()
    for i in range(len(full_order)):
        var pkg = full_order[i]
        if needed[pkg]:
            plan.append(pkg)

    return plan^


# ── reverse_deps ──────────────────────────────────────────────────────────────


fn reverse_deps(package: Int, dependencies: List[List[Int]]) -> List[Int]:
    """Packages that depend on the given package."""
    var result = List[Int]()
    var seen = List[Int]()
    for i in range(len(dependencies)):
        if len(dependencies[i]) >= 2 and dependencies[i][1] == package:
            var pkg = dependencies[i][0]
            # Check not already added
            var found = False
            for k in range(len(seen)):
                if seen[k] == pkg:
                    found = True
                    break
            if not found:
                result.append(pkg)
                seen.append(pkg)
    return result^
