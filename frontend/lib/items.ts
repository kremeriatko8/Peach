import { useQuery } from "@tanstack/react-query";
import { api, type ItemList } from "@/lib/api";

export async function fetchItems(): Promise<ItemList> {
  const result: ItemList = { items: [], total: 0 };
  let offset = 0;
  do {
    const page = await api.listItems({ limit: 100, offset });
    result.total = page.total;
    result.items.push(...page.items);
    offset += page.items.length;
    if (page.items.length === 0) break;
  } while (offset < result.total);
  return result;
}

export function useItems() {
  return useQuery({ queryKey: ["items"], queryFn: fetchItems });
}
