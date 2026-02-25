from data import courses
from graph_builder import build_graph, build_learning_graph
from pathfinder import find_learning_path

graph = build_learning_graph(courses) 

current_skills = ["Python"]
target_skill = "TensorFlow"

path, cost = find_learning_path(graph, current_skills, target_skill)

print("Path:", path)
print("Cost:", cost)