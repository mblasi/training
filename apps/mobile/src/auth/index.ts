import type { Auth } from 'firebase/auth';
import { signInWithEmailAndPassword as firebaseSignIn, signInWithCredential, signOut as firebaseSignOut, GoogleAuthProvider } from 'firebase/auth';
import { GoogleSignin } from '@react-native-google-signin/google-signin';

export async function signInWithEmail(auth: Auth, email: string, password: string) {
  return await firebaseSignIn(auth, email, password);
}

export async function signInWithGoogle(auth: Auth) {
  const result = await GoogleSignin.signIn();
  
  if (result.type !== 'success') {
    throw new Error('Google sign in cancelled');
  }
  
  const { idToken } = result.data;
  const credential = GoogleAuthProvider.credential(idToken);
  return await signInWithCredential(auth, credential);
}

export async function signOut(auth: Auth) {
  return await firebaseSignOut(auth);
}
