import type { Auth } from 'firebase/auth';
import { signInWithEmailAndPassword as firebaseSignIn, signOut as firebaseSignOut } from 'firebase/auth';

export async function signInWithEmail(auth: Auth, email: string, password: string) {
  return await firebaseSignIn(auth, email, password);
}

export async function signOut(auth: Auth) {
  return await firebaseSignOut(auth);
}
