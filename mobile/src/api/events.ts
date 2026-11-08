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
  return fetchEventsPage(query, 1);
}

async function fetchEventsPage(
  query: EventQuery,
  page: number,
): Promise<EventsResponse> {
  const params = new URLSearchParams({ page: String(page), page_size: '100' });
  if (query.q) params.set('q', query.q);
  if (query.country && query.country !== 'All')
    params.set('country', query.country);
  if (query.status && query.status !== 'all')
    params.set('status', query.status);

  return authenticatedRequest<EventsResponse>(
    `/api/v1/events?${params.toString()}`,
  );
}

export async function fetchAllEvents(
  query: EventQuery = {},
): Promise<EventsResponse> {
  const items: ConcertEvent[] = [];
  let page = 1;
  let response: EventsResponse = {
    items: [],
    total: 0,
    page: 1,
    pageSize: 100,
  };

  do {
    response = await fetchEventsPage(query, page);
    items.push(...response.items);
    page += 1;
  } while (items.length < response.total && response.items.length > 0);

  return { ...response, items, page: 1, pageSize: items.length };
}
