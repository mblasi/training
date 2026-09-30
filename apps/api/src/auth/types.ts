export interface AuthUser {
  id: string;
  uid: string;
  email: string;
  role: 'user' | 'admin';
}

export interface DecodedIdToken {
  uid: string;
  email?: string;
  email_verified?: boolean;
}
