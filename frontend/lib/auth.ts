import type { AuthProviderNoUserManagerProps } from "react-oidc-context";
import { WebStorageStateStore } from "oidc-client-ts";

export function authConfig(): AuthProviderNoUserManagerProps | null {
  const authority = process.env.NEXT_PUBLIC_COGNITO_AUTHORITY;
  const clientId = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;
  const domain = process.env.NEXT_PUBLIC_COGNITO_DOMAIN;
  const redirectUri = process.env.NEXT_PUBLIC_AUTH_REDIRECT_URI;
  const logoutUri = process.env.NEXT_PUBLIC_AUTH_LOGOUT_URI;
  if (!authority || !clientId || !domain || !redirectUri || !logoutUri)
    return null;
  return {
    authority,
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: "openid email profile",
    disablePKCE: false,
    automaticSilentRenew: false,
    // ID-token claims contain email; avoid an unnecessary userinfo request.
    loadUserInfo: false,
    ...(typeof window !== "undefined"
      ? {
          userStore: new WebStorageStateStore({ store: window.sessionStorage }),
          stateStore: new WebStorageStateStore({
            store: window.sessionStorage,
          }),
        }
      : {}),
    onSigninCallback: () => {
      window.history.replaceState({}, document.title, "/auth/callback/");
      window.location.replace("/");
    },
  };
}

export function cognitoLogoutUrl(): string {
  const domain = process.env.NEXT_PUBLIC_COGNITO_DOMAIN;
  const clientId = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;
  const logoutUri = process.env.NEXT_PUBLIC_AUTH_LOGOUT_URI;
  if (!domain || !clientId || !logoutUri)
    throw new Error("Sign out is not configured");
  const url = new URL("/logout", domain);
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("logout_uri", logoutUri);
  return url.toString();
}
