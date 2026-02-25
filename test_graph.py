from data import courses
from graph_builder import build_learning_graph

graph = build_learning_graph(courses)

print("Nodes in graph:")
print(graph.nodes())

print("\nEdges in graph:")
for u, v, data in graph.edges(data=True):
    print(f"{u} -> {v} | weight={data['weight']} | course={data['course']}")