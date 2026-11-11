import { ConcertEvent } from '../data/events';
import { authenticatedRequest } from './auth';

export type Recommendation = {
  event: ConcertEvent;
  score: number;
  reasons: string[];
};

export type RecommendationsResponse = {
  items: Recommendation[];
  model: string;
};

export async function fetchRecommendations(limit = 20) {
  return authenticatedRequest<RecommendationsResponse>(
    `/api/v1/recommendations?limit=${limit}`,
  );
}
