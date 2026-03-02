"""
Phase 3: UMAP Projections

Computes 2D and 3D UMAP projections from post embeddings.

Input: data/embeddings.npy
Output: data/umap_2d.npy, data/umap_3d.npy
"""

from pathlib import Path

import numpy as np

# ============ CONFIGURATION ============
EMBEDDINGS_PATH = Path("data/embeddings.npy")
UMAP_2D_PATH = Path("data/umap_2d.npy")
UMAP_3D_PATH = Path("data/umap_3d.npy")
N_NEIGHBORS = 15
MIN_DIST = 0.1
METRIC = "cosine"
# =======================================


def main():
    import umap

    embeddings = np.load(EMBEDDINGS_PATH)
    print(f"Loaded embeddings: {embeddings.shape}")

    print("Computing 2D UMAP...")
    reducer_2d = umap.UMAP(
        n_components=2, n_neighbors=N_NEIGHBORS,
        min_dist=MIN_DIST, metric=METRIC, random_state=42,
    )
    umap_2d = reducer_2d.fit_transform(embeddings)
    np.save(UMAP_2D_PATH, umap_2d.astype(np.float32))
    print(f"  → {UMAP_2D_PATH}")

    print("Computing 3D UMAP...")
    reducer_3d = umap.UMAP(
        n_components=3, n_neighbors=N_NEIGHBORS,
        min_dist=MIN_DIST, metric=METRIC, random_state=42,
    )
    umap_3d = reducer_3d.fit_transform(embeddings)
    np.save(UMAP_3D_PATH, umap_3d.astype(np.float32))
    print(f"  → {UMAP_3D_PATH}")


if __name__ == "__main__":
    main()
