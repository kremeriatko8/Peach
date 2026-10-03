import { useQuery } from "@tanstack/react-query";
import { ApiError, type ItemList } from "@/lib/api";
import { useItemApi } from "@/components/item-session";

export async function fetchItems(
  listItems: (params: { limit: number; offset: number }) => Promise<ItemList>,
): Promise<ItemList> {
  const result: ItemList = { items: [], total: 0 };
  let offset = 0;
  do {
    const page = await listItems({ limit: 100, offset });
    result.total = page.total;
    result.items.push(...page.items);
    offset += page.items.length;
    if (page.items.length === 0) break;
  } while (offset < result.total);
  return result;
}

export function useItems() {
  const client = useItemApi();
  return useQuery({
    queryKey: client.queryKey,
    enabled: !!client.session,
    queryFn: ({ signal }) =>
      fetchItems((params) => client.listItems(params, signal)),
    retry: (count, error) =>
      !(error instanceof ApiError && error.status === 401) && count < 1,
  });
}
