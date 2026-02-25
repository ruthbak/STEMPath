from flask import Flask, request, jsonify
from data import courses
from graph_builder import build_learning_graph
from pathfinder import find_learning_path

app = Flask(__name__)
graph = build_learning_graph(courses)

@app.route("/learning-path", methods=["POST"])
def learning_path():
    data = request.json

    current_skills = data["current_skills"]
    target_skill = data["target_skill"]

    path, cost = find_learning_path(graph, current_skills, target_skill)

    return jsonify({
        "path": path,
        "total_cost": cost
    })

if __name__ == "__main__":
    app.run(debug=True)