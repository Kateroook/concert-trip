"""Веб-інтерфейс. Поки що показує стан налаштувань і роботу класифікатора CT-31."""

from __future__ import annotations

import streamlit as st

from concertrip.config import settings
from concertrip.normalize.ticket_type import classify

st.set_page_config(page_title="ConcerTrip", page_icon="🎟️")
st.title("ConcerTrip")
st.caption("Відстеження концертів і старту продажів квитків")

st.subheader("Стан налаштувань")
st.write(
    {
        "База даних": settings.database_url,
        "Ticketmaster": "ключ задано" if settings.has_ticketmaster else "ключ не задано",
        "Країни": ", ".join(settings.countries),
    }
)

st.subheader("Класифікація типу квитка (CT-31)")
raw = st.text_input("Назва сектора", "Płyta stojąca")
if raw:
    result = classify(raw)
    st.write(f"Тип: **{result.ticket_type.value}**")
    st.write(f"VIP: **{'так' if result.is_vip else 'ні'}**")
    st.caption(f"Спрацювало правило: {result.matched_rule}")
