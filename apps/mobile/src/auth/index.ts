import type { Auth } from 'firebase/auth';
import { signInWithCredential, GoogleAuthProvider } from 'firebase/auth';
import { GoogleSignin } from '@react-native-google-signin/google-signin';

export { signInWithEmail, signOut } from './email';

export async function signInWithGoogle(auth: Auth) {
  const result = await GoogleSignin.signIn();
  
  if (result.type !== 'success') {
    throw new Error('Google sign in cancelled');
  }
  
  const { idToken } = result.data;
  const credential = GoogleAuthProvider.credential(idToken);
  return await signInWithCredential(auth, credential);
}
