import { ItemAccessGate } from "@/components/item-session";
import { ItemBoard } from "@/components/item-board";

export const metadata = { title: "Board | Peach" };

export default function ItemsPage() {
  return (
    <ItemAccessGate>
      <ItemBoard />
    </ItemAccessGate>
  );
}
