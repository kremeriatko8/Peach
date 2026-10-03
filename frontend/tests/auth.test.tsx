import { StrictMode } from "react";
import { OidcClient } from "oidc-client-ts";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthControls } from "@/components/auth-controls";
import LoginPage from "@/app/login/page";
import CallbackPage from "@/app/auth/callback/page";
import HomePage from "@/app/page";
import { SiteHeader } from "@/components/site-header";
import { api } from "@/lib/api";
import { fetchItems } from "@/lib/items";
import { makeItem, renderWithQuery } from "./utils";
import { authConfig, cognitoLogoutUrl } from "@/lib/auth";

const mocked = vi.hoisted(() => ({
  ready: true,
  params: false,
  auth: {
    isLoading: false,
    isAuthenticated: false,
    activeNavigator: undefined as string | undefined,
    error: undefined as Error | undefined,
    user: {
      profile: {
        email: "student@example.com",
        name: undefined as string | undefined,
      },
    },
    signinRedirect: vi.fn<() => Promise<void>>(),
    removeUser: vi.fn<() => Promise<void>>(),
  },
}));
vi.mock("next/navigation", () => ({ usePathname: () => "/" }));
vi.mock("react-oidc-context", () => ({
  useAuth: () => mocked.auth,
  hasAuthParams: () => mocked.params,
}));
vi.mock("@/components/auth-provider", () => ({
  useAuthReady: () => mocked.ready,
}));

beforeEach(() => {
  // Match next.config.ts: preserve registered slash URLs in Next Link.
  vi.stubEnv("__NEXT_MANUAL_TRAILING_SLASH", "true");
  mocked.auth.user.profile.name = undefined;
  mocked.ready = true;
  mocked.params = false;
  mocked.auth.isLoading = false;
  mocked.auth.isAuthenticated = false;
  mocked.auth.activeNavigator = undefined;
  mocked.auth.error = undefined;
  mocked.auth.signinRedirect.mockReset().mockResolvedValue();
  mocked.auth.removeUser.mockReset().mockResolvedValue();
  vi.stubEnv(
    "NEXT_PUBLIC_COGNITO_AUTHORITY",
    "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST",
  );
  vi.stubEnv("NEXT_PUBLIC_COGNITO_CLIENT_ID", "test-client");
  vi.stubEnv(
    "NEXT_PUBLIC_COGNITO_DOMAIN",
    "https://test.auth.us-east-1.amazoncognito.com",
  );
  vi.stubEnv(
    "NEXT_PUBLIC_AUTH_REDIRECT_URI",
    "http://localhost:3000/auth/callback/",
  );
  vi.stubEnv("NEXT_PUBLIC_AUTH_LOGOUT_URI", "http://localhost:3000/");
});

describe("authentication", () => {
  it("creates a real authorization request with S256 PKCE and the exact callback", async () => {
    const config = authConfig();
    if (!config) throw new Error("Missing test config");
    const client = new OidcClient({
      ...config,
      metadata: {
        issuer: config.authority,
        authorization_endpoint:
          "https://test.auth.us-east-1.amazoncognito.com/oauth2/authorize",
        token_endpoint:
          "https://test.auth.us-east-1.amazoncognito.com/oauth2/token",
      },
    });
    const request = await client.createSigninRequest({});
    const url = new URL(request.url);
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("code_challenge")).toBeTruthy();
    expect(url.searchParams.get("state")).toBeTruthy();
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("redirect_uri")).toBe(
      "http://localhost:3000/auth/callback/",
    );
  });

  it("links unauthenticated users to the slash login URL", () => {
    render(<AuthControls />);
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute(
      "href",
      "/login/",
    );
  });
  it("displays the email and sign-out control", () => {
    mocked.auth.isAuthenticated = true;
    render(<AuthControls />);
    expect(screen.getByText("student@example.com")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Sign out" }),
    ).toBeInTheDocument();
  });
  it("clears the session before navigating to the existing Cognito logout URL", async () => {
    mocked.auth.isAuthenticated = true;
    const navigate = vi.fn();
    const realWindow = window;
    render(<AuthControls />);
    vi.stubGlobal(
      "window",
      new Proxy(realWindow, {
        get(target, key) {
          if (key === "location") return { assign: navigate };
          return Reflect.get(target, key, target);
        },
      }),
    );
    try {
      fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
      await waitFor(() =>
        expect(navigate).toHaveBeenCalledWith(cognitoLogoutUrl()),
      );
      expect(mocked.auth.removeUser).toHaveBeenCalledTimes(1);
      expect(mocked.auth.removeUser.mock.invocationCallOrder[0]).toBeLessThan(
        navigate.mock.invocationCallOrder[0],
      );
    } finally {
      vi.unstubAllGlobals();
    }
  });
  it("shows a retryable error if clearing the local session fails", async () => {
    mocked.auth.isAuthenticated = true;
    mocked.auth.removeUser.mockRejectedValue(new Error("storage unavailable"));
    render(<AuthControls />);
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Could not sign out"),
    );
  });
  it("starts one redirect even under StrictMode and rerendering", async () => {
    const view = render(
      <StrictMode>
        <LoginPage />
      </StrictMode>,
    );
    view.rerender(
      <StrictMode>
        <LoginPage />
      </StrictMode>,
    );
    await waitFor(() =>
      expect(mocked.auth.signinRedirect).toHaveBeenCalledTimes(1),
    );
  });
  it.each(["loading", "navigator", "callback", "error", "unconfigured"])(
    "does not auto-redirect while %s",
    (state) => {
      if (state === "loading") mocked.auth.isLoading = true;
      if (state === "navigator") mocked.auth.activeNavigator = "signinRedirect";
      if (state === "callback") mocked.params = true;
      if (state === "error") mocked.auth.error = new Error("callback failed");
      if (state === "unconfigured") mocked.ready = false;
      render(<LoginPage />);
      expect(mocked.auth.signinRedirect).not.toHaveBeenCalled();
    },
  );
  it("allows explicit retry after a callback error without an automatic loop", () => {
    mocked.auth.error = new Error("callback failed");
    render(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(mocked.auth.signinRedirect).toHaveBeenCalledTimes(1);
  });
  it("shows callback failures without starting another redirect", () => {
    mocked.auth.error = new Error("callback failed");
    render(<CallbackPage />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Sign in could not be completed",
    );
    expect(mocked.auth.signinRedirect).not.toHaveBeenCalled();
  });
  it("uses public code/PKCE config and Cognito logout parameters", () => {
    const config = authConfig();
    expect(config?.response_type).toBe("code");
    expect(config?.disablePKCE).toBe(false);
    expect(config?.scope).toBe("openid email profile");
    expect(config?.client_secret).toBeUndefined();
    const logout = new URL(cognitoLogoutUrl());
    expect(logout.pathname).toBe("/logout");
    expect(logout.searchParams.get("client_id")).toBe("test-client");
    expect(logout.searchParams.get("logout_uri")).toBe(
      "http://localhost:3000/",
    );
    expect(logout.searchParams.has("post_logout_redirect_uri")).toBe(false);
  });
});

describe("Peach home", () => {
  it.each(["loading", "unconfigured", "redirecting"])(
    "shows only loading while %s",
    (state) => {
      mocked.auth.isLoading = state === "loading";
      mocked.ready = state !== "unconfigured";
      if (state === "redirecting")
        mocked.auth.activeNavigator = "signinRedirect";
      const tasks = vi.spyOn(api, "listItems");
      render(
        <>
          <SiteHeader />
          <HomePage />
        </>,
      );
      expect(screen.getByText("Getting Peach ready…")).toBeInTheDocument();
      expect(screen.queryByText("Welcome to Peach")).not.toBeInTheDocument();
      expect(
        screen.queryByRole("link", { name: "Dashboard" }),
      ).not.toBeInTheDocument();
      expect(tasks).not.toHaveBeenCalled();
    },
  );
  it("welcomes signed-out visitors without requesting tasks or readiness", async () => {
    const tasks = vi.spyOn(api, "listItems");
    const health = vi.spyOn(api, "readiness");
    render(
      <>
        <SiteHeader />
        <HomePage />
      </>,
    );
    expect(
      screen.getByRole("heading", { name: "Welcome to Peach" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Board" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() =>
      expect(mocked.auth.signinRedirect).toHaveBeenCalledTimes(1),
    );
    expect(tasks).not.toHaveBeenCalled();
    expect(health).not.toHaveBeenCalled();
  });
  it("renders real status counts, task previews, account controls and compact readiness", async () => {
    mocked.auth.isAuthenticated = true;
    vi.spyOn(api, "listItems").mockResolvedValue({
      items: [
        makeItem({ id: "a", name: "Read chapter" }),
        makeItem({ id: "b", name: "Write notes", status: "in_progress" }),
        makeItem({ id: "c", name: "Submit lab", status: "done" }),
        makeItem({ id: "d", name: "Review notes", status: "done" }),
      ],
      total: 4,
    });
    vi.spyOn(api, "readiness").mockResolvedValue({
      status: "ok",
      database: "ok",
    });
    renderWithQuery(
      <>
        <SiteHeader />
        <HomePage />
      </>,
    );
    expect(
      screen.getByRole("heading", { name: /Welcome back!/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("student@example.com")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Sign out" }),
    ).toBeInTheDocument();
    await screen.findByRole("region", { name: "Done summary" });
    expect(
      within(screen.getByRole("region", { name: "To do summary" })).getByText(
        "1",
      ),
    ).toBeInTheDocument();
    expect(
      within(
        screen.getByRole("region", { name: "In progress summary" }),
      ).getByText("1"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Done summary" })).getByText(
        "2",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Read chapter")).toHaveLength(2);
    expect(await screen.findByText("Connected")).toBeInTheDocument();
  });
  it("uses an actual name claim and shows an honest empty state", async () => {
    mocked.auth.isAuthenticated = true;
    mocked.auth.user.profile.name = "Sam";
    vi.spyOn(api, "listItems").mockResolvedValue({ items: [], total: 0 });
    vi.spyOn(api, "readiness").mockRejectedValue(new Error("offline"));
    renderWithQuery(<HomePage />);
    expect(
      screen.getByRole("heading", { name: /Welcome back, Sam!/ }),
    ).toBeInTheDocument();
    expect(await screen.findByText("A fresh start")).toBeInTheDocument();
    expect(await screen.findByText("Unavailable")).toBeInTheDocument();
  });
  it("fetches subsequent pages so summaries include tasks beyond the API page limit", async () => {
    const list = vi
      .spyOn(api, "listItems")
      .mockResolvedValueOnce({
        items: Array.from({ length: 100 }, (_, i) =>
          makeItem({ id: String(i) }),
        ),
        total: 101,
      })
      .mockResolvedValueOnce({
        items: [makeItem({ id: "last", status: "done" })],
        total: 101,
      });
    const data = await fetchItems((params) =>
      api.listItems(params, { accessToken: "test-access" }),
    );
    expect(data.items).toHaveLength(101);
    expect(list).toHaveBeenLastCalledWith(
      { limit: 100, offset: 100 },
      { accessToken: "test-access" },
    );
  });
});
