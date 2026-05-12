import argparse
import json

from data import courses
from graph_builder import build_learning_graph
from pathfinder import find_learning_path


WEIGHT_PRESETS = {
    "time": {"weight_time": 0.8, "weight_difficulty": 0.1, "weight_cost": 0.1},
    "cost": {"weight_time": 0.1, "weight_difficulty": 0.1, "weight_cost": 0.8},
    "balanced": {"weight_time": 0.4, "weight_difficulty": 0.3, "weight_cost": 0.3},
    "easy": {"weight_time": 0.1, "weight_difficulty": 0.8, "weight_cost": 0.1},
}

DEFAULT_DEMO_ROLES = [
    "Data Scientists",
    "Business Intelligence Analysts",
    "Information Security Analysts",
    "Information Security Engineers",
    "Software Developers",
    "Computer Network Architects",
]


def load_roles():
    with open("data/roles.json", "r", encoding="utf-8") as f:
        return json.load(f)


def find_role(roles, title):
    wanted = title.casefold()
    for role in roles:
        if role.get("title", "").casefold() == wanted:
            return role
    return None


def visible_steps(graph, path):
    steps = []
    hidden = []
    for start, end in zip(path or [], (path or [])[1:]):
        edge = graph.get_edge_data(start, end)
        course = edge.get("course", "")
        item = {
            "from": start,
            "to": end,
            "course": course,
            "time": edge.get("time", 0),
            "difficulty": edge.get("difficulty", 0),
            "cost": edge.get("cost", 0),
        }
        if course == "return_to_root" or course.startswith("prereq_check::"):
            hidden.append(item)
        else:
            steps.append(item)
    return steps, hidden


def parse_skills(value):
    return [s.strip() for s in value.split(",") if s.strip()]


def main():
    parser = argparse.ArgumentParser(
        description="Print STEMPath generated graph nodes and course steps for demo debugging."
    )
    parser.add_argument("--role", default="Data Scientists", help="Exact role title from data/roles.json.")
    parser.add_argument("--skills", default="", help="Comma-separated user skills, e.g. 'Git,Python'.")
    parser.add_argument(
        "--optimize",
        default="balanced",
        choices=sorted(WEIGHT_PRESETS),
        help="Optimization preference to test.",
    )
    parser.add_argument("--limit", type=int, default=6, help="Number of missing role skills to inspect.")
    parser.add_argument(
        "--targets",
        default="",
        help="Comma-separated target skills to inspect instead of the role's missing skills.",
    )
    parser.add_argument(
        "--all-demo-roles",
        action="store_true",
        help="Print the curated demo role set instead of one role.",
    )
    args = parser.parse_args()

    graph = build_learning_graph(courses)
    graph_skills = {n for n in graph.nodes if n != "ROOT" and not str(n).startswith("GATE::")}
    roles = load_roles()
    user_skills = parse_skills(args.skills)
    user_norm = {s.casefold() for s in user_skills}
    weights = WEIGHT_PRESETS[args.optimize]
    role_titles = DEFAULT_DEMO_ROLES if args.all_demo_roles else [args.role]

    print("=== STEMPath Pathway Debug ===")
    print(f"optimize_for: {args.optimize}")
    print(f"weights: {weights}")
    print(f"user_skills: {user_skills or []}")

    for title in role_titles:
        role = find_role(roles, title)
        if not role:
            print(f"\nRole not found: {title}")
            continue

        if args.targets:
            missing = [
                s for s in parse_skills(args.targets)
                if s in graph_skills and s.casefold() not in user_norm
            ]
        else:
            missing = [
                s for s in role.get("top_skills", [])
                if s in graph_skills and s.casefold() not in user_norm
            ][: args.limit]

        print(f"\nROLE: {role['title']} ({role['category']})")
        print(f"pathfindable_missing_skills: {missing}")

        for skill in missing:
            path, cost = find_learning_path(graph, user_skills, skill, **weights)
            print(f"\n  TARGET: {skill}")
            if not path:
                print("    no path found")
                continue

            steps, hidden = visible_steps(graph, path)
            print(f"    nodes: {' -> '.join(path)}")
            print(f"    weighted_cost: {round(cost, 1)}")
            print(f"    visible_step_count: {len(steps)}")
            for idx, step in enumerate(steps, start=1):
                print(
                    f"      {idx}. {step['from']} -> {step['to']} via {step['course']} "
                    f"(time={step['time']}, difficulty={step['difficulty']}, cost={step['cost']})"
                )
            if hidden:
                print("    hidden_edges:")
                for step in hidden:
                    print(f"      {step['from']} -> {step['to']} via {step['course']}")


if __name__ == "__main__":
    main()
