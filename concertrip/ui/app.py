"""Піксельний інтерфейс: стрічка, список, сповіщення, витяг з тексту."""

from __future__ import annotations

import sys
from pathlib import Path

# Гарантуємо, що корінь проєкту є в sys.path незалежно від того,
# звідки запускається Streamlit.
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from concertrip.availability import check_availability, simulate_restock
from concertrip.collect import bootstrap, collect_all
from concertrip.config import settings
from concertrip.db import init_db, session_scope
from concertrip.extract import extract_announcement, extract_with_model
from concertrip.feed import query_feed
from concertrip.jobs import ensure_scheduler
from concertrip.models import Alert, Artist, Event, EventArtist, WatchEvent
from concertrip.notify.messages import ticket_label
from concertrip.notify.telegram_bot import deliver_queued, send_telegram, send_test_message
from concertrip.prefs import get_pref, jsonld_urls, origin_city, quiet_hours, set_jsonld_urls, set_pref, set_unwanted_genres, unwanted_genres
from concertrip.ranking.festival import score_event
from concertrip.ranking.urgency import best_popularity, score_urgency
from concertrip.reference import ARTIST_GENRES, ORIGIN_CITIES
from concertrip.spotify_api import authorize_url, exchange_code, top_artists
from concertrip.trip import format_trip
from concertrip.ui.cards import badge_for, event_card
from concertrip.ui.theme import CSS, EMPTY, LOADING
from concertrip.watchlist import (
    clear_watch_event,
    follow_name,
    list_watch,
    set_watch_event,
    unfollow,
    watched_event_ids,
)

PAGE_SIZE = 5
TICKET_OPTIONS = ["any", "standing", "seated", "other"]
TICKET_LABELS = {
    "any": "Будь-який тип",
    "standing": "Стоячі",
    "seated": "Сидячі",
    "other": "Інше",
}


def _boot() -> None:
    init_db()
    if "booted" not in st.session_state:
        with session_scope() as session:
            bootstrap(session)
        st.session_state["booted"] = True
    ensure_scheduler()


def _watched_count() -> int:
    with session_scope() as session:
        from sqlalchemy import func, select
        return session.scalar(select(func.count()).select_from(WatchEvent)) or 0


def _origin_box() -> None:
    labels = {code: label for code, label in ORIGIN_CITIES}
    with session_scope() as session:
        current = origin_city(session)
    options = [code for code, _label in ORIGIN_CITIES]
    index = options.index(current) if current in options else 0
    chosen = st.sidebar.selectbox(
        "Звідки їдеш",
        options,
        index=index,
        format_func=lambda code: labels.get(code, code),
    )
    if chosen != current:
        with session_scope() as session:
            set_pref(session, "origin_city", chosen)


def _legend() -> None:
    st.sidebar.markdown(
        """
<div class="game-meta">
<span class="px" style="background:#00E5C7"></span> є квитки<br>
<span class="px" style="background:#FFD93D"></span> мало<br>
<span class="px" style="background:#E10600"></span> розпродано<br>
<span class="px" style="background:#6B5B8C"></span> ще не в продажу
</div>
""",
        unsafe_allow_html=True,
    )


def _title(event) -> str:
    if not event.artists_link:
        return "Подія"
    ordered = sorted(event.artists_link, key=lambda link: link.position)
    return ordered[0].raw_name


def _render_feed() -> None:
    countries = ["", "GB", "NL", "DE", "FR", "PL"]
    country_labels = {"": "Усі країни", "GB": "Британія", "NL": "Нідерланди", "DE": "Німеччина", "FR": "Франція", "PL": "Польща"}
    sources = ["", "seed", "jsonld", "ebilet", "ticketmaster"]
    source_labels = {"": "Усі джерела", "seed": "Резерв", "jsonld": "Розмітка", "ebilet": "eBilet", "ticketmaster": "Ticketmaster"}
    c1, c2, c3 = st.columns(3)
    with c1:
        country = st.selectbox("Країна", countries, format_func=lambda code: country_labels[code])
    with c2:
        ticket = st.selectbox("Тип квитка", TICKET_OPTIONS, format_func=lambda code: TICKET_LABELS[code])
    with c3:
        source = st.selectbox("Джерело", sources, format_func=lambda code: source_labels[code])
    only_mine = st.checkbox("Лише артисти з мого списку")
    with session_scope() as session:
        events = query_feed(
            session,
            country=country or None,
            ticket_type=None if ticket == "any" else ticket,
            source_id=source or None,
            watchlist_only=only_mine,
        )
        origin = origin_city(session)
        watched = watched_event_ids(session)
        cards = []
        for event in events:
            urgency = score_urgency(event, best_popularity(event))
            festival = score_event(session, event) if event.is_festival else None
            types = [(row.normalized_type, row.is_vip) for row in event.ticket_types]
            is_watched = event.id in watched
            cards.append(
                {
                    "id": event.id,
                    "html": event_card(
                        title=_title(event),
                        city=event.venue.city,
                        country=event.venue.country,
                        when=event.event_date.strftime("%d.%m.%Y"),
                        status=event.status,
                        badge=badge_for(types),
                        source=event.source_id,
                        urgency_segments=urgency.segments,
                        urgency_level=urgency.level,
                        urgency_text=urgency.text,
                        trip_text=format_trip(origin, event.venue.city) + ". Це не бронювання.",
                        festival_lines=(
                            [festival.anchor_text, festival.coverage_text, festival.penalty_text]
                            if festival
                            else None
                        ),
                        is_watched=is_watched,
                        url=event.url,
                    ),
                    "watched": watched.get(event.id),
                    "url": event.url,
                }
            )
    if not cards:
        st.markdown(EMPTY, unsafe_allow_html=True)
        st.write("Поки що тут тихо. Додай артиста або скинь фільтр.")
        return
    pages = max(1, (len(cards) + PAGE_SIZE - 1) // PAGE_SIZE)
    if st.session_state.get("feed_page", 1) > pages:
        st.session_state["feed_page"] = 1
    page = st.number_input("Сторінка", min_value=1, max_value=pages, key="feed_page")
    st.caption(f"{len(cards)} подій · {sum(1 for c in cards if c['watched'])} позначено")
    start = (int(page) - 1) * PAGE_SIZE
    for card in cards[start : start + PAGE_SIZE]:
        st.markdown(card["html"], unsafe_allow_html=True)
        left, mid, right = st.columns([2, 2, 2])
        with left:
            choice = st.selectbox(
                "Стежити за типом",
                TICKET_OPTIONS,
                index=TICKET_OPTIONS.index(card["watched"]) if card["watched"] in TICKET_OPTIONS else 0,
                format_func=lambda code: TICKET_LABELS[code],
                key=f"type-{card['id']}",
            )
        with mid:
            if card["watched"]:
                if st.button("Зняти позначку", key=f"clear-{card['id']}"):
                    with session_scope() as session:
                        clear_watch_event(session, card["id"])
                    st.rerun()
            elif st.button("⭐ Піду на це", key=f"watch-{card['id']}"):
                with session_scope() as session:
                    set_watch_event(session, card["id"], choice)
                st.toast("Подію позначено! Отримаєш сповіщення, коли з'являться квитки.", icon="✅")
                st.rerun()
        with right:
            pass  # кнопка купити вбудована в картку


def _render_my_concerts() -> None:
    """Список усіх позначених подій з управлінням і симуляцією."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    with session_scope() as session:
        watches = session.scalars(select(WatchEvent)).all()
        origin = origin_city(session)
        rows = []
        for watch in watches:
            event = session.scalar(
                select(Event)
                .where(Event.id == watch.event_id)
                .options(
                    selectinload(Event.artists_link).selectinload(EventArtist.artist),
                    selectinload(Event.venue),
                    selectinload(Event.ticket_types),
                )
            )
            if event is None:
                continue
            urgency = score_urgency(event, best_popularity(event))
            types = [(row.normalized_type, row.is_vip) for row in event.ticket_types]
            rows.append({
                "watch_id": watch.id,
                "event_id": event.id,
                "title": _title(event),
                "city": event.venue.city,
                "country": event.venue.country,
                "when": event.event_date.strftime("%d.%m.%Y"),
                "status": event.status,
                "ticket_filter": watch.ticket_type_filter,
                "url": event.url,
                "html": event_card(
                    title=_title(event),
                    city=event.venue.city,
                    country=event.venue.country,
                    when=event.event_date.strftime("%d.%m.%Y"),
                    status=event.status,
                    badge=badge_for(types),
                    source=event.source_id,
                    urgency_segments=urgency.segments,
                    urgency_level=urgency.level,
                    urgency_text=urgency.text,
                    trip_text=format_trip(origin, event.venue.city) + ". Це не бронювання.",
                    is_watched=True,
                    url=event.url,
                ),
            })

    if not rows:
        st.markdown(EMPTY, unsafe_allow_html=True)
        st.write("Жодної позначеної події. Відкрий Стрічку і натисни «⭐ Піду на це».")
        return

    # — Дії зверху —
    col_check, col_space = st.columns([2, 3])
    with col_check:
        if st.button("🔍 Перевірити зараз", help="Запустити перевірку статусу всіх позначених подій і доставити черу сповіщень"):
            holder = st.empty()
            holder.markdown(LOADING, unsafe_allow_html=True)
            with session_scope() as session:
                new_alerts = check_availability(session)
                sent = deliver_queued(session, send_telegram)
            holder.empty()
            if new_alerts:
                st.success(f"Знайдено {len(new_alerts)} нових сповіщень. Надіслано: {sent}.")
            else:
                st.info("Усе без змін. Нових сповіщень немає.")

    st.caption(f"{len(rows)} позначених подій")
    st.divider()

    # — Картки —
    for row in rows:
        st.markdown(row["html"], unsafe_allow_html=True)
        left, mid, right = st.columns([3, 2, 2])
        with left:
            st.markdown(
                f'<span class="game-meta">Тип: **{TICKET_LABELS.get(row["ticket_filter"], row["ticket_filter"])}**</span>',
                unsafe_allow_html=True,
            )
        with mid:
            if st.button("Зняти позначку", key=f"my-clear-{row['event_id']}"):
                with session_scope() as session:
                    clear_watch_event(session, row["event_id"])
                st.rerun()
        with right:
            if st.button("🎟 Зімітувати квитки", key=f"my-sim-{row['event_id']}", help="Симулювати появу квитків для тесту"):
                with session_scope() as session:
                    alert = simulate_restock(session, row["event_id"])
                if alert is None:
                    st.warning("Сповіщення не створено — статус вже був доступний або тип квитка не збігся.")
                else:
                    st.success(f"Сповіщення #{alert.id} у черзі! Натисни «Перевірити зараз» або іди на сторінку Telegram.")
                st.rerun()
        st.divider()


def _render_artists() -> None:
    name = st.text_input("Ім'я артиста")
    if st.button("Додати в список") and name.strip():
        with session_scope() as session:
            follow_name(session, name.strip())
        st.rerun()
    with session_scope() as session:
        items = list_watch(session)
        rows = [(item.artist_id, item.artist.name) for item in items if item.artist]
    if not rows:
        st.markdown(EMPTY, unsafe_allow_html=True)
        st.write("Список порожній. Додай бодай одне ім'я — і стрічка підніме його шоу нагору.")
    for artist_id, artist_name in rows:
        col, button = st.columns([4, 1])
        col.write(artist_name)
        if button.button("Прибрати", key=f"drop-{artist_id}"):
            with session_scope() as session:
                unfollow(session, artist_id)
            st.rerun()
    st.subheader("Spotify")
    if not settings.has_spotify:
        st.write("Без SPOTIFY_CLIENT_ID і SPOTIFY_CLIENT_SECRET імпорт не ввімкнеться. Імена можна додати вручну.")
        return
    state = st.session_state.setdefault("spotify_state", "concertrip")
    st.markdown(f"[Увійти в Spotify]({authorize_url(state)})")
    code = st.query_params.get("code")
    if code and "spotify_artists" not in st.session_state:
        try:
            token = exchange_code(code)
            st.session_state["spotify_artists"] = top_artists(token["access_token"])
            st.query_params.clear()
        except Exception as exc:
            st.write(f"Spotify не відповів: {exc}")
    artists = st.session_state.get("spotify_artists") or []
    chosen = []
    for artist in artists:
        if st.checkbox(artist["name"], key=f"sp-{artist['spotify_id']}"):
            chosen.append(artist)
    if artists and st.button("Стежити за обраними"):
        with session_scope() as session:
            for artist in chosen:
                follow_name(
                    session,
                    artist["name"],
                    spotify_id=artist["spotify_id"],
                    popularity=artist["popularity"],
                    genres=artist["genres"],
                )
        st.rerun()


def _render_alerts() -> None:
    """Налаштування Telegram і черга сповіщень."""
    with session_scope() as session:
        chat = get_pref(session, "telegram_chat_id", "")
        start, end = quiet_hours(session)
        blocked = sorted(unwanted_genres(session))

    # ── Покрокова інструкція ────────────────────────────────────────────────
    st.markdown(
        """
<div class="step-box">
  <div class="step-num">КРОК 1</div>
  <div class="step-desc">Відкрий <strong>@BotFather</strong> у Telegram → /newbot → скопіюй токен у <code>.env</code> як <code>TELEGRAM_BOT_TOKEN</code>.</div>
</div>
<div class="step-box">
  <div class="step-num">КРОК 2</div>
  <div class="step-desc">Знайди свого бота у Telegram і напиши йому <strong>/start</strong> — він сам збереже твій Chat ID. Або встав ID нижче вручну.</div>
</div>
<div class="step-box">
  <div class="step-num">КРОК 3</div>
  <div class="step-desc">Познач концерти у вкладці <strong>Стрічка</strong> кнопкою «⭐ Піду на це».</div>
</div>
<div class="step-box">
  <div class="step-num">КРОК 4</div>
  <div class="step-desc">Перевіряй вкладку <strong>Мої концерти</strong> або дочекайся автоматичного циклу (до 1 год). Як тільки квитки з'являться — прийде повідомлення.</div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Chat ID і тест ──────────────────────────────────────────────────────
    st.subheader("Chat ID")
    chat_id = st.text_input("Telegram Chat ID", value=chat, placeholder="Напр. 123456789")
    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("Зберегти Chat ID"):
            with session_scope() as session:
                set_pref(session, "telegram_chat_id", chat_id.strip())
            st.success("Збережено.")
    with c2:
        if st.button("📨 Надіслати тестове повідомлення"):
            if not chat_id.strip():
                st.warning("Спочатку вкажи Chat ID.")
            elif not settings.has_telegram:
                st.error("TELEGRAM_BOT_TOKEN відсутній у .env. Без токена надіслати неможливо.")
            else:
                holder = st.empty()
                holder.markdown(LOADING, unsafe_allow_html=True)
                ok = send_test_message(chat_id.strip())
                holder.empty()
                if ok:
                    st.success("Тестове повідомлення надіслано! Перевір Telegram.")
                else:
                    st.error("Не вийшло. Перевір токен і Chat ID.")

    if not settings.has_telegram:
        st.warning("TELEGRAM_BOT_TOKEN порожній — сповіщення будуть лишатись у черзі нижче, але не надходитимуть у Telegram.")

    st.divider()

    # ── Тихі години і жанри ────────────────────────────────────────────────
    st.subheader("Тихі години")
    q1, q2 = st.columns(2)
    with q1:
        quiet_start = st.number_input("Тиша від (година)", min_value=0, max_value=23, value=start)
    with q2:
        quiet_end = st.number_input("Тиша до (година)", min_value=0, max_value=23, value=end)
    genres = sorted(set(ARTIST_GENRES.values()))
    blocked_now = st.multiselect("Жанри, яких не хочеш на фестивалі", genres, default=[g for g in blocked if g in genres])
    if st.button("Зберегти налаштування"):
        with session_scope() as session:
            set_pref(session, "quiet_start", str(int(quiet_start)))
            set_pref(session, "quiet_end", str(int(quiet_end)))
            set_unwanted_genres(session, blocked_now)
            from concertrip.ranking.festival import recompute_festivals
            recompute_festivals(session)
        st.success("Збережено.")

    st.divider()

    # ── Черга сповіщень ─────────────────────────────────────────────────────
    st.subheader("Черга сповіщень")
    with session_scope() as session:
        from sqlalchemy import select
        queued = session.scalars(select(Alert).where(Alert.status == "queued").order_by(Alert.id.desc())).all()
        bodies = [(a.id, a.kind, a.body, a.attempts, a.last_error) for a in queued]

    if not bodies:
        st.info("Черга порожня. Познач концерт і зімітуй появу квитків у «Мої концерти».")
    else:
        if st.button("▶ Надіслати чергу"):
            holder = st.empty()
            holder.markdown(LOADING, unsafe_allow_html=True)
            with session_scope() as session:
                sent = deliver_queued(session, send_telegram)
            holder.empty()
            st.write(f"Надіслано: {sent}. Якщо нуль — черга порожня, тиша, вимкнено звук, або немає chat id і токена.")
        for alert_id, kind, body, attempts, error in bodies:
            st.markdown(f"**#{alert_id} · {kind} · спроб {attempts}**")
            st.code(body)
            if error:
                st.write(error)


def _render_extract() -> None:
    text = st.text_area("Текст анонсу", height=180)
    if st.button("Витягнути поля") and text.strip():
        try:
            if settings.has_anthropic:
                result = extract_with_model(text)
                st.caption("Джерело: модель")
            else:
                result = extract_announcement(text)
                st.caption("Джерело: локальні правила, бо ключа моделі немає")
        except Exception as exc:
            st.write(f"Не вийшло: {exc}")
            return
        rows = {
            "Артист": ", ".join(result.artist_names) or "—",
            "Майданчик": result.venue or "—",
            "Місто": result.city or "—",
            "Країна": result.country or "—",
            "Дата": result.event_date.isoformat() if result.event_date else "—",
            "Старт продажів": result.on_sale_date.isoformat() if result.on_sale_date else "—",
            "Статус": result.status or "—",
            "Посилання": result.url or "—",
        }
        for key, value in rows.items():
            mark = ""
            st.write(f"{key}: {value}{mark}")
        if result.low_confidence:
            st.write("Непевні поля (дату з них не записуємо): " + ", ".join(result.low_confidence))


def _render_sources() -> None:
    """Управління URL-джерелами з JSON-LD розміткою."""
    from datetime import date

    from concertrip.ingest import ingest_events
    from concertrip.sources.jsonld import JsonLdSource

    # ── Довідка: які сайти підтримують JSON-LD ──────────────────────────────
    st.markdown(
        """
<div class="step-box">
  <div class="step-num">ЩО ТАКЕ JSON-LD ДЖЕРЕЛА?</div>
  <div class="step-desc">
    Багато сайтів квитків вбудовують у сторінки схему <code>schema.org/MusicEvent</code>.
    ConcerTrip зчитує її автоматично — ніяких правил під кожен сайт.<br><br>
    <strong>Сайти, що добре підтримують JSON-LD:</strong><br>
    🎵 <strong>Songkick</strong> — сторінка артиста: <code>songkick.com/artists/SLUG/calendar</code><br>
    🎵 <strong>Bandsintown</strong> — <code>bandsintown.com/a/ARTIST-NAME/events</code><br>
    🎵 <strong>Resident Advisor</strong> — сторінка клубу або події<br>
    🎵 <strong>Eventim</strong> — сторінки окремих концертів<br>
    🎵 <strong>Сайти фестивалів</strong> — Glastonbury, Primavera, Rock Werchter тощо<br>
    🎵 <strong>Сайти залів</strong> — Roundhouse, Paradiso, Columbiahalle<br><br>
    Вставляй URL сторінки з розкладом або окремої події. По одному рядку.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    # ── Поточні збережені URL ───────────────────────────────────────────────
    with session_scope() as session:
        saved = jsonld_urls(session)

    st.subheader("Мої URL-джерела")
    raw_input = st.text_area(
        "URL-и сторінок (по одному на рядок)",
        value="\n".join(saved),
        height=180,
        placeholder=(
            "https://www.songkick.com/artists/123-radiohead/calendar\n"
            "https://www.bandsintown.com/a/radiohead/events"
        ),
        help="Вставляй будь-яку сторінку з розміткою schema.org/MusicEvent.",
    )

    col_save, col_fetch = st.columns([1, 2])
    with col_save:
        if st.button("💾 Зберегти"):
            urls = [u.strip() for u in raw_input.splitlines() if u.strip().startswith("http")]
            with session_scope() as session:
                set_jsonld_urls(session, urls)
            st.toast(f"Збережено {len(urls)} URL.", icon="✅")
            st.rerun()

    with col_fetch:
        if st.button("⬇️ Завантажити події зараз", help="Негайно завантажити події з усіх збережених URL"):
            urls = [u.strip() for u in raw_input.splitlines() if u.strip().startswith("http")]
            if not urls:
                st.warning("Спочатку додай хоча б один URL.")
            else:
                with session_scope() as session:
                    set_jsonld_urls(session, urls)

                holder = st.empty()
                holder.markdown(LOADING, unsafe_allow_html=True)

                raws = []
                try:
                    source = JsonLdSource(paths=[], urls=urls, delay=0.5)
                    raws = source.fetch(date.today())
                except Exception as exc:
                    holder.empty()
                    st.error(f"Помилка під час завантаження: {exc}")

                total_new = 0
                if raws:
                    with session_scope() as session:
                        stats = ingest_events(session, raws)
                    total_new = stats.upserted

                holder.empty()

                if not raws:
                    st.warning(
                        "Подій не знайдено. Перевір URL — сторінка має містити розмітку "
                        "schema.org/MusicEvent. Відкрий у браузері → Ctrl+U → пошукай `ld+json`."
                    )
                else:
                    st.success(f"Знайдено {len(raws)} подій, збережено {total_new} нових.")
                    _status_icon = {"available": "🟢", "limited": "🟡", "low": "🟡",
                                    "sold_out": "🔴", "unknown": "⚫"}
                    for ev in raws[:20]:
                        artist = ev.artist_names[0] if ev.artist_names else "?"
                        short_url = ev.url[:60] + "…" if len(ev.url) > 60 else ev.url
                        icon = _status_icon.get(ev.status, "⚫")
                        st.markdown(
                            f"{icon} **{artist}** — {ev.city}, {ev.country} · "
                            f"{ev.event_date} · [{short_url}]({ev.url})"
                        )
                    if len(raws) > 20:
                        st.caption(f"… і ще {len(raws) - 20} подій. Відкрий Стрічку, щоб побачити всі.")

    # ── Збережені URL зі кнопкою видалення ─────────────────────────────────
    if saved:
        st.divider()
        st.subheader("Збережені джерела")
        for url in saved:
            col_url, col_del = st.columns([5, 1])
            with col_url:
                st.markdown(f"[{url}]({url})")
            with col_del:
                if st.button("✕", key=f"del-{url}", help="Видалити це джерело"):
                    with session_scope() as session:
                        set_jsonld_urls(session, [u for u in saved if u != url])
                    st.rerun()


def main() -> None:

    st.set_page_config(page_title="ConcerTrip", page_icon="🎟️", layout="wide")
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    _boot()
    st.title("CONCERTRIP")
    st.write("Спершу квиток. Поїздка — лише оцінка поруч.")

    # Лічильник позначених концертів у сайдбарі
    watched_count = _watched_count()
    watched_label = f"Мої концерти [{watched_count}]" if watched_count else "Мої концерти"

    page = st.sidebar.radio(
        "Куди",
        ["Стрічка", "Артисти", watched_label, "Джерела", "Telegram", "Витяг"],
    )
    _origin_box()
    _legend()

    if page == "Стрічка":
        _render_feed()
    elif page == "Артисти":
        _render_artists()
    elif page.startswith("Мої концерти"):
        _render_my_concerts()
    elif page == "Джерела":
        _render_sources()
    elif page == "Telegram":
        _render_alerts()
    else:
        _render_extract()


main()
