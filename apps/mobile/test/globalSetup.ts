export default function setup(): void {
  if (!process.env.EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST) {
    throw new Error(
      'EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST no definido. Los tests de integración requieren el emulador de Firebase Auth.'
    );
  }
}
