import networkx as nx

def build_learning_graph(courses):
    """
    Builds a directed weighted graph.

    - No prerequisites:
        ROOT -> taught_skill
    - One prerequisite:
        prereq -> taught_skill
    - Multiple prerequisites:
        prereq_i -> GATE::course_name -> taught_skill

    Also adds zero-cost return edges from each skill back to ROOT so the
    planner can learn another independent branch before unlocking a gate.
    """
    G = nx.DiGraph()

    for course in courses:
        prereqs = course["prerequisites"]
        targets = course["teaches"]

        edge_data = {
            "course": course["name"],
            "time": course["time"],
            "difficulty": course["difficulty"],
            "cost": course.get("cost", 0),
            "weight": (course["time"] * 0.5) + (course["difficulty"] * 0.5),
        }

        if len(prereqs) == 0:
            for taught_skill in targets:
                G.add_edge("ROOT", taught_skill, **edge_data)

        elif len(prereqs) == 1:
            for taught_skill in targets:
                G.add_edge(prereqs[0], taught_skill, **edge_data)

        else:
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

    # Allow the search to return to ROOT after gaining any skill,
    # so it can learn another independent prerequisite branch.
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