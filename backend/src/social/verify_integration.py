"""
六度分隔算法 → looma-zervi 集成验证脚本

用实际的 looma.db 数据库测试：
  1. 构建社交图谱
  2. 查找用户间最短路径（几何层 degrees）
  3. 统计 6 步内可达用户
  4. 网络拓扑分析

注意：不做 degrees→trust_score 映射（TRUST_LAYER 红线）。

运行方式:
  cd C:/Users/szben/Desktop/GenzLTD/looma-zervi/backend
  python -m src.social.verify_integration
"""
import sys
import os
import random

# 确保能 import backend 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.manager import DatabaseManager
from src.social.graph_builder import build_social_graph, get_graph_stats
from src.social.social_bfs import (
    bfs_shortest_path,
    bfs_reachable_users,
    compute_network_stats,
)


def main():
    # verify_integration.py 在 backend/src/social/ 下，数据库在 backend/data/looma.db
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(backend_dir, "data", "looma.db")
    db_path = os.path.normpath(db_path)
    print(f"数据库路径: {db_path}")
    print(f"存在: {os.path.exists(db_path)}")
    print("=" * 60)

    if not os.path.exists(db_path):
        print("数据库文件不存在，尝试 :memory: 模式...")
        db = DatabaseManager(":memory:")
        db.init_schema()
        seeded = db.seed_beta_users()
        print(f"已播种 {len(seeded)} 个测试用户")
    else:
        db = DatabaseManager(db_path)
        db.init_schema()

    # Step 1: 构建社交图谱
    print("\n[1/4] 构建社交图谱...")
    adj = build_social_graph(db)
    stats = get_graph_stats(adj)
    print(f"  节点数: {stats['nodes']}")
    print(f"  边数:   {stats['edges']}")
    print(f"  平均度数: {stats['avg_degree']}")
    print(f"  孤立节点: {stats['isolated']}")

    if stats["nodes"] == 0:
        print("\n  数据库中没有社交关系数据。")
        print("  需要先通过推荐码、舰队、企业功能产生用户关系。")
        print("  算法本身已验证可用，等待数据填充后即可生效。")
        return

    # 打印 Hub 节点
    if stats["top_hubs"]:
        print("\n  Hub 用户 (度数最高):")
        for hub in stats["top_hubs"][:5]:
            print(f"    {hub['user_id'][:8]}... → 度数 {hub['degree']}")

    # Step 2: 找两个随机用户的最短路径
    print("\n[2/4] 查找最短社交路径...")
    nodes = list(adj.keys())
    if len(nodes) >= 2:
        source = random.choice(nodes)
        target = random.choice(nodes)
        while target == source:
            target = random.choice(nodes)

        path = bfs_shortest_path(adj, source, target)
        if path:
            degrees = len(path) - 1
            print(f"  起点: {source[:8]}...")
            print(f"  终点: {target[:8]}...")
            print(f"  分隔度数: {degrees}")
            print(f"  路径: {' → '.join(uid[:8] + '...' for uid in path)}")
        else:
            print(f"  {source[:8]}... → {target[:8]}... : 无法建立连接")

    # Step 3: 6 步内可达用户
    print("\n[3/4] 6 步内可达用户统计...")
    if len(nodes) >= 1:
        source = random.choice(nodes)
        distances = bfs_reachable_users(adj, source, max_depth=6)
        by_degree = {}
        for uid, dist in distances.items():
            if uid != source:
                by_degree.setdefault(dist, 0)
                by_degree[dist] += 1

        total_reach = sum(by_degree.values())
        print(f"  从用户 {source[:8]}... 出发:")
        for d in sorted(by_degree.keys()):
            print(f"    第 {d} 度: {by_degree[d]} 人")
        print(f"  总计可达: {total_reach} / {len(adj) - 1} 人")

    # Step 4: 网络拓扑分析
    print("\n[4/4] 网络拓扑分析...")
    net_stats = compute_network_stats(adj, sample_size=min(100, len(adj)))
    print(f"  平均路径长度: {net_stats['avg_path_length']}")
    print(f"  6 步内可达比例: {net_stats['reachable_6step_pct']}%")
    print(f"  平均度数: {net_stats['avg_degree']}")

    print("\n" + "=" * 60)
    print("  集成验证完成!（几何层 only，无 trust_score）")
    print("=" * 60)


if __name__ == "__main__":
    main()
