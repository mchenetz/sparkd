import type { Recipe } from "../hooks/useRecipes";
import type { Cluster } from "../hooks/useClusters";

/**
 * Infer how many DGX Spark boxes a recipe needs from its vLLM args.
 *
 * vLLM distributes work across GPUs via tensor- and pipeline-parallelism.
 * Total GPUs needed = tensor_parallel_size * pipeline_parallel_size. On
 * DGX Spark each box has exactly one GPU, so the box count equals the GPU
 * count. Both flags default to 1, so a recipe with neither set requires 1
 * box (single-node).
 *
 * Args land in `recipe.args` with their leading dashes intact (e.g.
 * `"--tensor-parallel-size": "4"`); both long and short forms are checked.
 */
export function recipeNodeCount(recipe: Recipe): number {
  const a = recipe.args ?? {};
  const tp = readInt(a["--tensor-parallel-size"]) ?? readInt(a["-tp"]) ?? 1;
  const pp = readInt(a["--pipeline-parallel-size"]) ?? readInt(a["-pp"]) ?? 1;
  return Math.max(1, tp * pp);
}

/**
 * Resolve a target string to a node count.
 *  - "" → null (no target → no filtering)
 *  - "<box_id>" → 1
 *  - "cluster:<name>" → that cluster's box_count, or null if unknown.
 */
export function targetNodeCount(
  target: string,
  clusters: Cluster[],
): number | null {
  if (!target) return null;
  if (target.startsWith("cluster:")) {
    const name = target.slice("cluster:".length);
    const c = clusters.find((x) => x.name === name);
    return c?.box_count ?? null;
  }
  return 1;
}

function readInt(v: string | undefined): number | null {
  if (v === undefined || v === "") return null;
  const n = parseInt(v, 10);
  return Number.isFinite(n) && n > 0 ? n : null;
}
