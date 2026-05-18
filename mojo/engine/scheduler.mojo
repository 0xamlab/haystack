"""
scheduler.mojo — Task scheduling library. Zero Python imports.
Topological sort, priority scheduling, critical path analysis.

Public API:
  struct Task              — task with id, name, priority, estimated_ms, dependencies
  struct CriticalPathResult — result of critical_path (path + total_time)
  struct Scheduler         — manages tasks, execution order, completion tracking
    add_task        — add a new task
    schedule        — topological sort by deps, then priority within each level
    critical_path   — longest path through dependency graph + total time
    can_run         — check if all dependencies of a task are completed
    mark_complete   — mark a task as completed
    get_ready_tasks — tasks whose deps are all complete
    total_estimated_time — sum of all task estimated_ms
"""


# ── Task Struct ───────────────────────────────────────────────────────────────


struct Task(Copyable, Movable):
    """A schedulable task with dependencies.

    Fields:
        id:            Unique task identifier (auto-assigned by Scheduler).
        name:          Human-readable task name.
        priority:      Priority level (higher = more important).
        estimated_ms:  Estimated execution time in milliseconds.
        dependencies:  List of task IDs that must complete before this task.
        completed:     Whether this task has been completed.
    """

    var id: Int
    var name: String
    var priority: Int
    var estimated_ms: Int
    var dependencies: List[Int]
    var completed: Bool

    fn __init__(
        out self,
        id: Int,
        name: String,
        priority: Int,
        estimated_ms: Int,
        dependencies: List[Int],
    ):
        self.id = id
        self.name = name
        self.priority = priority
        self.estimated_ms = estimated_ms
        self.dependencies = dependencies.copy()
        self.completed = False


# ── CriticalPathResult Struct ─────────────────────────────────────────────────


struct CriticalPathResult(Copyable, Movable):
    """Result of critical path analysis.

    Fields:
        path:       List of task IDs on the critical path (in order).
        total_time: Total estimated time of the critical path in ms.
    """

    var path: List[Int]
    var total_time: Int

    fn __init__(out self, path: List[Int], total_time: Int):
        self.path = path.copy()
        self.total_time = total_time


# ── Scheduler Struct ──────────────────────────────────────────────────────────


struct Scheduler(Copyable, Movable):
    """Task scheduler with topological ordering and priority scheduling.

    Manages a collection of tasks, tracks completion, and provides
    scheduling algorithms including topological sort and critical path.
    """

    var tasks: List[Task]
    var execution_order: List[Int]

    fn __init__(out self):
        """Create an empty scheduler."""
        self.tasks = List[Task]()
        self.execution_order = List[Int]()

    fn add_task(
        mut self, name: String, priority: Int, est_ms: Int, deps: List[Int]
    ):
        """Add a new task to the scheduler.

        The task ID is auto-assigned as the current length of the tasks list.

        Args:
            name:     Human-readable task name.
            priority: Priority level (higher = more important).
            est_ms:   Estimated execution time in milliseconds.
            deps:     List of task IDs that must complete before this task.
        """
        var task_id = len(self.tasks)
        self.tasks.append(
            Task(task_id, name, priority, est_ms, deps)
        )

    fn schedule(mut self) -> List[Int]:
        """Schedule tasks using topological sort, breaking ties by priority.

        Uses Kahn's algorithm (BFS-based topological sort).
        Within the same topological level, tasks are sorted by
        priority (higher priority first).

        Returns:
            List of task IDs in scheduled execution order.
        """
        var n = len(self.tasks)
        if n == 0:
            self.execution_order = List[Int]()
            return List[Int]()

        # Compute in-degree: count how many valid deps each task has
        var in_degree = List[Int]()
        for i in range(n):
            in_degree.append(0)

        for i in range(n):
            var count = 0
            for d_idx in range(len(self.tasks[i].dependencies)):
                var dep = self.tasks[i].dependencies[d_idx]
                if dep >= 0 and dep < n:
                    count += 1
            in_degree[i] = count

        # Find initial ready tasks (in_degree == 0)
        var ready = List[Int]()
        for i in range(n):
            if in_degree[i] == 0:
                ready.append(i)

        var order = List[Int]()

        while len(ready) > 0:
            # Sort ready tasks by priority (descending) using insertion sort
            for i in range(1, len(ready)):
                var j = i
                while j > 0 and self.tasks[ready[j]].priority > self.tasks[ready[j - 1]].priority:
                    # Swap
                    var tmp = ready[j]
                    ready[j] = ready[j - 1]
                    ready[j - 1] = tmp
                    j -= 1

            # Take the highest priority task
            var current = ready[0]
            # Remove first element by shifting
            var new_ready = List[Int]()
            for i in range(1, len(ready)):
                new_ready.append(ready[i])
            ready = new_ready^

            order.append(current)

            # For each task that depends on current, decrement in_degree
            for i in range(n):
                for d_idx in range(len(self.tasks[i].dependencies)):
                    if self.tasks[i].dependencies[d_idx] == current:
                        in_degree[i] -= 1
                        if in_degree[i] == 0:
                            ready.append(i)
                        break  # Each dep listed once

        self.execution_order = order.copy()
        return order^

    fn critical_path(self) -> CriticalPathResult:
        """Find the critical path — longest path through the dependency graph.

        Uses dynamic programming: for each task (processed in topological order),
        compute the longest path ending at that task.

        Returns:
            CriticalPathResult with path (List[Int]) and total_time (Int).
        """
        var n = len(self.tasks)
        if n == 0:
            return CriticalPathResult(List[Int](), 0)

        # Compute topological order using Kahn's algorithm (inline)
        var in_degree = List[Int]()
        for i in range(n):
            in_degree.append(0)

        for i in range(n):
            for d_idx in range(len(self.tasks[i].dependencies)):
                var dep = self.tasks[i].dependencies[d_idx]
                if dep >= 0 and dep < n:
                    in_degree[i] += 1

        var queue = List[Int]()
        for i in range(n):
            if in_degree[i] == 0:
                queue.append(i)

        var topo_order = List[Int]()
        var head = 0
        while head < len(queue):
            var curr = queue[head]
            head += 1
            topo_order.append(curr)

            for i in range(n):
                for d_idx in range(len(self.tasks[i].dependencies)):
                    if self.tasks[i].dependencies[d_idx] == curr:
                        in_degree[i] -= 1
                        if in_degree[i] == 0:
                            queue.append(i)
                        break

        # DP: dist[i] = longest path time ending at task i
        var dist = List[Int]()
        var prev = List[Int]()
        for i in range(n):
            dist.append(0)
            prev.append(-1)

        for t_idx in range(len(topo_order)):
            var t = topo_order[t_idx]
            var task_time = self.tasks[t].estimated_ms
            # Check all dependencies
            var max_dep_dist = 0
            var best_dep = -1
            for d_idx in range(len(self.tasks[t].dependencies)):
                var dep = self.tasks[t].dependencies[d_idx]
                if dep >= 0 and dep < n:
                    if dist[dep] > max_dep_dist:
                        max_dep_dist = dist[dep]
                        best_dep = dep
            dist[t] = max_dep_dist + task_time
            prev[t] = best_dep

        # Find task with maximum dist
        var max_dist = 0
        var end_task = 0
        for i in range(n):
            if dist[i] > max_dist:
                max_dist = dist[i]
                end_task = i

        # Backtrack to build the path
        var path = List[Int]()
        var current = end_task
        while current != -1:
            path.append(current)
            current = prev[current]

        # Reverse the path
        var reversed_path = List[Int]()
        for i in range(len(path)):
            reversed_path.append(path[len(path) - 1 - i])

        return CriticalPathResult(reversed_path^, max_dist)

    fn can_run(self, task_id: Int) -> Bool:
        """Check if a task can run (all dependencies completed).

        Args:
            task_id: The task ID to check.

        Returns:
            True if all dependencies of the task are completed.
        """
        if task_id < 0 or task_id >= len(self.tasks):
            return False

        for d_idx in range(len(self.tasks[task_id].dependencies)):
            var dep = self.tasks[task_id].dependencies[d_idx]
            if dep >= 0 and dep < len(self.tasks):
                if not self.tasks[dep].completed:
                    return False
        return True

    fn mark_complete(mut self, task_id: Int):
        """Mark a task as completed.

        Args:
            task_id: The task ID to mark as complete.
        """
        if task_id >= 0 and task_id < len(self.tasks):
            self.tasks[task_id].completed = True

    fn get_ready_tasks(self) -> List[Int]:
        """Get all tasks that are ready to run.

        A task is ready if:
        - It is not yet completed.
        - All of its dependencies are completed.

        Returns:
            List of task IDs that are ready to run.
        """
        var ready = List[Int]()
        for i in range(len(self.tasks)):
            if not self.tasks[i].completed and self.can_run(i):
                ready.append(i)
        return ready^

    fn total_estimated_time(self) -> Int:
        """Sum of all task estimated_ms.

        Returns:
            Total estimated time in milliseconds.
        """
        var total = 0
        for i in range(len(self.tasks)):
            total += self.tasks[i].estimated_ms
        return total
