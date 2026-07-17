import { FirebaseError } from "firebase/app";
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
  onAuthStateChanged,
  type Unsubscribe,
} from "firebase/auth";
import { AuthUser } from "@/models/auth";
import { getFirebaseAuth, isFirebaseConfigured } from "@/lib/firebase";

export { isFirebaseConfigured };

const NOT_CONFIGURED = "Autentikasi belum dikonfigurasi.";
const SANDBOX_USERS_KEY = "suara-nafas:auth-users:v1";
const SANDBOX_SESSION_KEY = "suara-nafas:auth-session:v1";

interface SandboxAccount extends AuthUser {
  passwordHash: string;
  passwordSalt: string;
}

function canUseSandboxAuth(): boolean {
  return typeof window !== "undefined" && "localStorage" in window;
}

function readSandboxAccounts(): SandboxAccount[] {
  if (!canUseSandboxAuth()) return [];

  try {
    const value = window.localStorage.getItem(SANDBOX_USERS_KEY);
    return value ? (JSON.parse(value) as SandboxAccount[]) : [];
  } catch {
    return [];
  }
}

function readSandboxSession(): AuthUser | null {
  if (!canUseSandboxAuth()) return null;

  try {
    const value = window.localStorage.getItem(SANDBOX_SESSION_KEY);
    return value ? (JSON.parse(value) as AuthUser) : null;
  } catch {
    return null;
  }
}

function writeSandboxSession(user: AuthUser | null): void {
  if (!canUseSandboxAuth()) return;

  if (user) {
    window.localStorage.setItem(SANDBOX_SESSION_KEY, JSON.stringify(user));
  } else {
    window.localStorage.removeItem(SANDBOX_SESSION_KEY);
  }
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}

function hexToBytes(value: string): Uint8Array<ArrayBuffer> {
  const bytes = new Uint8Array(value.length / 2);
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = Number.parseInt(value.slice(index * 2, index * 2 + 2), 16);
  }
  return bytes;
}

async function hashPassword(
  password: string,
  salt: Uint8Array<ArrayBuffer>,
): Promise<string> {
  const key = await window.crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const derived = await window.crypto.subtle.deriveBits(
    {
      name: "PBKDF2",
      hash: "SHA-256",
      salt,
      iterations: 120_000,
    },
    key,
    256,
  );
  return bytesToHex(new Uint8Array(derived));
}

function shouldUseSandbox(error: unknown): boolean {
  return (
    error instanceof FirebaseError &&
    (error.code === "auth/configuration-not-found" ||
      error.message.includes("CONFIGURATION_NOT_FOUND"))
  );
}

function mapAuthError(error: unknown): Error {
  if (!(error instanceof FirebaseError)) {
    return error instanceof Error ? error : new Error("Autentikasi gagal.");
  }

  const messages: Record<string, string> = {
    "auth/email-already-in-use": "Email sudah terdaftar. Silakan masuk.",
    "auth/invalid-credential": "Email atau kata sandi salah.",
    "auth/invalid-email": "Format email tidak valid.",
    "auth/too-many-requests": "Terlalu banyak percobaan. Coba lagi nanti.",
    "auth/weak-password": "Kata sandi minimal 6 karakter.",
  };

  return new Error(messages[error.code] ?? "Autentikasi gagal. Coba lagi.");
}

async function signInSandbox(
  email: string,
  password: string,
): Promise<AuthUser> {
  const normalizedEmail = email.trim().toLowerCase();
  const account = readSandboxAccounts().find(
    (item) => item.email === normalizedEmail,
  );

  if (!account) throw new Error("Email atau kata sandi salah.");

  const passwordHash = await hashPassword(
    password,
    hexToBytes(account.passwordSalt),
  );
  if (passwordHash !== account.passwordHash) {
    throw new Error("Email atau kata sandi salah.");
  }

  const user = { uid: account.uid, email: account.email };
  writeSandboxSession(user);
  return user;
}

async function signUpSandbox(
  email: string,
  password: string,
): Promise<AuthUser> {
  const normalizedEmail = email.trim().toLowerCase();
  const accounts = readSandboxAccounts();

  if (accounts.some((item) => item.email === normalizedEmail)) {
    throw new Error("Email sudah terdaftar. Silakan masuk.");
  }

  const user = { uid: window.crypto.randomUUID(), email: normalizedEmail };
  const passwordSalt = window.crypto.getRandomValues(new Uint8Array(16));
  const account = {
    ...user,
    passwordHash: await hashPassword(password, passwordSalt),
    passwordSalt: bytesToHex(passwordSalt),
  };
  window.localStorage.setItem(
    SANDBOX_USERS_KEY,
    JSON.stringify([...accounts, account]),
  );
  writeSandboxSession(user);
  return user;
}

export function observeAuth(
  callback: (user: AuthUser | null) => void,
): Unsubscribe {
  const auth = getFirebaseAuth();
  const sandboxSession = readSandboxSession();

  if (!auth) {
    callback(sandboxSession);
    return () => {};
  }

  return onAuthStateChanged(auth, (user) => {
    callback(
      user ? { uid: user.uid, email: user.email } : readSandboxSession(),
    );
  });
}

export async function signIn(email: string, password: string): Promise<AuthUser> {
  const auth = getFirebaseAuth();
  if (!auth) {
    if (canUseSandboxAuth()) return signInSandbox(email, password);
    throw new Error(NOT_CONFIGURED);
  }

  try {
    const credential = await signInWithEmailAndPassword(auth, email, password);
    return { uid: credential.user.uid, email: credential.user.email };
  } catch (error) {
    if (shouldUseSandbox(error)) return signInSandbox(email, password);
    throw mapAuthError(error);
  }
}

export async function signUp(email: string, password: string): Promise<AuthUser> {
  const auth = getFirebaseAuth();
  if (!auth) {
    if (canUseSandboxAuth()) return signUpSandbox(email, password);
    throw new Error(NOT_CONFIGURED);
  }

  try {
    const credential = await createUserWithEmailAndPassword(auth, email, password);
    return { uid: credential.user.uid, email: credential.user.email };
  } catch (error) {
    if (shouldUseSandbox(error)) return signUpSandbox(email, password);
    throw mapAuthError(error);
  }
}

export async function signOutUser(): Promise<void> {
  writeSandboxSession(null);

  const auth = getFirebaseAuth();
  if (!auth) return;
  await firebaseSignOut(auth);
}
