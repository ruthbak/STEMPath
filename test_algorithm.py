from data import courses
from graph_builder import build_learning_graph
from pathfinder import find_learning_path

graph = build_learning_graph(courses)


def run_case(current_skills, target_skill):
    path, cost = find_learning_path(graph, current_skills, target_skill)
    print("=" * 60)
    print("Current skills:", current_skills)
    print("Target skill:", target_skill)
    print("Path:", path)
    print("Cost:", cost)


# Should work because Python is already owned, then Statistics, then ML, then TensorFlow
run_case(["Python"], "TensorFlow")

# This is the important test:
# should now work from empty by learning Python and SQL before Data Visualization
run_case([], "Data Visualization")

# Another multi-step case from empty
run_case([], "Machine Learning")