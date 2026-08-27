"""
BFS 社交路径引擎 — 适配 looma-zervi 后端

从六度分隔算法项目移植，适配 looma 的 DatabaseManager 和用户体系。
核心功能：
  1. 查找两个用户之间的最短社交路径（推荐链）
  2. 计算分隔度数（几何层；不做用户可见信用分）
  3. 统计 N 步内可达用户
  4. 网络拓扑分析（平均路径、聚类系数、Hub 节点）

红线（TRUST_LAYER / ENGINEERING_CLOSED_LOOP_P0）：
  社交距离度数 ≠ 信任分。禁止把 degrees 映射成用户可见的 trust_score。
"""
from __future__ import annotations
from collections import deque
from typing import Dict, List, Set, Optional
import random


def bfs_shortest_path(adj: Dict[str, Set[str]], source: str, target: str) -> Optional[List[str]]:
    """
    BFS 查找从 source 到 target 的最短社交路径。

    Returns:
        路径列表 [source, ...intermediaries..., target]，不可达返回 None
    """
    if source == target:
        return [source]
    if source not in adj or target not in adj:
        return None

    visited: Set[str] = {source}
    queue: deque = deque([(source, [source])])

    while queue:
        current, path = queue.popleft()
        for neighbor in adj.get(current, set()):
            if neighbor == target:
                return path + [neighbor]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return None


def compute_degrees_of_separation(adj: Dict[str, Set[str]], source: str, target: str) -> int:
    """计算两个用户之间的分隔度数。不可达返回 -1。"""
    path = bfs_shortest_path(adj, source, target)
    if path is None:
        return -1
    return len(path) - 1


def bfs_reachable_users(adj: Dict[str, Set[str]], source: str, max_depth: int = 6) -> Dict[str, int]:
    """
    统计从 source 出发，在 max_depth 步内可达的所有用户及其距离。

    Returns:
        {user_id: distance} 字典
    """
    if source not in adj:
        return {}

    distances: Dict[str, int] = {source: 0}
    queue: deque = deque([source])

    while queue:
        current = queue.popleft()
        current_dist = distances[current]
        if current_dist >= max_depth:
            continue
        for neighbor in adj.get(current, set()):
            if neighbor not in distances:
                distances[neighbor] = current_dist + 1
                queue.append(neighbor)

    return distances


def compute_network_stats(adj: Dict[str, Set[str]], sample_size: int = 200) -> dict:
    """
    网络拓扑分析（Admin 仪表盘用）。

    对大图使用采样近似平均路径长度。
    """
    n = len(adj)
    if n == 0:
        return {"nodes": 0, "edges": 0, "avg_path_length": 0, "reachable_6step": 0}

    total_edges = sum(len(neighbors) for neighbors in adj.values()) // 2

    # 采样计算平均路径长度
    nodes = list(adj.keys())
    if len(nodes) <= sample_size:
        sample_nodes = nodes
    else:
        sample_nodes = random.sample(nodes, sample_size)

    total_distance = 0
    pair_count = 0
    reach_within_6 = 0
    total_pairs = 0

    for source in sample_nodes:
        distances = bfs_reachable_users(adj, source, max_depth=6)
        for target, dist in distances.items():
            if target != source:
                total_distance += dist
                pair_count += 1
                reach_within_6 += 1
        total_pairs += (n - 1)

    avg_path = total_distance / pair_count if pair_count > 0 else 0
    reach_pct = (reach_within_6 / total_pairs * 100) if total_pairs > 0 else 0

    # Hub 节点排名
    degree_sorted = sorted(adj.items(), key=lambda x: len(x[1]), reverse=True)
    top_hubs = [
        {"user_id": uid, "degree": len(neighbors)}
        for uid, neighbors in degree_sorted[:10]
    ]

    return {
        "nodes": n,
        "edges": total_edges,
        "avg_degree": round(sum(len(v) for v in adj.values()) / n, 2) if n > 0 else 0,
        "avg_path_length": round(avg_path, 2),
        "reachable_6step_pct": round(reach_pct, 1),
        "top_hubs": top_hubs,
    }
