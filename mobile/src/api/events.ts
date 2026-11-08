import { ConcertEvent, EventStatus } from '../data/events';
import { authenticatedRequest } from './auth';

export type EventsResponse = {
  items: ConcertEvent[];
  total: number;
  page: number;
  pageSize: number;
};

export type EventQuery = {
  q?: string;
  country?: string;
  status?: EventStatus | 'all';
};

export async function fetchEvents(
  query: EventQuery = {},
): Promise<EventsResponse> {
  const params = new URLSearchParams({ page: '1', page_size: '100' });
  if (query.q) params.set('q', query.q);
  if (query.country && query.country !== 'All')
    params.set('country', query.country);
  if (query.status && query.status !== 'all')
    params.set('status', query.status);

  return authenticatedRequest<EventsResponse>(
    `/api/v1/events?${params.toString()}`,
  );
}
