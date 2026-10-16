import os
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional, Any

# Ensure local cache for Matplotlib
if "MPLCONFIGDIR" not in os.environ:
    mpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".mpl_cache")
    os.environ["MPLCONFIGDIR"] = os.path.abspath(mpl_dir)
    os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import matplotlib.pyplot as plt
import networkx as nx

# 33-Component Smart Distribution Microgrid Topology (IEEE 33 Testbed)
SAMPLE_NODES: Dict[str, Tuple[float, float]] = {
    "Substation (B1)": (0.0, 0.0),
    "Main Feeder (B2)": (1.2, 0.0),
    "West Trunk (B3)": (2.4, 0.0),
    "Commercial A (B4)": (3.6, 0.0),
    "Sub-Junction 1 (B5)": (4.8, 0.0),
    "North Split (B6)": (6.0, 0.0),
    "Residential Hub (B7)": (7.2, 0.0),
    "Solar East (B8)": (8.4, 0.0),
    "Junction East (B9)": (9.6, 0.0),
    "Tech Park (B10)": (10.8, 0.0),
    "Campus (B11)": (12.0, 0.0),
    "Hospital (B12)": (13.2, 0.0),
    "East Lateral (B13)": (14.4, 0.0),
    "Solar PV Farm (B14)": (15.6, 0.0),
    "Commercial B (B15)": (16.8, 0.0),
    "Sub-Junction 2 (B16)": (18.0, 0.0),
    "Dist. Node 17 (B17)": (19.2, 0.0),
    "Wind Turbine A (B18)": (20.4, 0.0),
    # Lateral 1 (South Branch from B2)
    "South Feeder (B19)": (1.2, -1.8),
    "Sub-Junction 3 (B20)": (2.4, -1.8),
    "BESS Storage 1 (B21)": (3.6, -1.8),
    "EV Depot South (B22)": (4.8, -1.8),
    # Lateral 2 (South Branch from B3)
    "Central Lateral (B23)": (2.4, -3.4),
    "Heavy Industry (B24)": (3.6, -3.4),
    "Rooftop PV Hub (B25)": (4.8, -3.4),
    # Lateral 3 (North Branch from B6)
    "North Feeder (B26)": (6.0, 1.8),
    "Sub-Junction 4 (B27)": (7.2, 1.8),
    "Commercial North (B28)": (8.4, 1.8),
    "Data Center (B29)": (9.6, 1.8),
    "Dist. Node 30 (B30)": (10.8, 1.8),
    "EV Depot North (B31)": (12.0, 1.8),
    "BESS Storage 2 (B32)": (13.2, 1.8),
    "Wind Turbine B (B33)": (14.4, 1.8),
}

SAMPLE_LINES: List[Tuple[str, str, str, float, float]] = [
    # Main Trunk (Lines 1-17)
    ("L1", "Substation (B1)", "Main Feeder (B2)", 1.2, 280.0),
    ("L2", "Main Feeder (B2)", "West Trunk (B3)", 2.4, 240.0),
    ("L3", "West Trunk (B3)", "Commercial A (B4)", 1.8, 195.0),
    ("L4", "Commercial A (B4)", "Sub-Junction 1 (B5)", 1.5, 160.0),
    ("L5", "Sub-Junction 1 (B5)", "North Split (B6)", 2.1, 145.0),
    ("L6", "North Split (B6)", "Residential Hub (B7)", 1.9, 120.0),
    ("L7", "Residential Hub (B7)", "Solar East (B8)", 3.2, 110.0),
    ("L8", "Solar East (B8)", "Junction East (B9)", 1.8, 90.0),
    ("L9", "Junction East (B9)", "Tech Park (B10)", 1.6, 75.0),
    ("L10", "Tech Park (B10)", "Campus (B11)", 0.8, 65.0),
    ("L11", "Campus (B11)", "Hospital (B12)", 1.1, 55.0),
    ("L12", "Hospital (B12)", "East Lateral (B13)", 2.3, 45.0),
    ("L13", "East Lateral (B13)", "Solar PV Farm (B14)", 1.2, 35.0),
    ("L14", "Solar PV Farm (B14)", "Commercial B (B15)", 0.9, 28.0),
    ("L15", "Commercial B (B15)", "Sub-Junction 2 (B16)", 1.0, 22.0),
    ("L16", "Sub-Junction 2 (B16)", "Dist. Node 17 (B17)", 1.7, 18.0),
    ("L17", "Dist. Node 17 (B17)", "Wind Turbine A (B18)", 1.3, 12.0),
    # Lateral 1 (Lines 18-21)
    ("L18", "Main Feeder (B2)", "South Feeder (B19)", 0.7, 85.0),
    ("L19", "South Feeder (B19)", "Sub-Junction 3 (B20)", 1.9, 70.0),
    ("L20", "Sub-Junction 3 (B20)", "BESS Storage 1 (B21)", 0.9, 50.0),
    ("L21", "BESS Storage 1 (B21)", "EV Depot South (B22)", 1.4, 38.0),
    # Lateral 2 (Lines 22-24)
    ("L22", "West Trunk (B3)", "Central Lateral (B23)", 1.1, 95.0),
    ("L23", "Central Lateral (B23)", "Heavy Industry (B24)", 2.2, 80.0),
    ("L24", "Heavy Industry (B24)", "Rooftop PV Hub (B25)", 1.8, 45.0),
    # Lateral 3 (Lines 25-32)
    ("L25", "North Split (B6)", "North Feeder (B26)", 0.8, 110.0),
    ("L26", "North Feeder (B26)", "Sub-Junction 4 (B27)", 1.0, 95.0),
    ("L27", "Sub-Junction 4 (B27)", "Commercial North (B28)", 1.8, 75.0),
    ("L28", "Commercial North (B28)", "Data Center (B29)", 1.5, 60.0),
    ("L29", "Data Center (B29)", "Dist. Node 30 (B30)", 1.1, 48.0),
    ("L30", "Dist. Node 30 (B30)", "EV Depot North (B31)", 1.6, 36.0),
    ("L31", "EV Depot North (B31)", "BESS Storage 2 (B32)", 0.7, 24.0),
    ("L32", "BESS Storage 2 (B32)", "Wind Turbine B (B33)", 0.9, 15.0),
    # Tie Switches (Lines 33-37)
    ("T33", "Solar East (B8)", "BESS Storage 1 (B21)", 2.0, 0.0),
    ("T34", "Junction East (B9)", "Commercial B (B15)", 2.0, 0.0),
    ("T35", "Hospital (B12)", "EV Depot South (B22)", 2.0, 0.0),
    ("T36", "Wind Turbine A (B18)", "Wind Turbine B (B33)", 0.8, 35.0),
    ("T37", "Rooftop PV Hub (B25)", "Data Center (B29)", 0.7, 45.0),
]

SAMPLE_SELECTED_LINES: Set[str] = {
    "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L11", "L12", "L13",
    "L14", "L15", "L16", "L17", "L18", "L19", "L20", "L21", "L22", "L23", "L24",
    "L25", "L26", "L27", "L29", "L30", "L31", "L32", "T36", "T37"
}


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
        title: str = "Optimized 33-Component Distribution Microgrid Topology (IEEE 33 Testbed)"
    ) -> Path:
        """
        Generates and saves the microgrid routing visualization.
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

        fig, ax = plt.subplots(figsize=(19, 10))
        ax.set_title(title, fontsize=18, weight="bold", pad=15)

        # Draw unused candidate lines first so selected lines remain prominent
        nx.draw_networkx_edges(
            graph, nodes, edgelist=unused_edges, ax=ax,
            edge_color="#b8c0cc", width=2.2, style="dashed", alpha=0.85,
        )
        nx.draw_networkx_edges(
            graph, nodes, edgelist=selected_edges, ax=ax,
            edge_color="#16803c", width=3.8,
        )
        nx.draw_networkx_nodes(
            graph, nodes, ax=ax,
            node_color="#e0f2fe", edgecolors="#0369a1",
            linewidths=1.8, node_size=1100,
        )
        nx.draw_networkx_labels(
            graph, nodes, ax=ax, font_size=7.2, font_weight="bold",
        )

        # Show line IDs on every candidate line
        edge_id_labels = {
            (a, b): attrs["line_id"]
            for a, b, attrs in graph.edges(data=True)
        }
        nx.draw_networkx_edge_labels(
            graph, nodes, edge_labels=edge_id_labels, ax=ax,
            font_size=7, font_color="#1e293b", label_pos=0.5,
            bbox={"alpha": 0.7, "color": "white", "pad": 0.8},
        )

        if show_line_metrics:
            metric_labels = {
                (a, b): f"{attrs['flow_kw']:.0f}kW"
                for a, b, attrs in graph.edges(data=True)
                if attrs["line_id"] in selected_line_ids and attrs["flow_kw"] > 0
            }
            nx.draw_networkx_edge_labels(
                graph, nodes, edge_labels=metric_labels, ax=ax,
                font_size=6.2, font_color="#15803d", label_pos=0.72,
                bbox={"alpha": 0.8, "color": "#f0fdf4", "pad": 0.6},
            )

        # Legend & Information Badges
        ax.plot([], [], color="#16803c", linewidth=4, label="Active Distribution Branch (Energized)")
        ax.plot([], [], color="#b8c0cc", linewidth=2.2, linestyle="dashed", label="Open Tie Switch (Standby)")
        ax.legend(loc="upper left", frameon=True, fontsize=11)
        ax.text(
            0.01, 0.01,
            f"Components: {len(nodes)} Buses | Active Lines: {len(selected_line_ids)} of {len(lines)} Branches | Open Tie Switches: {len(unused_edges)}",
            transform=ax.transAxes, fontsize=11, color="#334155", weight="bold"
        )
        ax.axis("off")
        fig.tight_layout()

        out_path = Path(output_file)
        fig.savefig(str(out_path), dpi=240, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return out_path.resolve()

    @classmethod
    def plot_sample_microgrid(
        cls,
        selected_line_ids: Optional[Set[str]] = None,
        output_file: str = "optimized_microgrid.png",
        show_line_metrics: bool = True
    ) -> Path:
        """Plots the default reference 33-component microgrid topology."""
        active_ids = selected_line_ids if selected_line_ids is not None else SAMPLE_SELECTED_LINES
        return cls.plot_microgrid(
            nodes=SAMPLE_NODES,
            lines=SAMPLE_LINES,
            selected_line_ids=active_ids,
            output_file=output_file,
            show_line_metrics=show_line_metrics
        )
