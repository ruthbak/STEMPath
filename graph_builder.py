"""
graph_builder.py
================
Constructs the directed weighted skill/resource graph used by Dijkstra's
algorithm to find optimal learning pathways in STEMPath.

Each node in the graph represents either a skill, a gate (multi-prerequisite
aggregator), or the special ROOT entry point. Each directed edge represents
a course or resource that, when traversed, teaches the destination skill.
"""

import networkx as nx


def build_learning_graph(courses):
    """
    Build a directed weighted graph from the STEMPath course/resource catalog.

    Graph structure
    ---------------
    The graph encodes three prerequisite patterns:

    1. No prerequisites:
            ROOT ──[course]──> taught_skill
       Skills with no prerequisites are reachable directly from ROOT,
       making them valid entry points for any learning path.

    2. One prerequisite:
            prereq ──[course]──> taught_skill
       The learner must hold the prerequisite skill before this edge
       can be traversed.

    3. Multiple prerequisites (GATE node):
            prereq_1 ──[prereq_check]──> GATE::course_name
            prereq_2 ──[prereq_check]──> GATE::course_name
            GATE::course_name ──[course]──> taught_skill
       All prerequisites must be satisfied before the gate node is
       reachable, enforcing hard dependency chains (e.g. Machine Learning
       requires both Python and Statistics).

    Return-to-ROOT edges
    --------------------
    Every non-ROOT, non-GATE skill node also has a zero-cost return edge
    back to ROOT. This allows Dijkstra's algorithm to learn one independent
    skill branch, return to ROOT, and then start a different branch —
    enabling multi-prerequisite paths to be satisfied incrementally.

    Edge weights
    ------------
    The default edge weight is computed as:
        weight = (time * 0.5) + (difficulty * 0.5)

    This default is overridden at query time by the user's optimize_for
    preference in find_learning_path(), which applies different multipliers
    to time, difficulty, and cost fields stored on each edge.

    Args:
        courses (list[dict]): The course/resource catalog from data.py.
            Each entry must contain:
                name          (str)       : Unique course/resource identifier.
                teaches       (list[str]) : Skills this course unlocks.
                prerequisites (list[str]) : Skills required before taking it.
                time          (int)       : Estimated hours to complete.
                difficulty    (int)       : Difficulty rating (1=easy, 3=hard).
                cost          (float)     : Monetary cost (0 = free).

    Returns:
        nx.DiGraph: A directed weighted graph where:
            - Nodes are skill names, GATE nodes, or 'ROOT'.
            - Edges carry course metadata (name, time, difficulty, cost,
              weight) used by the Dijkstra pathfinder.

    Example:
        >>> from data import courses
        >>> G = build_learning_graph(courses)
        >>> list(G.successors("ROOT"))
        ['Python Basics', 'SQL Basics', 'Git Basics', ...]
    """
    G = nx.DiGraph()

    for course in courses:
        prereqs = course["prerequisites"]
        targets = course["teaches"]

        edge_data = {
            "course":     course["name"],
            "time":       course["time"],
            "difficulty": course["difficulty"],
            "cost":       course.get("cost", 0),
            # Default composite weight — overridden by find_learning_path
            "weight":     (course["time"] * 0.5) + (course["difficulty"] * 0.5),
        }

        if len(prereqs) == 0:
            # No prerequisites: connect directly from ROOT
            for taught_skill in targets:
                G.add_edge("ROOT", taught_skill, **edge_data)

        elif len(prereqs) == 1:
            # Single prerequisite: direct edge from prereq to skill
            for taught_skill in targets:
                G.add_edge(prereqs[0], taught_skill, **edge_data)

        else:
            # Multiple prerequisites: funnel through a GATE node
            gate = f"GATE::{course['name']}"

            for prereq in prereqs:
                G.add_edge(
                    prereq,
                    gate,
                    course=f"prereq_check::{course['name']}",
                    time=0,
                    difficulty=0,
                    cost=0,
                    weight=0,
                )

            for taught_skill in targets:
                G.add_edge(gate, taught_skill, **edge_data)

    # Add zero-cost return edges from every skill back to ROOT so the
    # pathfinder can satisfy one prerequisite branch, return to ROOT,
    # and begin a different independent branch before reaching a GATE.
    for node in list(G.nodes):
        if node != "ROOT" and not str(node).startswith("GATE::"):
            G.add_edge(
                node,
                "ROOT",
                course="return_to_root",
                time=0,
                difficulty=0,
                cost=0,
                weight=0,
            )

    return G