// Decodes a JWT's payload without verifying the signature — client-side use
// only (e.g. reading tenant_id/exp for UI state). The server independently
// verifies every token on every request; this never gates access.
export function parseJwt(token) {
  try {
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(b64));
  } catch {
    return {};
  }
}
