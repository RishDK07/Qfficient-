import os
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional, Any

# Ensure MPLCONFIGDIR is configured for safe execution in restricted environments
if "MPLCONFIGDIR" not in os.environ:
    mpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".mpl_cache")
    os.environ["MPLCONFIGDIR"] = os.path.abspath(mpl_dir)
    os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import matplotlib.pyplot as plt
import networkx as nx

# 12-Component (Node) Microgrid Topology
SAMPLE_NODES: Dict[str, Tuple[float, float]] = {
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

SAMPLE_LINES: List[Tuple[str, str, str, float, float]] = [
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

SAMPLE_SELECTED_LINES: Set[str] = {"L1", "L3", "L4", "L5", "L8", "L9", "L10", "L12", "L13", "L15"}


class MicrogridVisualizer:
    """
    Renders microgrid network topology diagrams highlighting active/selected lines
    versus unused candidate lines, with line metric annotations (loss, flow) and status indicators.
    """

    @staticmethod
    def plot_microgrid(
        nodes: Dict[str, Tuple[float, float]],
        lines: List[Tuple[str, str, str, float, float]],
        selected_line_ids: Set[str],
        output_file: str = "optimized_microgrid.png",
        show_line_metrics: bool = True,
        title: str = "Optimized Microgrid Routing Configuration (12 Components)"
    ) -> Path:
        """
        Generates and saves the microgrid routing visualization.

        Args:
            nodes: Dict mapping node names to (x, y) coordinates.
            lines: List of tuples (line_id, node_a, node_b, loss_kw, flow_kw).
            selected_line_ids: Set of line_ids chosen by the optimizer/solver.
            output_file: Path to save the PNG image.
            show_line_metrics: Whether to display loss and flow text near edges.
            title: Diagram header title.

        Returns:
            Resolved Path of the saved image.
        """
        graph = nx.Graph()
        graph.add_nodes_from(nodes)
        for line_id, node_a, node_b, loss_kw, flow_kw in lines:
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
        ax.set_title(title, fontsize=16, weight="bold")

        # Draw unused candidate lines first so selected lines remain prominent
        nx.draw_networkx_edges(
            graph, nodes, edgelist=unused_edges, ax=ax,
            edge_color="#b8c0cc", width=2, style="dashed", alpha=0.8,
        )
        nx.draw_networkx_edges(
            graph, nodes, edgelist=selected_edges, ax=ax,
            edge_color="#16803c", width=4,
        )
        nx.draw_networkx_nodes(
            graph, nodes, ax=ax,
            node_color="#e8f1ff", edgecolors="#234a73",
            linewidths=1.5, node_size=1600,
        )
        nx.draw_networkx_labels(
            graph, nodes, ax=ax, font_size=8.5, font_weight="bold",
        )

        # Show stable line IDs on every candidate line
        edge_id_labels = {
            (a, b): attrs["line_id"]
            for a, b, attrs in graph.edges(data=True)
        }
        nx.draw_networkx_edge_labels(
            graph, nodes, edge_labels=edge_id_labels, ax=ax,
            font_size=8, font_color="#263238", label_pos=0.5,
            bbox={"alpha": 0.75, "color": "white", "pad": 1},
        )

        if show_line_metrics:
            metric_labels = {
                (a, b): f"loss {attrs['loss_kw']:.1f} kW\nflow {attrs['flow_kw']:.0f} kW"
                for a, b, attrs in graph.edges(data=True)
                if attrs["line_id"] in selected_line_ids
            }
            nx.draw_networkx_edge_labels(
                graph, nodes, edge_labels=metric_labels, ax=ax,
                font_size=7, font_color="#14532d", label_pos=0.76,
                bbox={"alpha": 0.85, "color": "white", "pad": 1},
            )

        # Legend explaining selected and unused lines
        ax.plot([], [], color="#16803c", linewidth=4, label="Selected / active line")
        ax.plot([], [], color="#b8c0cc", linewidth=2, linestyle="dashed", label="Unused candidate line")
        ax.legend(loc="upper left", frameon=True, fontsize=10)
        ax.text(
            0.01, 0.01,
            f"Components: {len(nodes)} | Selected lines: {len(selected_line_ids)} of {len(lines)}",
            transform=ax.transAxes, fontsize=10, color="#374151", weight="bold"
        )
        ax.axis("off")
        fig.tight_layout()

        out_path = Path(output_file)
        fig.savefig(str(out_path), dpi=220, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return out_path.resolve()

    @classmethod
    def plot_sample_microgrid(
        cls,
        selected_line_ids: Optional[Set[str]] = None,
        output_file: str = "optimized_microgrid.png",
        show_line_metrics: bool = True
    ) -> Path:
        """Plots the default reference microgrid topology with specified or default active lines."""
        active_ids = selected_line_ids if selected_line_ids is not None else SAMPLE_SELECTED_LINES
        return cls.plot_microgrid(
            nodes=SAMPLE_NODES,
            lines=SAMPLE_LINES,
            selected_line_ids=active_ids,
            output_file=output_file,
            show_line_metrics=show_line_metrics
        )
