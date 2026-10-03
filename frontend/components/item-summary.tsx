import { Circle, CircleCheck, CircleDashed } from "lucide-react";
import { itemStatuses, type Item } from "@/lib/api";
import { statusMeta } from "@/lib/item-status";
const colors = {
  todo: "bg-tint-peach text-tint-peach-foreground",
  in_progress: "bg-tint-blue text-tint-blue-foreground",
  done: "bg-tint-green text-tint-green-foreground",
};
const icons = { todo: Circle, in_progress: CircleDashed, done: CircleCheck };
export function ItemSummary({ items }: { items: Item[] }) {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {itemStatuses.map((status) => {
        const Icon = icons[status];
        return (
          <section
            key={status}
            aria-label={`${statusMeta[status].label} summary`}
            className={`rounded-2xl border border-black/3 p-6 ${colors[status]}`}
          >
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-sm font-medium">
                {statusMeta[status].label}
              </h2>
              <Icon className="size-5 opacity-70" />
            </div>
            <p className="text-4xl font-semibold tracking-tight tabular-nums">
              {items.filter((item) => item.status === status).length}
            </p>
            <p className="mt-2 text-xs opacity-75">
              {status === "done"
                ? "A little progress worth celebrating"
                : status === "in_progress"
                  ? "One step closer to done"
                  : "Ready when you are"}
            </p>
          </section>
        );
      })}
    </div>
  );
}
