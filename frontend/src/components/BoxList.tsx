import { Box, useDeleteBox } from "../hooks/useBoxes";

export default function BoxList({ boxes }: { boxes: Box[] }) {
  const del = useDeleteBox();
  return (
    <table>
      <thead>
        <tr>
          <th>name</th>
          <th>host</th>
          <th>user</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {boxes.map((b) => (
          <tr key={b.id}>
            <td>{b.name}</td>
            <td>
              {b.host}:{b.port}
            </td>
            <td>{b.user}</td>
            <td>
              <button onClick={() => del.mutate(b.id)}>delete</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
