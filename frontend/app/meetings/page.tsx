import { ItemAccessGate } from "@/components/item-session";
import { Meetings } from "@/components/meetings";

export const metadata = { title: "Meetings | Peach" };

export default function MeetingsPage() {
  return (
    <ItemAccessGate resource="meetings">
      <Meetings />
    </ItemAccessGate>
  );
}
