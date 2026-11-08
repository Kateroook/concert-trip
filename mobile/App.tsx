import { useMemo, useState } from 'react';
import {
  FlatList,
  Linking,
  Pressable,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import {
  SafeAreaProvider,
  useSafeAreaInsets,
} from 'react-native-safe-area-context';
import { AuthScreen } from './src/components/AuthScreen';
import { Recommendation } from './src/api/recommendations';
import { EventStatus, ConcertEvent } from './src/data/events';
import { useAuth } from './src/hooks/useAuth';
import { useEvents } from './src/hooks/useEvents';
import { useSpotify } from './src/hooks/useSpotify';
import { useRecommendations } from './src/hooks/useRecommendations';

function App() {
  return (
    <SafeAreaProvider>
      <StatusBar barStyle="dark-content" />
      <AppContent />
    </SafeAreaProvider>
  );
}

function AppContent() {
  const safeAreaInsets = useSafeAreaInsets();
  const auth = useAuth();
  const spotify = useSpotify(auth.status === 'signed_in');
  const [view, setView] = useState<'events' | 'recommended'>('events');
  const recommendationState = useRecommendations(
    auth.status === 'signed_in' && view === 'recommended',
  );
  const { events, loading, error, retry } = useEvents(
    auth.status === 'signed_in',
  );
  const [query, setQuery] = useState('');
  const [country, setCountry] = useState('All');
  const [status, setStatus] = useState<EventStatus | 'all'>('all');
  const countries = useMemo(
    () => ['All', ...Array.from(new Set(events.map(event => event.country)))],
    [events],
  );
  const filteredEvents = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return events.filter(event => {
      const matchesQuery =
        !normalizedQuery ||
        `${event.artist} ${event.city} ${event.venue}`
          .toLowerCase()
          .includes(normalizedQuery);
      const matchesCountry = country === 'All' || event.country === country;
      const matchesStatus = status === 'all' || event.status === status;

      return matchesQuery && matchesCountry && matchesStatus;
    });
  }, [country, events, query, status]);

  if (auth.status === 'loading') {
    return (
      <View style={[styles.container, styles.centered]}>
        <Text style={styles.empty}>Restoring your session...</Text>
      </View>
    );
  }

  if (auth.status === 'signed_out') {
    return (
      <AuthScreen
        onSignIn={auth.signIn}
        onRegister={async (email, password) => {
          const response = await auth.register(email, password);
          return response.verificationToken;
        }}
        onVerify={async token => {
          await auth.verifyEmail(token);
        }}
      />
    );
  }

  const resetFilters = () => {
    setQuery('');
    setCountry('All');
    setStatus('all');
  };

  const renderListItem = ({
    item,
  }: {
    item: ConcertEvent | Recommendation;
  }) => {
    if (showingRecommendations) {
      return <RecommendationCard recommendation={item as Recommendation} />;
    }
    return <EventCard event={item as ConcertEvent} />;
  };
  const showingRecommendations = view === 'recommended';
  const listLoading = showingRecommendations
    ? recommendationState.loading
    : loading;
  const listError = showingRecommendations
    ? recommendationState.error
    : error;
  const listData: Array<ConcertEvent | Recommendation> = showingRecommendations
    ? recommendationState.recommendations
    : filteredEvents;

  return (
    <View style={[styles.container, { paddingTop: safeAreaInsets.top }]}>
      <FlatList<ConcertEvent | Recommendation>
        data={listData}
        keyExtractor={item =>
          showingRecommendations
            ? (item as Recommendation).event.id
            : (item as ConcertEvent).id
        }
        renderItem={renderListItem}
        contentContainerStyle={styles.content}
        ListHeaderComponent={
          <>
            <View style={styles.accountRow}>
              <Text style={styles.accountEmail}>{auth.user?.email}</Text>
              <Pressable onPress={auth.signOut} accessibilityRole="button">
                <Text style={styles.reset}>Sign out</Text>
              </Pressable>
            </View>
            <View style={styles.spotifyRow}>
              <View style={styles.spotifyCopy}>
                <Text style={styles.spotifyTitle}>Spotify preferences</Text>
                <Text style={styles.spotifySubtitle}>
                  {spotify.status?.connected
                    ? `${spotify.status.preferenceCount} preferences synced`
                    : 'Connect your listening history'}
                </Text>
              </View>
              <View style={styles.spotifyActions}>
                <Pressable
                  onPress={
                    spotify.status?.connected ? spotify.sync : spotify.connect
                  }
                  disabled={spotify.busy}
                  style={styles.spotifyButton}
                  accessibilityRole="button"
                >
                  <Text style={styles.spotifyButtonText}>
                    {spotify.busy
                      ? '...'
                      : spotify.status?.connected
                      ? 'Sync'
                      : 'Connect'}
                  </Text>
                </Pressable>
                {spotify.status?.connected && (
                  <Pressable
                    onPress={spotify.disconnect}
                    disabled={spotify.busy}
                    accessibilityRole="button"
                  >
                    <Text style={styles.spotifyDisconnect}>Disconnect</Text>
                  </Pressable>
                )}
              </View>
            </View>
            {spotify.error && (
              <Text style={styles.spotifyError}>{spotify.error}</Text>
            )}
            <View style={styles.viewToggle}>
              <Pressable
                onPress={() => setView('events')}
                style={[styles.viewButton, view === 'events' && styles.viewButtonSelected]}
                accessibilityRole="button"
              >
                <Text style={[styles.viewButtonText, view === 'events' && styles.viewButtonTextSelected]}>Events</Text>
              </Pressable>
              <Pressable
                onPress={() => setView('recommended')}
                style={[styles.viewButton, view === 'recommended' && styles.viewButtonSelected]}
                accessibilityRole="button"
              >
                <Text style={[styles.viewButtonText, view === 'recommended' && styles.viewButtonTextSelected]}>For you</Text>
              </Pressable>
            </View>
            <Text style={styles.eyebrow}>CONCERTRIP</Text>
            <Text style={styles.title}>Live shows worth the trip.</Text>
            <Text style={styles.subtitle}>
              A small preview of concerts we are tracking for you.
            </Text>
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder="Search artist, city or venue"
              placeholderTextColor="#8c8880"
              style={styles.search}
              accessibilityLabel="Search events"
            />
            <FilterRow
              label="Country"
              options={countries}
              selected={country}
              onSelect={setCountry}
            />
            <FilterRow
              label="Status"
              options={[
                'all',
                ...Array.from(new Set(events.map(event => event.status))),
              ]}
              selected={status}
              onSelect={value => setStatus(value as EventStatus | 'all')}
            />
            <View style={styles.resultsRow}>
              <Text style={styles.results}>
                {listLoading
                  ? 'Loading...'
                  : showingRecommendations
                    ? `${recommendationState.recommendations.length} recommendations`
                    : `${filteredEvents.length} events`}
              </Text>
              {(query || country !== 'All' || status !== 'all') && (
                <Pressable onPress={resetFilters} accessibilityRole="button">
                  <Text style={styles.reset}>Reset filters</Text>
                </Pressable>
              )}
            </View>
          </>
        }
        ListEmptyComponent={
          listLoading ? (
            <Text style={styles.empty}>Loading events from ConcerTrip...</Text>
          ) : listError ? (
            <View style={styles.emptyState}>
              <Text style={styles.empty}>{listError}</Text>
              <Pressable
                onPress={showingRecommendations ? recommendationState.retry : retry}
                style={styles.retryButton}
                accessibilityRole="button"
              >
                <Text style={styles.ticketButtonText}>Try again</Text>
              </Pressable>
            </View>
          ) : (
            <Text style={styles.empty}>No concerts match these filters.</Text>
          )
        }
        showsVerticalScrollIndicator={false}
      />
    </View>
  );
}

function FilterRow({
  label,
  options,
  selected,
  onSelect,
}: {
  label: string;
  options: string[];
  selected: string;
  onSelect: (value: string) => void;
}) {
  return (
    <View style={styles.filterGroup}>
      <Text style={styles.filterLabel}>{label}</Text>
      <View style={styles.chips}>
        {options.map(option => (
          <Pressable
            key={option}
            onPress={() => onSelect(option)}
            style={[styles.chip, selected === option && styles.selectedChip]}
            accessibilityRole="button"
            accessibilityState={{ selected: selected === option }}
          >
            <Text
              style={[
                styles.chipText,
                selected === option && styles.selectedChipText,
              ]}
            >
              {option.replace('_', ' ')}
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function EventCard({ event }: { event: ConcertEvent }) {
  const openTickets = async () => {
    const supported = await Linking.canOpenURL(event.url);
    if (supported) {
      await Linking.openURL(event.url);
    }
  };

  return (
    <View style={styles.card}>
      <View style={styles.cardTopline}>
        <Text style={styles.date}>{formatDate(event.eventDate)}</Text>
        <Text style={[styles.status, getStatusStyle(event.status)]}>
          {event.status.replace('_', ' ')}
        </Text>
      </View>
      <Text style={styles.artist}>{event.artist}</Text>
      <Text style={styles.venue}>{event.venue}</Text>
      <Text style={styles.location}>
        {event.city}, {event.country}
      </Text>
      <View style={styles.cardFooter}>
        <Text style={styles.ticketType}>{event.ticketType}</Text>
        <Pressable
          onPress={openTickets}
          style={styles.ticketButton}
          accessibilityRole="button"
        >
          <Text style={styles.ticketButtonText}>Tickets</Text>
        </Pressable>
      </View>
    </View>
  );
}

function RecommendationCard({ recommendation }: { recommendation: Recommendation }) {
  return (
    <View>
      <EventCard event={recommendation.event} />
      <View style={styles.recommendationMeta}>
        <Text style={styles.recommendationScore}>
          AI match: {Math.round(recommendation.score * 100)}%
        </Text>
        {recommendation.reasons.map(reason => (
          <Text key={reason} style={styles.recommendationReason}>
            • {reason}
          </Text>
        ))}
      </View>
    </View>
  );
}

function formatDate(value: string | null) {
  if (!value) return 'Date to be announced';
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(`${value}T12:00:00`));
}

function getStatusStyle(status: EventStatus) {
  switch (status) {
    case 'available':
    case 'onsale':
      return styles.status_available;
    case 'limited':
    case 'low':
      return styles.status_limited;
    case 'sold_out':
    case 'offsale':
    case 'canceled':
      return styles.status_sold_out;
    default:
      return styles.status_unknown;
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f6f3ed',
  },
  centered: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: {
    padding: 20,
    paddingBottom: 36,
  },
  accountRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 28,
  },
  accountEmail: {
    color: '#67645d',
    flex: 1,
    fontSize: 12,
    marginRight: 12,
  },
  spotifyRow: {
    alignItems: 'center',
    backgroundColor: '#e4eee6',
    borderRadius: 12,
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 24,
    padding: 14,
  },
  spotifyCopy: {
    flex: 1,
    marginRight: 12,
  },
  spotifyTitle: {
    color: '#1e2825',
    fontSize: 14,
    fontWeight: '800',
  },
  spotifySubtitle: {
    color: '#53645a',
    fontSize: 12,
    marginTop: 4,
  },
  spotifyActions: {
    alignItems: 'flex-end',
    gap: 7,
  },
  spotifyButton: {
    backgroundColor: '#1e2825',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  spotifyButtonText: {
    color: '#fffdf8',
    fontSize: 12,
    fontWeight: '800',
  },
  spotifyDisconnect: {
    color: '#964238',
    fontSize: 11,
    fontWeight: '700',
  },
  spotifyError: {
    color: '#964238',
    fontSize: 12,
    marginBottom: 16,
  },
  viewToggle: {
    backgroundColor: '#ebe6dc',
    borderRadius: 10,
    flexDirection: 'row',
    marginBottom: 22,
    padding: 3,
  },
  viewButton: {
    borderRadius: 8,
    flex: 1,
    paddingVertical: 9,
  },
  viewButtonSelected: {
    backgroundColor: '#1e2825',
  },
  viewButtonText: {
    color: '#514e47',
    fontSize: 13,
    fontWeight: '700',
    textAlign: 'center',
  },
  viewButtonTextSelected: {
    color: '#fffdf8',
  },
  recommendationMeta: {
    backgroundColor: '#e4eee6',
    borderRadius: 10,
    marginBottom: 12,
    marginTop: -7,
    padding: 12,
  },
  recommendationScore: {
    color: '#1e2825',
    fontSize: 13,
    fontWeight: '800',
  },
  recommendationReason: {
    color: '#53645a',
    fontSize: 12,
    marginTop: 4,
  },
  eyebrow: {
    color: '#bd4b2f',
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 2,
    marginBottom: 12,
  },
  title: {
    color: '#1e2825',
    fontSize: 32,
    fontWeight: '800',
    lineHeight: 36,
    maxWidth: 330,
  },
  subtitle: {
    color: '#67645d',
    fontSize: 15,
    lineHeight: 22,
    marginTop: 10,
    marginBottom: 20,
  },
  search: {
    backgroundColor: '#fffdf8',
    borderColor: '#ded8cc',
    borderRadius: 12,
    borderWidth: 1,
    color: '#1e2825',
    fontSize: 15,
    paddingHorizontal: 15,
    paddingVertical: 13,
  },
  filterGroup: {
    marginTop: 16,
  },
  filterLabel: {
    color: '#67645d',
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    backgroundColor: '#ebe6dc',
    borderRadius: 18,
    paddingHorizontal: 13,
    paddingVertical: 8,
  },
  selectedChip: {
    backgroundColor: '#1e2825',
  },
  chipText: {
    color: '#514e47',
    fontSize: 13,
    textTransform: 'capitalize',
  },
  selectedChipText: {
    color: '#fffdf8',
  },
  resultsRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 24,
    marginBottom: 10,
  },
  results: {
    color: '#67645d',
    fontSize: 13,
    fontWeight: '700',
  },
  reset: {
    color: '#bd4b2f',
    fontSize: 13,
    fontWeight: '700',
  },
  card: {
    backgroundColor: '#fffdf8',
    borderColor: '#e5ded2',
    borderRadius: 16,
    borderWidth: 1,
    marginBottom: 12,
    padding: 16,
  },
  cardTopline: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  date: {
    color: '#bd4b2f',
    fontSize: 13,
    fontWeight: '800',
  },
  status: {
    borderRadius: 10,
    fontSize: 11,
    fontWeight: '800',
    overflow: 'hidden',
    paddingHorizontal: 8,
    paddingVertical: 4,
    textTransform: 'uppercase',
  },
  status_available: { backgroundColor: '#d9eadb', color: '#2c6542' },
  status_limited: { backgroundColor: '#f6dfbd', color: '#8b5a1b' },
  status_low: { backgroundColor: '#f6dfbd', color: '#8b5a1b' },
  status_sold_out: { backgroundColor: '#ead8d5', color: '#964238' },
  status_unknown: { backgroundColor: '#e5e0d6', color: '#67645d' },
  artist: {
    color: '#1e2825',
    fontSize: 22,
    fontWeight: '800',
    marginTop: 16,
  },
  venue: {
    color: '#403f3a',
    fontSize: 15,
    fontWeight: '700',
    marginTop: 5,
  },
  location: {
    color: '#77736b',
    fontSize: 14,
    marginTop: 3,
  },
  cardFooter: {
    alignItems: 'center',
    borderTopColor: '#eee8de',
    borderTopWidth: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 16,
    paddingTop: 13,
  },
  ticketType: {
    color: '#77736b',
    flex: 1,
    fontSize: 12,
    marginRight: 10,
  },
  ticketButton: {
    backgroundColor: '#bd4b2f',
    borderRadius: 9,
    paddingHorizontal: 14,
    paddingVertical: 9,
  },
  ticketButtonText: {
    color: '#fffdf8',
    fontSize: 13,
    fontWeight: '800',
  },
  empty: {
    color: '#67645d',
    fontSize: 15,
    paddingVertical: 28,
    textAlign: 'center',
  },
  emptyState: {
    alignItems: 'center',
  },
  retryButton: {
    backgroundColor: '#bd4b2f',
    borderRadius: 9,
    paddingHorizontal: 14,
    paddingVertical: 9,
  },
});

export default App;
