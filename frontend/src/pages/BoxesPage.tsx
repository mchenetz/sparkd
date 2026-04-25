import AddBoxDialog from "../components/AddBoxDialog";
import BoxList from "../components/BoxList";
import { useBoxes } from "../hooks/useBoxes";

export default function BoxesPage() {
  const { data, isLoading, error } = useBoxes();
  if (isLoading) return <div>loading…</div>;
  if (error) return <div>error: {String(error)}</div>;
  return (
    <div>
      <h1>Boxes</h1>
      <AddBoxDialog />
      <BoxList boxes={data ?? []} />
    </div>
  );
}
