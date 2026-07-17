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

export function observeAuth(
  callback: (user: AuthUser | null) => void,
): Unsubscribe {
  const auth = getFirebaseAuth();
  if (!auth) {
    callback(null);
    return () => {};
  }
  return onAuthStateChanged(auth, (user) => {
    callback(user ? { uid: user.uid, email: user.email } : null);
  });
}

export async function signIn(email: string, password: string): Promise<AuthUser> {
  const auth = getFirebaseAuth();
  if (!auth) throw new Error(NOT_CONFIGURED);
  const credential = await signInWithEmailAndPassword(auth, email, password);
  return { uid: credential.user.uid, email: credential.user.email };
}

export async function signUp(email: string, password: string): Promise<AuthUser> {
  const auth = getFirebaseAuth();
  if (!auth) throw new Error(NOT_CONFIGURED);
  const credential = await createUserWithEmailAndPassword(auth, email, password);
  return { uid: credential.user.uid, email: credential.user.email };
}

export async function signOutUser(): Promise<void> {
  const auth = getFirebaseAuth();
  if (!auth) return;
  await firebaseSignOut(auth);
}
