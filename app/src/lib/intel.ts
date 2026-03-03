/**
 * Authenticated fetch wrapper for Intel API calls.
 * Injects the bearer token from NEXT_PUBLIC_INTEL_API_KEY if set.
 */

const API_KEY = process.env.NEXT_PUBLIC_INTEL_API_KEY || "";

export async function intelFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const headers = new Headers(init?.headers);
  if (API_KEY) {
    headers.set("Authorization", `Bearer ${API_KEY}`);
  }
  return fetch(path, { ...init, headers });
}
