import { StrictMode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ItemSessionProvider, ItemAccessGate } from "@/components/item-session";
import { useItems } from "@/lib/items";
import { api, ApiError, type ItemList } from "@/lib/api";
import { ItemBoard } from "@/components/item-board";
import { makeItem } from "./utils";

const state = vi.hoisted(() => ({
  ready: true,
  auth: {
    isLoading: false,
    isAuthenticated: true,
    activeNavigator: undefined as string | undefined,
    user: {
      profile: { sub: "user-a" },
      access_token: "access-a",
      id_token: "id-a",
      refresh_token: "refresh-a",
    },
    signinRedirect: vi.fn<() => Promise<void>>(),
  },
}));
vi.mock("react-oidc-context", () => ({ useAuth: () => state.auth }));
vi.mock("@/components/auth-provider", () => ({
  useAuthReady: () => state.ready,
}));
beforeEach(() => {
  state.ready = true;
  state.auth.isLoading = false;
  state.auth.isAuthenticated = true;
  state.auth.activeNavigator = undefined;
  state.auth.user = {
    profile: { sub: "user-a" },
    access_token: "access-a",
    id_token: "id-a",
    refresh_token: "refresh-a",
  };
  state.auth.signinRedirect.mockReset().mockResolvedValue();
});
function Probe() {
  const items = useItems();
  return (
    <div>
      {items.data?.items.map((item) => (
        <p key={item.id}>{item.name}</p>
      ))}
    </div>
  );
}
function mount(child = <Probe />, strict = false) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Tree() {
    return (
      <QueryClientProvider client={client}>
        <ItemSessionProvider>
          <ItemAccessGate>{child}</ItemAccessGate>
        </ItemSessionProvider>
      </QueryClientProvider>
    );
  }
  const view = render(
    strict ? (
      <StrictMode>
        <Tree />
      </StrictMode>
    ) : (
      <Tree />
    ),
  );
  return {
    client,
    ...view,
    refresh: () =>
      view.rerender(
        strict ? (
          <StrictMode>
            <Tree />
          </StrictMode>
        ) : (
          <Tree />
        ),
      ),
  };
}
describe("protected item sessions", () => {
  it.each(["loading", "signed-out", "unconfigured"])(
    "does not fetch while %s",
    (condition) => {
      state.auth.isLoading = condition === "loading";
      state.auth.isAuthenticated = condition !== "signed-out";
      state.ready = condition !== "unconfigured";
      const list = vi.spyOn(api, "listItems");
      mount(<ItemBoard />);
      expect(list).not.toHaveBeenCalled();
      expect(
        screen.queryByRole("button", { name: "New task" }),
      ).not.toBeInTheDocument();
    },
  );
  it("scopes caches to sub and drops the old cache on account switch/logout", async () => {
    const list = vi
      .spyOn(api, "listItems")
      .mockImplementation(async (_params, auth) => ({
        items: [
          makeItem({
            name:
              auth.accessToken === "access-a"
                ? "A private task"
                : "B private task",
          }),
        ],
        total: 1,
      }));
    const view = mount();
    await screen.findByText("A private task");
    expect(view.client.getQueryData(["items", "user-a"])).toBeDefined();
    const aSignal = list.mock.calls[0][1].signal;
    state.auth.user = {
      ...state.auth.user,
      profile: { sub: "user-b" },
      access_token: "access-b",
    };
    view.refresh();
    expect(screen.queryByText("A private task")).not.toBeInTheDocument();
    await screen.findByText("B private task");
    expect(aSignal?.aborted).toBe(true);
    expect(view.client.getQueryData(["items", "user-a"])).toBeUndefined();
    expect(view.client.getQueryData(["items", "user-b"])).toBeDefined();
    state.auth.isAuthenticated = false;
    view.refresh();
    expect(screen.queryByText("B private task")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(view.client.getQueryData(["items", "user-b"])).toBeUndefined(),
    );
  });
  it("cancels pending A requests and never renders their late result as B", async () => {
    let finish!: (items: ItemList) => void;
    const list = vi
      .spyOn(api, "listItems")
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finish = resolve;
          }),
      )
      .mockResolvedValue({ items: [makeItem({ name: "B task" })], total: 1 });
    const view = mount();
    await waitFor(() => expect(list).toHaveBeenCalledTimes(1));
    state.auth.user = {
      ...state.auth.user,
      profile: { sub: "user-b" },
      access_token: "access-b",
    };
    view.refresh();
    finish({ items: [makeItem({ name: "A secret" })], total: 1 });
    await screen.findByText("B task");
    expect(screen.queryByText("A secret")).not.toBeInTheDocument();
    expect(view.client.getQueryData(["items", "user-a"])).toBeUndefined();
  });
  it("uses only the access token for every item operation; health stays public", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(
      async (_url, init) =>
        ({
          ok: true,
          status: init?.method === "DELETE" ? 204 : 200,
          json: async () =>
            String(_url).includes("health")
              ? { status: "ok", database: "ok" }
              : init?.method
                ? makeItem()
                : { items: [], total: 0 },
        }) as Response,
    );
    const auth = { accessToken: state.auth.user.access_token };
    await api.listItems({}, auth);
    await api.createItem({ name: "x", status: "todo" }, auth);
    await api.updateItem("x", { status: "done" }, auth);
    await api.deleteItem("x", auth);
    await api.readiness();
    for (const [, init] of fetch.mock.calls.slice(0, 4)) {
      expect(init?.headers).toMatchObject({ Authorization: "Bearer access-a" });
      expect(JSON.stringify(init)).not.toContain("id-a");
      expect(JSON.stringify(init)).not.toContain("refresh-a");
    }
    expect(fetch.mock.calls[4][1]?.headers).not.toHaveProperty("Authorization");
  });
  it("stops after one 401 and requires explicit sign in", async () => {
    const list = vi
      .spyOn(api, "listItems")
      .mockRejectedValue(new ApiError(401, "Expired"));
    mount();
    fireEvent.click(
      await screen.findByRole("button", { name: "Sign in again" }),
    );
    await waitFor(() =>
      expect(state.auth.signinRedirect).toHaveBeenCalledTimes(1),
    );
    expect(list).toHaveBeenCalledTimes(1);
  });
  it("works under StrictMode effect replay", async () => {
    vi.spyOn(api, "listItems").mockResolvedValue({
      items: [makeItem({ name: "Strict task" })],
      total: 1,
    });
    mount(<Probe />, true);
    expect(await screen.findByText("Strict task")).toBeInTheDocument();
  });
  it("optimistic moves affect only the current account cache", async () => {
    vi.spyOn(api, "listItems").mockResolvedValue({
      items: [makeItem()],
      total: 1,
    });
    const update = vi
      .spyOn(api, "updateItem")
      .mockReturnValue(new Promise(() => {}));
    const view = mount(<ItemBoard />);
    view.client.setQueryData(["items", "user-b"], {
      items: [makeItem({ name: "B cached" })],
      total: 1,
    });
    const card = await screen.findByRole("button", { name: "Edit Example" });
    const store = new Map<string, string>();
    const dataTransfer = {
      types: ["application/x-peach-item"],
      setData: (k: string, v: string) => store.set(k, v),
      getData: (k: string) => store.get(k) ?? "",
      effectAllowed: "",
      dropEffect: "",
    };
    fireEvent.dragStart(card, { dataTransfer, clientX: 10, clientY: 10 });
    fireEvent.drop(screen.getByRole("region", { name: "Done" }), {
      dataTransfer,
      clientX: 10,
      clientY: 10,
    });
    await waitFor(() => expect(update).toHaveBeenCalled());
    expect(
      view.client.getQueryData<ItemList>(["items", "user-a"])?.items[0].status,
    ).toBe("done");
    expect(
      view.client.getQueryData<ItemList>(["items", "user-b"])?.items[0].status,
    ).toBe("todo");
    expect(view.client.getQueryData(["items"])).toBeUndefined();
  });
  it("does not restore a previous user's optimistic cache after a late mutation failure", async () => {
    vi.spyOn(api, "listItems").mockImplementation(async (_params, auth) => ({
      items: [
        makeItem({
          name: auth.accessToken === "access-a" ? "Example" : "B task",
        }),
      ],
      total: 1,
    }));
    let fail!: (error: Error) => void;
    vi.spyOn(api, "updateItem").mockImplementationOnce(
      () =>
        new Promise((_resolve, reject) => {
          fail = reject;
        }),
    );
    const view = mount(<ItemBoard />);
    const card = await screen.findByRole("button", { name: "Edit Example" });
    const store = new Map<string, string>();
    const dataTransfer = {
      types: ["application/x-peach-item"],
      setData: (k: string, v: string) => store.set(k, v),
      getData: (k: string) => store.get(k) ?? "",
      effectAllowed: "",
      dropEffect: "",
    };
    fireEvent.dragStart(card, { dataTransfer, clientX: 10, clientY: 10 });
    fireEvent.drop(screen.getByRole("region", { name: "Done" }), {
      dataTransfer,
      clientX: 10,
      clientY: 10,
    });
    await waitFor(() => expect(fail).toBeDefined());
    state.auth.user = {
      ...state.auth.user,
      profile: { sub: "user-b" },
      access_token: "access-b",
    };
    view.refresh();
    await screen.findByRole("button", { name: "Edit B task" });
    fail(new Error("Delayed failure"));
    await waitFor(() => expect(view.client.isMutating()).toBe(0));
    expect(view.client.getQueryData(["items", "user-a"])).toBeUndefined();
    expect(
      view.client.getQueryData<ItemList>(["items", "user-b"])?.items[0].name,
    ).toBe("B task");
    expect(
      screen.queryByRole("button", { name: "Edit Example" }),
    ).not.toBeInTheDocument();
  });
  it("closes account A's task dialog before displaying account B", async () => {
    vi.spyOn(api, "listItems").mockImplementation(async (_params, auth) => ({
      items: [
        makeItem({
          name: auth.accessToken === "access-a" ? "A title" : "B title",
        }),
      ],
      total: 1,
    }));
    const view = mount(<ItemBoard />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Edit A title" }),
    );
    expect(screen.getByLabelText("Title")).toHaveValue("A title");
    state.auth.user = {
      ...state.auth.user,
      profile: { sub: "user-b" },
      access_token: "access-b",
    };
    view.refresh();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await screen.findByRole("button", { name: "Edit B title" });
    expect(screen.queryByText("A title")).not.toBeInTheDocument();
  });
});
