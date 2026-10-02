import 'firebase/auth';

declare module 'firebase/auth' {
  export interface ReactNativeAsyncStorage {
    setItem(key: string, value: string): Promise<void>;
    getItem(key: string): Promise<string | null>;
    removeItem(key: string): Promise<void>;
  }

  export interface Persistence {
    readonly type: string;
  }

  export function getReactNativePersistence(storage: ReactNativeAsyncStorage): Persistence;
}
