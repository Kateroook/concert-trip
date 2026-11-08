import { Linking } from 'react-native';
import { useCallback, useEffect, useState } from 'react';

import * as spotifyApi from '../api/spotify';

export function useSpotify(enabled: boolean) {
  const [status, setStatus] = useState<spotifyApi.SpotifyStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!enabled) return;
    try {
      setStatus(await spotifyApi.getSpotifyStatus());
      setError(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Spotify status failed',
      );
    }
  }, [enabled]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    if (!enabled) return;
    const handleUrl = ({ url }: { url: string }) => {
      if (url.startsWith('concertrip://spotify/callback')) reload();
    };
    const subscription = Linking.addEventListener('url', handleUrl);
    Linking.getInitialURL().then(url => {
      if (url?.startsWith('concertrip://spotify/callback')) reload();
    });
    return () => subscription.remove();
  }, [enabled, reload]);

  const connect = async () => {
    setBusy(true);
    setError(null);
    try {
      await spotifyApi.connectSpotify();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Spotify connection failed',
      );
    } finally {
      setBusy(false);
    }
  };

  const sync = async () => {
    setBusy(true);
    setError(null);
    try {
      setStatus(await spotifyApi.syncSpotify());
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Spotify sync failed',
      );
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    setError(null);
    try {
      await spotifyApi.disconnectSpotify();
      setStatus({
        connected: false,
        providerAccountId: null,
        lastSyncedAt: null,
        preferenceCount: 0,
      });
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Spotify disconnect failed',
      );
    } finally {
      setBusy(false);
    }
  };

  return { status, busy, error, connect, sync, disconnect, reload };
}
