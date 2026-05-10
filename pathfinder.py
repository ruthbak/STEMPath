"""
pathfinder.py
=============
Implements a custom Dijkstra's shortest-path algorithm over the STEMPath
skill/resource graph to find the minimum-cost learning pathway from a
user's current skills to a target skill gap.

Algorithm overview
------------------
Standard Dijkstra operates over static nodes. STEMPath extends this with
a stateful formulation where each node in the priority queue also carries
the set of skills acquired so far. This is necessary because:

  1. GATE nodes require ALL predecessor skills to be acquired before they
     can be traversed — a constraint that depends on accumulated state,
     not just the current node.

  2. The user may already hold some prerequisite skills, meaning the
     effective starting point varies per user and cannot be hard-coded.

State representation:
    (cost, current_node, path_so_far, acquired_skills_frozenset)

Time complexity: O((V + E) log V) where V = skill nodes, E = course edges.
For the current graph size this runs in effectively constant time (<10ms).
"""

import heapq


def _norm(skill: str) -> str:
    """
    Normalise a skill name for case-insensitive set membership checks.

    Args:
        skill (str): Raw skill name.

    Returns:
        str: Lowercase, stripped skill name.
    """
    return skill.strip().lower()


def find_learning_path(
    graph,
    current_skills,
    target_skill,
    weight_time=0.5,
    weight_difficulty=0.3,
    weight_cost=0.2,
):
    """
    Find the minimum-cost learning path from the user's current skills
    to a target skill gap using a stateful Dijkstra's algorithm.

    The algorithm is initialised from every skill the user already holds
    (plus ROOT), allowing it to immediately continue from any node in the
    graph rather than always starting from ROOT. This means a user who
    already knows Python will skip the Python intro nodes and jump
    directly to the next step in their path.

    Edge weight formula
    -------------------
    Each edge is scored as a weighted combination of three cost dimensions:

        composite = (time * weight_time)
                  + (difficulty * weight_difficulty)
                  + (cost * weight_cost)

    The three weight parameters correspond to the user's optimize_for
    preference set in their profile:
        - "time"     : weight_time=0.8, weight_difficulty=0.1, weight_cost=0.1
        - "cost"     : weight_time=0.1, weight_difficulty=0.1, weight_cost=0.8
        - "easy"     : weight_time=0.1, weight_difficulty=0.8, weight_cost=0.1
        - "balanced" : weight_time=0.4, weight_difficulty=0.3, weight_cost=0.3

    GATE node handling
    ------------------
    GATE nodes (prefixed "GATE::") represent courses with multiple
    prerequisites. Before a GATE node can be entered, ALL of its
    non-ROOT predecessor skills must be present in the acquired_skills
    set. Paths that cannot satisfy this constraint are pruned from the
    search. The return-to-ROOT edges in the graph allow Dijkstra to
    acquire prerequisite skills in separate branches before a gate is
    attempted.

    Visited state
    -------------
    The visited dictionary is keyed by (current_node, acquired_skills_frozenset)
    rather than just current_node. This prevents suboptimal paths from
    being discarded simply because a node was visited with a different
    skill set — a requirement of the stateful formulation.

    Args:
        graph (nx.DiGraph): The directed weighted graph built by
            build_learning_graph() in graph_builder.py.
        current_skills (list[str]): Skills the user already holds.
            Used to initialise the search from multiple starting nodes.
        target_skill (str): The skill gap the user needs to reach.
            Must be a node name present in the graph.
        weight_time (float): Weight applied to the time cost dimension.
            Default 0.5.
        weight_difficulty (float): Weight applied to the difficulty
            cost dimension. Default 0.3.
        weight_cost (float): Weight applied to the monetary cost
            dimension. Default 0.2.

    Returns:
        tuple[list[str] | None, float]:
            - path : Ordered list of node names from a start node to
                     target_skill, or None if no path exists.
            - cost : Total weighted cost of the path, or inf if no
                     path was found.

    Example:
        >>> path, cost = find_learning_path(
        ...     graph, ["Python", "SQL"], "Machine Learning",
        ...     weight_time=0.4, weight_difficulty=0.3, weight_cost=0.3
        ... )
        >>> path
        ['Python', 'Statistics', 'GATE::ML Basics', 'Machine Learning']
        >>> cost
        42.5
    """
    if not graph.has_node(target_skill):
        return None, float("inf")

    # Build the normalised set of skills the user already holds
    initial_acquired = {_norm(s) for s in current_skills if isinstance(s, str)}

    # Collect valid graph nodes the user can start from
    start_nodes = []
    for s in current_skills:
        if graph.has_node(s) and s not in start_nodes:
            start_nodes.append(s)

    # ROOT is always a valid starting point for skills with no prerequisites
    if "ROOT" not in start_nodes:
        start_nodes.append("ROOT")

    best_path = None
    best_cost = float("inf")

    # Run Dijkstra from each valid starting node and keep the global best
    for start in start_nodes:
        start_skills = set(initial_acquired)

        # If starting from an already-acquired skill node, include it
        if start != "ROOT" and not str(start).startswith("GATE::"):
            start_skills.add(_norm(start))

        # Priority queue: (cost, current_node, path, acquired_skills)
        heap = [(0, start, [start], frozenset(start_skills))]

        # Visited keyed by (node, skills) to handle stateful traversal
        visited = {}

        while heap:
            cost, current, path, skills_so_far = heapq.heappop(heap)

            state_key = (current, skills_so_far)
            if state_key in visited and visited[state_key] <= cost:
                continue
            visited[state_key] = cost

            # Target reached — record if this is the best path found
            if current == target_skill:
                if cost < best_cost:
                    best_cost = cost
                    best_path = path
                break

            for neighbor in graph.successors(current):
                # GATE check: all prerequisite skills must be acquired
                if str(neighbor).startswith("GATE::"):
                    required = {
                        _norm(pred)
                        for pred in graph.predecessors(neighbor)
                        if pred != "ROOT" and not str(pred).startswith("GATE::")
                    }
                    if not required.issubset(skills_so_far):
                        continue  # Prune: prerequisites not yet satisfied

                edge = graph.get_edge_data(current, neighbor)

                # Compute weighted composite cost for this edge
                composite = (
                    edge.get("time", 0)       * weight_time
                    + edge.get("difficulty", 0) * weight_difficulty
                    + edge.get("cost", 0)       * weight_cost
                )

                new_skills = set(skills_so_far)

                # Add real skill nodes to acquired set (not ROOT or GATE)
                if neighbor != "ROOT" and not str(neighbor).startswith("GATE::"):
                    new_skills.add(_norm(neighbor))

                heapq.heappush(
                    heap,
                    (cost + composite, neighbor, path + [neighbor], frozenset(new_skills)),
                )

    return best_path, best_cost