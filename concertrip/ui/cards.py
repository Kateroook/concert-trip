"""Картка події як картка в грі. Дати лишаються в читабельному шрифті."""

from __future__ import annotations

import html

_STATUS = {
    "available": ("#00E5C7", "Квитки є"),
    "limited": ("#FFD93D", "Лишилось небагато"),
    "low": ("#FFD93D", "Майже розпродано"),
    "sold_out": ("#E10600", "Розпродано"),
    "unknown": ("#6B5B8C", "Ще не в продажу"),
}
_TYPE = {
    "standing": "СТОЯЧІ",
    "seated": "СИДЯЧІ",
    "other": "ІНШЕ",
    "unknown": "ТИП НЕЯСНИЙ",
}
_SOURCE = {
    "seed": "резерв",
    "jsonld": "розмітка",
    "ebilet": "eBilet",
    "ticketmaster": "Ticketmaster",
}


def event_card(
    *,
    title: str,
    city: str,
    country: str,
    when: str,
    status: str,
    badge: str,
    source: str,
    urgency_segments: int,
    urgency_level: str,
    urgency_text: str,
    trip_text: str,
    festival_lines: list[str] | None = None,
    is_watched: bool = False,
    url: str = "",
) -> str:
    color, label = _STATUS.get(status, _STATUS["unknown"])
    watched_class = " watched" if is_watched else ""
    watched_label = ' <span class="watch-badge">👁 Стежиш</span>' if is_watched else ""
    buy_btn = (
        f'<a class="ticket-link" href="{html.escape(url)}" target="_blank" rel="noopener">КУПИТИ →</a>'
        if url else ""
    )
    cells = []
    for index in range(3):
        klass = f"on-{urgency_level}" if index < urgency_segments else ""
        cells.append(f'<i class="{klass}"></i>')
    festival = ""
    if festival_lines:
        items = "".join(f"<div>{html.escape(line)}</div>" for line in festival_lines)
        festival = f'<div class="game-meta">{items}</div>'
    return f"""
<article class="game-card{watched_class}">
  <div class="game-top">
    <div>
      <div class="game-artist">{html.escape(title)}</div>
      <div class="game-meta">{html.escape(city)} · {html.escape(country)} · {html.escape(when)}</div>
      <div class="game-meta">{html.escape(_SOURCE.get(source, source))}</div>
    </div>
    <div class="game-badge">{html.escape(badge)}</div>
  </div>
  <div class="meter" title="{html.escape(urgency_text)}">{''.join(cells)}</div>
  <div class="game-meta">{html.escape(urgency_text)}</div>
  <div class="game-meta">{html.escape(trip_text)}</div>
  {festival}
  <div class="game-status" style="background:{color}">
    <span style="display:flex;align-items:center;gap:8px">
      <span class="px" style="background:{color}"></span>
      <span class="game-status-label">{html.escape(label)}</span>{watched_label}
    </span>
    {buy_btn}
  </div>
</article>
"""


def badge_for(types: list[tuple[str, bool]]) -> str:
    if not types:
        return "БЕЗ СЕКТОРА"
    order = ["standing", "seated", "other", "unknown"]
    chosen = sorted(types, key=lambda item: order.index(item[0]) if item[0] in order else 9)[0]
    label = _TYPE.get(chosen[0], chosen[0])
    if chosen[1]:
        label += " VIP"
    return label
