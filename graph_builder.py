import networkx as nx

def build_learning_graph(courses):
    """
    Builds a directed weighted graph.
    Nodes = skills
    Edges = courses, storing time/difficulty/cost separately
    so the custom Dijkstra can apply different weight combinations.
    """
    G = nx.DiGraph()

    for course in courses:
        targets = course["prerequisites"] if course["prerequisites"] else ["ROOT"]

        for prereq in targets:
            for taught_skill in course["teaches"]:
                G.add_edge(
                    prereq,
                    taught_skill,
                    course=course["name"],
                    time=course["time"],
                    difficulty=course["difficulty"],
                    cost=course.get("cost", 0),
                    # Default weight kept for any networkx fallback calls
                    weight=(course["time"] * 0.5) + (course["difficulty"] * 0.5)
                )
    return G