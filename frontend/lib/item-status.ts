import type { ItemStatus } from "@/lib/api";

/** Labels and Notion status-group colours, in board column order. */
export const statusMeta: Record<
  ItemStatus,
  { label: string; dot: string; pill: string; column: string }
> = {
  todo: {
    label: "To do",
    dot: "bg-tint-peach-foreground",
    pill: "bg-tint-peach text-tint-peach-foreground",
    column: "bg-tint-peach/60",
  },
  in_progress: {
    label: "In progress",
    dot: "bg-tint-blue-foreground",
    pill: "bg-tint-blue text-tint-blue-foreground",
    column: "bg-tint-blue/60",
  },
  done: {
    label: "Done",
    dot: "bg-tint-green-foreground",
    pill: "bg-tint-green text-tint-green-foreground",
    column: "bg-tint-green/60",
  },
};
