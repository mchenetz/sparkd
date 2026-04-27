import { useBoxes } from "../hooks/useBoxes";
import { useClusters } from "../hooks/useClusters";

type Props = {
  /** Current value: "", "<box_id>", or "cluster:<name>". */
  value: string;
  onChange: (next: string) => void;
  /** Show the clusters optgroup. Default true. */
  allowClusters?: boolean;
  /** Show a leading "default" option (empty value). Default false. */
  allowDefault?: boolean;
  /** Label for the default option (when allowDefault). */
  defaultLabel?: string;
  /** Placeholder when neither default nor any options apply. */
  placeholder?: string;
};

/**
 * Optgrouped selector for "pick a target". Sole source of truth for the
 * cluster-or-box picker UX. Encodes cluster targets as `cluster:<name>`.
 */
export default function TargetSelect({
  value,
  onChange,
  allowClusters = true,
  allowDefault = false,
  defaultLabel = "DGX Spark (default specs)",
  placeholder = "— target box —",
}: Props) {
  const boxes = useBoxes();
  const clusters = useClusters();
  const clusterList = clusters.data?.clusters ?? [];
  const boxList = boxes.data ?? [];
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {allowDefault ? (
        <option value="">{defaultLabel}</option>
      ) : (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {allowClusters && clusterList.length > 0 && (
        <optgroup label="clusters (multi-node)">
          {clusterList.map((c) => (
            <option key={c.name} value={`cluster:${c.name}`}>
              {c.name} — {c.box_count} node{c.box_count === 1 ? "" : "s"}
            </option>
          ))}
        </optgroup>
      )}
      {boxList.length > 0 && (
        <optgroup label="single box">
          {boxList.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
              {b.host ? ` · ${b.host}` : ""}
            </option>
          ))}
        </optgroup>
      )}
    </select>
  );
}
