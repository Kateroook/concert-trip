import { useEffect, useState } from 'react';

import * as authApi from '../api/auth';

export type AuthStatus = 'loading' | 'signed_out' | 'signed_in';

export function useAuth() {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<authApi.AuthUser | null>(null);

  useEffect(() => {
    let active = true;
    authApi
      .currentUser()
      .then(currentUser => {
        if (active) {
          setUser(currentUser);
          setStatus('signed_in');
        }
      })
      .catch(() => {
        if (active) setStatus('signed_out');
      });
    return () => {
      active = false;
    };
  }, []);

  const signIn = async (email: string, password: string) => {
    await authApi.login(email, password);
    const currentUser = await authApi.currentUser();
    setUser(currentUser);
    setStatus('signed_in');
  };

  const signOut = async () => {
    await authApi.logout();
    setUser(null);
    setStatus('signed_out');
  };

  return {
    status,
    user,
    signIn,
    signOut,
    register: authApi.register,
    verifyEmail: authApi.verifyEmail,
  };
}
