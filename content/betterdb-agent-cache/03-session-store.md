The session tier is a per-thread key-value store for agent state. It is designed for the patterns that come up in multi-step, multi-turn agents: storing user intent, intermediate reasoning, extracted entities, and tool call context between invocations.

## How It Works

Each session field is stored as an individual Valkey key:

```
betterdb_ac:session:{threadId}:{field}
```

This differs from storing everything in a Redis HASH. Individual keys allow **per-field TTL** - different fields can have different expiry times - and `get()` automatically refreshes the TTL on each read (sliding window). The trade-off is that `getAll()` and `destroyThread()` require a SCAN + pipeline rather than a single `HGETALL` or `DEL`.

## Basic Operations

```typescript
import Valkey from 'iovalkey';
import { AgentCache } from '@betterdb/agent-cache';

const client = new Valkey({ host: 'localhost', port: 6379 });
const cache = new AgentCache({
  client,
  tierDefaults: { session: { ttl: 1800 } }, // 30 min sliding window
});

const threadId = 'user-42-thread-001';

// Write state fields
await cache.session.set(threadId, 'intent', 'book_flight');
await cache.session.set(threadId, 'destination', 'Sofia');
await cache.session.set(threadId, 'departure', '2026-06-01');

// Read a field (also refreshes its TTL)
const intent = await cache.session.get(threadId, 'intent');
// 'book_flight'

// Returns null for fields that don't exist or have expired
const missing = await cache.session.get(threadId, 'return_date');
// null
```

## Getting All Fields

```typescript
const state = await cache.session.getAll(threadId);
console.log(state);
// { intent: 'book_flight', destination: 'Sofia', departure: '2026-06-01' }
```

`getAll()` uses SCAN to find all keys for the thread and fetches them in a pipeline. It is designed for sessions with dozens of fields - not thousands. If you have thousands of fields per thread, consider a HASH-based approach instead.

## Refreshing TTLs

```typescript
// On each user interaction, refresh all session fields to keep the session alive
await cache.session.touch(threadId);
```

`touch()` extends the TTL on every field for the thread. Call it at the start of each agent invocation to prevent partial expiry where some fields outlive others.

## Deleting State

```typescript
// Delete a single field
await cache.session.delete(threadId, 'departure');

// Destroy the entire thread - session state + LangGraph checkpoints
const deleted = await cache.session.destroyThread(threadId);
console.log(`Deleted ${deleted} keys`);
```

`destroyThread()` is the clean shutdown path. Call it when a conversation ends or a user explicitly resets their session.

## Multi-Step Agent Example

Here is a booking agent that accumulates state across multiple tool calls:

```typescript
interface BookingState {
  intent?: string;
  origin?: string;
  destination?: string;
  departure?: string;
  passengerCount?: string;
  searchResults?: string;
}

async function runBookingAgent(threadId: string, userMessage: string) {
  // Load existing state
  const state = await cache.session.getAll(threadId) as BookingState;

  // Extract intent from message (simplified)
  if (userMessage.includes('book') && userMessage.includes('flight')) {
    await cache.session.set(threadId, 'intent', 'book_flight');
  }

  // Extract destination
  const destMatch = userMessage.match(/to (\w+)/i);
  if (destMatch) {
    await cache.session.set(threadId, 'destination', destMatch[1]);
  }

  // Extract departure date
  const dateMatch = userMessage.match(/on (\d{4}-\d{2}-\d{2})/);
  if (dateMatch) {
    await cache.session.set(threadId, 'departure', dateMatch[1]);
  }

  // Refresh all TTLs so the session doesn't partially expire
  await cache.session.touch(threadId);

  // Read current state
  const currentState = await cache.session.getAll(threadId) as BookingState;

  // Search for flights only when we have enough context
  if (currentState.destination && currentState.departure && !currentState.searchResults) {
    const results = await cache.tool.check('search_flights', {
      destination: currentState.destination,
      date: currentState.departure,
    });

    if (!results.hit) {
      const flightData = await searchFlights(currentState);
      await cache.tool.store('search_flights', {
        destination: currentState.destination,
        date: currentState.departure,
      }, JSON.stringify(flightData));
      await cache.session.set(threadId, 'searchResults', JSON.stringify(flightData));
    } else {
      await cache.session.set(threadId, 'searchResults', results.response!);
    }
  }

  return cache.session.getAll(threadId);
}
```

## Session State Patterns

| Pattern | Implementation |
|---------|---------------|
| User intent tracking | `set(thread, 'intent', value)` on each turn |
| Entity accumulation | One field per entity: `set(thread, 'city', 'Sofia')` |
| Conversation stage | `set(thread, 'stage', 'collecting_dates')` |
| Intermediate results | Store JSON: `set(thread, 'search_results', JSON.stringify(data))` |
| Error recovery | `set(thread, 'last_failed_step', 'payment')` |
| Session keepalive | `touch(thread)` at start of each invocation |

## Per-Field TTL Override

For fields with different freshness requirements, override TTL per write:

```typescript
// Short-lived field: search results that go stale quickly
await cache.session.set(threadId, 'flight_prices', JSON.stringify(prices), {
  ttl: 300, // 5 minutes
});

// Long-lived field: user preferences that persist across sessions
await cache.session.set(threadId, 'preferred_seat', 'aisle', {
  ttl: 86400 * 30, // 30 days
});
```

The per-call TTL overrides `tierDefaults.session.ttl` for that specific field.
