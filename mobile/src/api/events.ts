import { API_BASE_URL } from '../config';
import { ConcertEvent, EventStatus } from '../data/events';

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

  const response = await fetch(
    `${API_BASE_URL}/api/v1/events?${params.toString()}`,
  );
  if (!response.ok) {
    throw new Error(`Events request failed (${response.status})`);
  }
  return response.json() as Promise<EventsResponse>;
}
