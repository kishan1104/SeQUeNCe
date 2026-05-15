import json
from itertools import combinations

nodes = []

# Create nodes
seed = 0
for i in range(5):
    main = f"N{i}"
    child1 = f"N{i}0"
    child2 = f"N{i}1"

    for name in [main, child1, child2]:
        nodes.append({
            "name": name,
            "type": "DPSNode",
            "seed": seed,
            "memo_size": 50
        })
        seed += 1

qconnections = []

# Backbone quantum links
for i in range(4):
    qconnections.append({
        "node1": f"N{i}",
        "node2": f"N{i+1}",
        "attenuation": 0,
        "distance": 20000,
        "type": "meet_in_the_middle"
    })

# Cluster quantum links
for i in range(5):
    main = f"N{i}"
    c1 = f"N{i}0"
    c2 = f"N{i}1"

    cluster_links = [
        (main, c1),
        (main, c2),
        (c1, c2)
    ]

    for a, b in cluster_links:
        qconnections.append({
            "node1": a,
            "node2": b,
            "attenuation": 0,
            "distance": 2000,
            "type": "meet_in_the_middle"
        })

# Fully connected classical network
all_node_names = [n["name"] for n in nodes]

cconnections = []

for a, b in combinations(all_node_names, 2):
    cconnections.append({
        "node1": a,
        "node2": b,
        "delay": 1000000
    })

network = {
    "nodes": nodes,
    "qconnections": qconnections,
    "cconnections": cconnections,
    "stop_time": 1000000000000
}

with open("clustered_network.json", "w") as f:
    json.dump(network, f, indent=2)

print("Generated clustered_network.json")