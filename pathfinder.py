import heapq


def _norm(skill: str) -> str:
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
    Custom Dijkstra over the learning graph.

    Gate nodes require ALL prerequisite skills to already be in the
    acquired skill set.

    State = (current_node, acquired_skills_set)
    """
    if not graph.has_node(target_skill):
        return None, float("inf")

    initial_acquired = {_norm(s) for s in current_skills if isinstance(s, str)}
    relevant_nodes = {"ROOT", target_skill}
    stack = [target_skill]
    while stack:
        node = stack.pop()
        for pred in graph.predecessors(node):
            if pred not in relevant_nodes:
                relevant_nodes.add(pred)
                stack.append(pred)

    start_nodes = []
    for s in current_skills:
        if graph.has_node(s) and s not in start_nodes:
            start_nodes.append(s)

    if "ROOT" not in start_nodes:
        start_nodes.append("ROOT")

    best_path = None
    best_cost = float("inf")

    for start in start_nodes:
        start_skills = set(initial_acquired)

        if start != "ROOT" and not str(start).startswith("GATE::"):
            start_skills.add(_norm(start))

        heap = [(0, start, [start], frozenset(start_skills))]
        visited = {}

        while heap:
            cost, current, path, skills_so_far = heapq.heappop(heap)

            state_key = (current, skills_so_far)
            if state_key in visited and visited[state_key] <= cost:
                continue
            visited[state_key] = cost

            if current == target_skill:
                if cost < best_cost:
                    best_cost = cost
                    best_path = path
                break

            for neighbor in graph.successors(current):
                if neighbor not in relevant_nodes:
                    continue

                # Gate node: all non-gate predecessors must already be acquired
                if str(neighbor).startswith("GATE::"):
                    required = {
                        _norm(pred)
                        for pred in graph.predecessors(neighbor)
                        if pred != "ROOT" and not str(pred).startswith("GATE::")
                    }
                    if not required.issubset(skills_so_far):
                        continue

                edge = graph.get_edge_data(current, neighbor)
                composite = (
                    edge.get("time", 0) * weight_time
                    + edge.get("difficulty", 0) * weight_difficulty
                    + edge.get("cost", 0) * weight_cost
                )

                new_skills = set(skills_so_far)

                # Only real skills should be added to acquired-skills state
                if neighbor != "ROOT" and not str(neighbor).startswith("GATE::"):
                    new_skills.add(_norm(neighbor))

                heapq.heappush(
                    heap,
                    (cost + composite, neighbor, path + [neighbor], frozenset(new_skills)),
                )

    return best_path, best_cost
