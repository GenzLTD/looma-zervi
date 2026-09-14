#!/usr/bin/env python3
"""
诗词库按作者切分 — 从陆游母版全集 ChromaDB 抽出一个博主的专属子库。

背景：陆游实例的诗词「货」是 chinese-poetry 全集（ChromaDB 集合 poetry_full，
      目录 data/poetry_full，metadata 含 author 字段）。
      李白/白居易「各配各的货」= 各自只保留自己作者的诗。

用法：
    # 抽李白（精确匹配 author == "李白"）
    python scripts/poetry-split-by-author.py \
        --source-dir data/poetry_full \
        --target-dir data/poetry_full_libai \
        --author 李白

    # 多作者（逗号分隔）或含朝代变体的模糊匹配
    python scripts/poetry-split-by-author.py \
        --source-dir data/poetry_full \
        --target-dir data/poetry_full_libai \
        --author 李白,杜甫 \
        --contains

    # 目标目录已存在时强制覆盖
    ... --force

产出：target-dir 下是一个新的 ChromaDB 目录（集合名与源一致，默认 poetry_full）。
      部署时把该目录替换/挂载到容器的 data/poetry_full 位置即可。

说明：
    - 只抽 documents + metadatas（不复制 embeddings）；新集合查询时用默认
      embedding function 现场算向量，与母版 sqlite 关键词优先 + chroma 兜底的
      检索架构一致。
    - 源目录只读时自动复制到临时目录再读（与 import_poetry.py 同款处理）。
"""
import argparse
import os
import shutil
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def resolve_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(PROJECT_ROOT, path)


def read_and_filter(source_dir: str, collection_name: str,
                    authors: list[str], contains: bool):
    import chromadb

    chroma_file = os.path.join(source_dir, "chroma.sqlite3")
    if not os.path.isfile(chroma_file):
        raise FileNotFoundError(f"源 ChromaDB 不存在: {chroma_file}")

    work_dir = source_dir
    if not os.access(chroma_file, os.W_OK):
        work_dir = tempfile.mkdtemp(prefix="poetry_split_")
        print(f"[split] 源目录只读，复制到临时目录: {work_dir}")
        shutil.copytree(source_dir, work_dir, dirs_exist_ok=True)

    client = chromadb.PersistentClient(path=work_dir)
    coll = client.get_collection(collection_name)
    total = coll.count()
    print(f"[split] 源集合 '{collection_name}' 共 {total} 首")

    batch_size = 5000
    offset = 0
    matched_ids = []
    matched_docs = []
    matched_metas = []

    author_set = {a.strip() for a in authors if a and a.strip()}
    if not author_set:
        raise ValueError("未指定任何作者（--author 必填）")

    while offset < total:
        result = coll.get(
            include=["documents", "metadatas"],
            limit=batch_size,
            offset=offset,
        )
        ids = result["ids"]
        docs = result["documents"]
        metas = result["metadatas"]

        for i in range(len(ids)):
            meta = metas[i] if metas and i < len(metas) else {}
            author = (meta.get("author") or "").strip()

            hit = False
            if contains:
                hit = any(a in author or author in a for a in author_set)
            else:
                hit = author in author_set

            if hit:
                matched_ids.append(ids[i])
                matched_docs.append(docs[i] if docs else "")
                matched_metas.append(meta)

        offset += batch_size
        print(f"[split]  已扫描 {min(offset, total)}/{total}，命中 {len(matched_ids)}")

    print(f"[split] 命中作者 {sorted(author_set)} 的诗共 {len(matched_ids)} 首")
    return matched_ids, matched_docs, matched_metas


def write_collection(target_dir: str, collection_name: str,
                     ids, docs, metas, force: bool):
    import chromadb

    if os.path.isdir(target_dir) and os.listdir(target_dir):
        if not force:
            raise FileExistsError(
                f"目标目录非空: {target_dir}（加 --force 覆盖）")
        print(f"[split] 目标目录非空，--force 已指定，先清空")
        shutil.rmtree(target_dir)

    os.makedirs(target_dir, exist_ok=True)
    client = chromadb.PersistentClient(path=target_dir)
    # 用与源同名的集合；查询端仍按 collection_name 找，部署时替换目录即可
    coll = client.get_or_create_collection(collection_name)

    # 分批写入，避免单次 add 过大
    batch = 2000
    for i in range(0, len(ids), batch):
        coll.add(
            ids=ids[i:i + batch],
            documents=docs[i:i + batch],
            metadatas=metas[i:i + batch],
        )
    print(f"[split] 已写入目标集合 '{collection_name}'，共 {coll.count()} 首")
    print(f"[split] 目标目录: {target_dir}")


def main():
    parser = argparse.ArgumentParser(description="诗词库按作者切分")
    parser.add_argument("--source-dir", default="data/poetry_full")
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--author", required=True,
                        help="作者名，逗号分隔，如 '李白,杜甫'")
    parser.add_argument("--collection", default="poetry_full")
    parser.add_argument("--contains", action="store_true",
                        help="子串匹配（author 含朝代等变体时用）")
    parser.add_argument("--force", action="store_true",
                        help="目标目录非空时覆盖")
    args = parser.parse_args()

    source_dir = resolve_path(args.source_dir)
    target_dir = resolve_path(args.target_dir)
    authors = [a for a in args.author.split(",")]

    print(f"[split] 源: {source_dir}")
    print(f"[split] 目标: {target_dir}")

    ids, docs, metas = read_and_filter(source_dir, args.collection,
                                       authors, args.contains)
    if not ids:
        print("[split] 未命中任何诗，终止（请核对作者名/集合名）")
        sys.exit(1)

    write_collection(target_dir, args.collection, ids, docs, metas, args.force)
    print(f"\n✅ 切分完成：{len(ids)} 首 → {target_dir}")


if __name__ == "__main__":
    main()
