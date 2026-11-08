import { useEffect, useState } from 'react';

import { fetchEvents } from '../api/events';
import { ConcertEvent } from '../data/events';

export function useEvents(enabled = true) {
  const [events, setEvents] = useState<ConcertEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let active = true;
    if (!enabled) {
      setEvents([]);
      setLoading(false);
      setError(null);
      return () => {
        active = false;
      };
    }
    setLoading(true);
    setError(null);

    fetchEvents()
      .then(response => {
        if (active) setEvents(response.items);
      })
      .catch(requestError => {
        if (active) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : 'Could not load events',
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [enabled, reloadToken]);

  return {
    events,
    loading,
    error,
    retry: () => setReloadToken(value => value + 1),
  };
}
