export type EventStatus =
  | 'available'
  | 'limited'
  | 'low'
  | 'sold_out'
  | 'onsale'
  | 'offsale'
  | 'canceled'
  | 'postponed'
  | 'rescheduled'
  | 'unknown';

export type ConcertEvent = {
  id: string;
  artist: string;
  venue: string;
  city: string;
  country: string;
  eventDate: string | null;
  dateStatus?: 'confirmed' | 'tba' | 'tbd' | 'unknown';
  onSaleDate: string | null;
  ticketType: string;
  status: EventStatus;
  url: string;
};

export const events: ConcertEvent[] = [
  {
    id: 'seed-001',
    artist: 'Tame Impala',
    venue: 'Co-op Live',
    city: 'Manchester',
    country: 'GB',
    eventDate: '2027-05-28',
    onSaleDate: '2026-08-28',
    ticketType: 'Standing - General Admission',
    status: 'limited',
    url: 'https://example.org/seed-001',
  },
  {
    id: 'seed-002',
    artist: 'Tame Impala',
    venue: 'The O2',
    city: 'London',
    country: 'GB',
    eventDate: '2027-06-01',
    onSaleDate: '2026-08-28',
    ticketType: 'Golden Circle Standing',
    status: 'low',
    url: 'https://example.org/seed-002',
  },
  {
    id: 'seed-003',
    artist: 'Tame Impala',
    venue: 'Rotterdam Ahoy',
    city: 'Rotterdam',
    country: 'NL',
    eventDate: '2027-06-07',
    onSaleDate: '2026-08-28',
    ticketType: 'Vloer staanplaats',
    status: 'available',
    url: 'https://example.org/seed-003',
  },
  {
    id: 'seed-004',
    artist: 'Tame Impala',
    venue: 'Accor Arena',
    city: 'Paris',
    country: 'FR',
    eventDate: '2027-06-12',
    onSaleDate: '2026-09-02',
    ticketType: 'Fosse Or',
    status: 'available',
    url: 'https://example.org/seed-004',
  },
  {
    id: 'seed-005',
    artist: 'Tame Impala',
    venue: 'Lanxess Arena',
    city: 'Koeln',
    country: 'DE',
    eventDate: '2027-06-17',
    onSaleDate: '2026-08-28',
    ticketType: 'Stehplatz Innenraum',
    status: 'sold_out',
    url: 'https://example.org/seed-005',
  },
];
