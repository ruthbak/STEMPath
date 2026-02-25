import heapq

def find_learning_path(graph, current_skills, target_skill,
                       weight_time=0.5, weight_difficulty=0.3, weight_cost=0.2):
    """
    Custom Dijkstra implementation using a min-heap priority queue.
    Supports multi-criteria weighted edges: time, difficulty, cost.
    O((V + E) log V) time complexity.
    """
    best_path = None
    best_cost = float("inf")

    starting_nodes = list(current_skills) + ["ROOT"]

    for start in starting_nodes:
        if not graph.has_node(start) or not graph.has_node(target_skill):
            continue

        # Priority queue entries: (cumulative_cost, node, path_so_far)
        heap = [(0, start, [start])]
        visited = {}

        while heap:
            cost, current, path = heapq.heappop(heap)

            # Already found a cheaper way to this node
            if current in visited and visited[current] <= cost:
                continue
            visited[current] = cost

            if current == target_skill:
                if cost < best_cost:
                    best_cost = cost
                    best_path = path
                break

            for neighbor in graph.successors(current):
                if neighbor in visited:
                    continue
                edge = graph.get_edge_data(current, neighbor)

                # Multi-criteria composite weight
                composite = (
                    edge.get("time", 0)       * weight_time +
                    edge.get("difficulty", 0) * weight_difficulty +
                    edge.get("cost", 0)       * weight_cost
                )

                heapq.heappush(heap,
                    (cost + composite, neighbor, path + [neighbor]))

    return best_path, best_cost