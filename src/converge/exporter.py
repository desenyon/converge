from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import networkx as nx

from converge.project_context import ProjectContext


class ExportError(Exception):
    pass


class GraphExporter:
    def __init__(self, context: ProjectContext):
        self.context = context
        self.export_dir = context.artifact_dir / "exports"

    def export(self, graph: nx.DiGraph[Any], output_format: str) -> list[Path]:
        self.export_dir.mkdir(parents=True, exist_ok=True)

        if output_format == "json":
            return [self._export_json(graph)]
        if output_format == "csv":
            return self._export_csv(graph)

        raise ExportError(f"Unsupported export format: {output_format}")

    def _export_json(self, graph: nx.DiGraph[Any]) -> Path:
        output_path = self.export_dir / "graph.json"
        payload = {
            "repository": str(self.context.root_dir),
            "nodes": [
                {"id": node_id, **data}
                for node_id, data in sorted(graph.nodes(data=True), key=lambda item: str(item[0]))
            ],
            "edges": [
                {"source": source, "target": target, **data}
                for source, target, data in sorted(
                    graph.edges(data=True), key=lambda item: (str(item[0]), str(item[1]))
                )
            ],
        }
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return output_path

    def _export_csv(self, graph: nx.DiGraph[Any]) -> list[Path]:
        nodes_path = self.export_dir / "nodes.csv"
        edges_path = self.export_dir / "edges.csv"

        with nodes_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["id", "name", "type"])
            writer.writeheader()
            for node_id, data in sorted(graph.nodes(data=True), key=lambda item: str(item[0])):
                writer.writerow(
                    {
                        "id": node_id,
                        "name": data.get("name", ""),
                        "type": data.get("type", ""),
                    }
                )

        with edges_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["source", "target", "type"])
            writer.writeheader()
            for source, target, data in sorted(
                graph.edges(data=True), key=lambda item: (str(item[0]), str(item[1]))
            ):
                writer.writerow(
                    {
                        "source": source,
                        "target": target,
                        "type": data.get("type", ""),
                    }
                )

        return [nodes_path, edges_path]
