import { Linking } from 'react-native';

import { authenticatedRequest } from './auth';

export type SpotifyStatus = {
  connected: boolean;
  providerAccountId: string | null;
  lastSyncedAt: string | null;
  preferenceCount: number;
};

type AuthorizeResponse = { authorizeUrl: string };
type SyncResponse = { imported: number; status: SpotifyStatus };

export async function getSpotifyStatus() {
  return authenticatedRequest<SpotifyStatus>(
    '/api/v1/integrations/spotify/status',
  );
}

export async function connectSpotify() {
  const response = await authenticatedRequest<AuthorizeResponse>(
    '/api/v1/integrations/spotify/authorize',
  );
  await Linking.openURL(response.authorizeUrl);
}

export async function syncSpotify() {
  const response = await authenticatedRequest<SyncResponse>(
    '/api/v1/integrations/spotify/sync',
    { method: 'POST' },
  );
  return response.status;
}

export async function disconnectSpotify() {
  await authenticatedRequest('/api/v1/integrations/spotify', {
    method: 'DELETE',
  });
}
