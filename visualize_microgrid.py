import os
from pathlib import Path

# Ensure local cache for Matplotlib
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ["MPLCONFIGDIR"] = os.path.join(current_dir, ".mpl_cache")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import matplotlib.pyplot as plt
import networkx as nx

# ---------------------------------------------------------------------------
# 1) Microgrid topology with 12 components (nodes).
#    Each line has a stable ID, endpoints, resistance/loss estimate, and flow.
# ---------------------------------------------------------------------------
NODES = {
    "Substation": (0.0, 2.0),
    "Solar Farm": (1.2, 3.4),
    "Wind Park": (1.2, 0.6),
    "Battery BESS": (2.2, 2.4),
    "Junction A": (2.8, 3.5),
    "Junction B": (2.8, 1.8),
    "Junction C": (2.8, 0.5),
    "EV Depot": (4.3, 3.8),
    "Hospital": (4.3, 2.8),
    "Data Center": (4.3, 1.9),
    "Residential": (4.3, 1.0),
    "Heavy Industry": (4.3, 0.1),
}

LINES = [
    # id, endpoint 1, endpoint 2, loss in kW, flow in kW
    ("L1", "Substation", "Battery BESS", 1.2, 85.0),
    ("L2", "Substation", "Junction B", 1.8, 95.0),
    ("L3", "Solar Farm", "Junction A", 0.8, 48.0),
    ("L4", "Solar Farm", "Battery BESS", 0.6, 32.0),
    ("L5", "Wind Park", "Junction C", 0.9, 44.0),
    ("L6", "Wind Park", "Junction B", 1.1, 26.0),
    ("L7", "Battery BESS", "Junction A", 0.7, 35.0),
    ("L8", "Battery BESS", "Junction B", 0.5, 40.0),
    ("L9", "Junction A", "EV Depot", 1.4, 52.0),
    ("L10", "Junction A", "Hospital", 0.7, 38.0),
    ("L11", "Junction B", "Hospital", 1.0, 22.0),
    ("L12", "Junction B", "Data Center", 0.9, 60.0),
    ("L13", "Junction B", "Residential", 1.3, 45.0),
    ("L14", "Junction C", "Residential", 0.8, 30.0),
    ("L15", "Junction C", "Heavy Industry", 1.5, 70.0),
    ("L16", "Data Center", "Heavy Industry", 0.6, 20.0),
]

# ---------------------------------------------------------------------------
# 2) Optimizer result selecting lines across the 12 components.
#    Selected 11 active lines to form an optimal connected radial topology.
# ---------------------------------------------------------------------------
selected_line_ids = {"L1", "L3", "L4", "L5", "L8", "L9", "L10", "L12", "L13", "L15"}

# Set True to print each line's loss and flow next to the line in the diagram.
SHOW_LINE_METRICS = True
OUTPUT_FILE = "optimized_microgrid.png"


def main():
    graph = nx.Graph()
    graph.add_nodes_from(NODES)
    for line_id, node_a, node_b, loss_kw, flow_kw in LINES:
        graph.add_edge(
            node_a,
            node_b,
            line_id=line_id,
            loss_kw=loss_kw,
            flow_kw=flow_kw,
        )

    known_line_ids = {attrs["line_id"] for _, _, attrs in graph.edges(data=True)}
    unknown_ids = selected_line_ids - known_line_ids
    if unknown_ids:
        raise ValueError(f"Selected line IDs do not exist in LINES: {sorted(unknown_ids)}")

    selected_edges = [
        (a, b) for a, b, attrs in graph.edges(data=True)
        if attrs["line_id"] in selected_line_ids
    ]
    unused_edges = [
        (a, b) for a, b, attrs in graph.edges(data=True)
        if attrs["line_id"] not in selected_line_ids
    ]

    fig, ax = plt.subplots(figsize=(13, 8))
    ax.set_title("Optimized Microgrid Routing Configuration (12 Components)", fontsize=16, weight="bold")

    # Draw unused candidate lines first so selected lines remain prominent.
    nx.draw_networkx_edges(
        graph, NODES, edgelist=unused_edges, ax=ax,
        edge_color="#b8c0cc", width=2, style="dashed", alpha=0.8,
    )
    nx.draw_networkx_edges(
        graph, NODES, edgelist=selected_edges, ax=ax,
        edge_color="#16803c", width=4,
    )
    nx.draw_networkx_nodes(
        graph, NODES, ax=ax,
        node_color="#e8f1ff", edgecolors="#234a73",
        linewidths=1.5, node_size=1600,
    )
    nx.draw_networkx_labels(
        graph, NODES, ax=ax, font_size=8.5, font_weight="bold",
    )

    # Show stable line IDs on every candidate line.
    edge_id_labels = {
        (a, b): attrs["line_id"]
        for a, b, attrs in graph.edges(data=True)
    }
    nx.draw_networkx_edge_labels(
        graph, NODES, edge_labels=edge_id_labels, ax=ax,
        font_size=8, font_color="#263238", label_pos=0.5,
        bbox={"alpha": 0.75, "color": "white", "pad": 1},
    )

    if SHOW_LINE_METRICS:
        metric_labels = {
            (a, b): f"loss {attrs['loss_kw']:.1f} kW\nflow {attrs['flow_kw']:.0f} kW"
            for a, b, attrs in graph.edges(data=True)
            if attrs["line_id"] in selected_line_ids
        }
        nx.draw_networkx_edge_labels(
            graph, NODES, edge_labels=metric_labels, ax=ax,
            font_size=7, font_color="#14532d", label_pos=0.76,
            bbox={"alpha": 0.85, "color": "white", "pad": 1},
        )

    # Matplotlib legend explaining selected and unused lines.
    ax.plot([], [], color="#16803c", linewidth=4, label="Selected / active line")
    ax.plot([], [], color="#b8c0cc", linewidth=2, linestyle="dashed", label="Unused candidate line")
    ax.legend(loc="upper left", frameon=True, fontsize=10)
    ax.text(
        0.01, 0.01,
        f"Components: {len(NODES)} | Selected lines: {len(selected_line_ids)} of {len(LINES)}",
        transform=ax.transAxes, fontsize=10, color="#374151", weight="bold"
    )
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUTPUT_FILE, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved network diagram to: {Path(OUTPUT_FILE).resolve()}")


if __name__ == "__main__":
    main()
