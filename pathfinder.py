import networkx as nx

def find_learning_path(graph, current_skills, target_skill, max_time=None):
    best_path = None
    best_cost = float("inf")

    for skill in current_skills:
        try:
            path = nx.dijkstra_path(graph, skill, target_skill, weight="weight")
            cost = nx.dijkstra_path_length(graph, skill, target_skill, weight="weight")

            # NEW: calculate total time
            total_time = 0
            for i in range(len(path) - 1):
                edge_data = graph.get_edge_data(path[i], path[i+1])
                total_time += edge_data["weight"]  # proxy for time

            # Enforce constraint
            if max_time is not None and total_time > max_time:
                continue

            if cost < best_cost:
                best_cost = cost
                best_path = path

        except nx.NetworkXNoPath:
            continue

    return best_path, best_cost