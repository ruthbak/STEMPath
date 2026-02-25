# graph_builder.py
import networkx as nx

def build_learning_graph(courses):
    """
    Builds a directed weighted graph:
    Nodes = skills
    Edges = courses that move you from prerequisite → taught skill
    """
    G = nx.DiGraph() #initializing empty graph

    for course in courses:
        # simple, explainable weight formula
        weight = (course["time"] * 0.5) + (course["difficulty"] * 0.5)

        for prereq in course["prerequisites"]:
            for taught_skill in course["teaches"]:
                G.add_edge(
                    prereq,
                    taught_skill,
                    weight=weight,
                    course=course["name"]
                )
    return G