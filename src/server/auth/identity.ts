import { cert, getApps, initializeApp, type App } from "firebase-admin/app";
import { getAuth } from "firebase-admin/auth";

/**
 * Server-side caller identity.
 *
 * Client-side Firebase state is not an authorisation boundary: anyone can forge
 * it. Every route that grants or spends money resolves the caller here, from a
 * verified ID token, and refuses to proceed without one.
 */
export interface Caller {
  uid: string;
  email: string | null;
}

/**
 * Build the Firebase Admin app from the environment.
 *
 * Returns null when credentials are absent, which callers treat as "identity
 * cannot be verified" rather than as "identity is anonymous".
 */
function initializeAdminApp(): App | null {
  const projectId =
    process.env.FIREBASE_PROJECT_ID?.trim() ||
    process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID?.trim();
  const clientEmail = process.env.FIREBASE_CLIENT_EMAIL?.trim();
  const privateKey = process.env.FIREBASE_PRIVATE_KEY?.replace(/\\n/g, "\n").trim();

  if (getApps().length > 0) return getApps()[0];
  if (!projectId || !clientEmail || !privateKey) return null;

  return initializeApp({ credential: cert({ projectId, clientEmail, privateKey }) });
}

function bearerToken(authorization: string | null): string | null {
  if (!authorization) return null;
  const [scheme, token] = authorization.split(" ");
  if (!scheme || scheme.toLowerCase() !== "bearer" || !token) return null;
  return token.trim() || null;
}

/** Resolve the caller, or null when the request is unauthenticated. */
export async function resolveCaller(authorization: string | null): Promise<Caller | null> {
  const token = bearerToken(authorization);
  if (!token) return null;

  const app = initializeAdminApp();
  if (!app) return null;

  try {
    const decoded = await getAuth(app).verifyIdToken(token, true);
    return { uid: decoded.uid, email: decoded.email ?? null };
  } catch {
    return null;
  }
}