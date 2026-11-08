import { fetchEvents } from '../src/api/events';

const fetchMock = jest.fn();

describe('fetchEvents', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    globalThis.fetch = fetchMock;
  });

  it('requests the events endpoint with filters', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 1, pageSize: 100 }),
    });

    await fetchEvents({ country: 'GB', status: 'available', q: 'Tame Impala' });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://10.0.2.2:8000/api/v1/events?page=1&page_size=100&q=Tame+Impala&country=GB&status=available',
    );
  });

  it('raises an error for a non-success response', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 503 });

    await expect(fetchEvents()).rejects.toThrow('Events request failed (503)');
  });
});
