jest.mock('../src/api/auth', () => ({
  authenticatedRequest: jest.fn(),
}));

import { fetchEvents } from '../src/api/events';
import { authenticatedRequest } from '../src/api/auth';

const requestMock = authenticatedRequest as jest.MockedFunction<typeof authenticatedRequest>;

describe('fetchEvents', () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it('requests the events endpoint with filters', async () => {
    requestMock.mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 100 });

    await fetchEvents({ country: 'GB', status: 'available', q: 'Tame Impala' });

    expect(requestMock).toHaveBeenCalledWith(
      '/api/v1/events?page=1&page_size=100&q=Tame+Impala&country=GB&status=available',
    );
  });

  it('raises an error for a non-success response', async () => {
    requestMock.mockRejectedValue(new Error('Events request failed (503)'));

    await expect(fetchEvents()).rejects.toThrow('Events request failed (503)');
  });
});
