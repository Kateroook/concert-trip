import { useEffect, useState } from 'react';

import * as recommendationsApi from '../api/recommendations';

export function useRecommendations(enabled: boolean) {
  const [recommendations, setRecommendations] = useState<
    recommendationsApi.Recommendation[]
  >([]);
  const [model, setModel] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    setLoading(true);
    setError(null);
    recommendationsApi
      .fetchRecommendations()
      .then(response => {
        if (active) {
          setRecommendations(response.items);
          setModel(response.model);
        }
      })
      .catch(requestError => {
        if (active) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : 'Could not load recommendations',
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
    recommendations,
    model,
    loading,
    error,
    retry: () => setReloadToken(value => value + 1),
  };
}
