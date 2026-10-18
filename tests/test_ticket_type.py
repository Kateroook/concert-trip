"""CT-31. Тестовий набір: 20 назв із п'яти країн + вимірювання точності."""

from concertrip.normalize.ticket_type import TicketType, classify

# (назва сектора, країна, очікуваний тип, очікуваний VIP)
TEST_SET = [
    # Польща
    ("Płyta stojąca", "PL", TicketType.STANDING, False),
    ("Sektor stojący przed sceną", "PL", TicketType.STANDING, False),
    ("Miejsca siedzące - trybuna A", "PL", TicketType.SEATED, False),
    ("Złoty Krąg VIP", "PL", TicketType.OTHER, True),
    # Німеччина
    ("Stehplatz Innenraum", "DE", TicketType.STANDING, False),
    ("Sitzplatz Rang 2", "DE", TicketType.SEATED, False),
    ("Block C Sitzplätze", "DE", TicketType.SEATED, False),
    ("VIP Lounge", "DE", TicketType.OTHER, True),
    # Франція
    ("Fosse Or", "FR", TicketType.STANDING, False),
    ("Place assise numérotée", "FR", TicketType.SEATED, False),
    ("Parterre debout", "FR", TicketType.STANDING, False),
    ("Loge VIP", "FR", TicketType.OTHER, True),
    # Велика Британія
    ("Standing - General Admission", "UK", TicketType.STANDING, False),
    ("Golden Circle Standing", "UK", TicketType.STANDING, True),
    ("Seated Tier 1", "UK", TicketType.SEATED, False),
    ("Stalls Reserved Seat", "UK", TicketType.SEATED, False),
    # Україна
    ("Танцпол", "UA", TicketType.STANDING, False),
    ("Фан-зона", "UA", TicketType.STANDING, False),
    ("Сидячі місця, сектор B", "UA", TicketType.SEATED, False),
    ("VIP ложа", "UA", TicketType.OTHER, True),
]


def run() -> float:
    ok_type = ok_vip = 0
    print(f"{'Назва':<34} {'Країна':<7} {'Очікувано':<16} {'Отримано':<16} {'':<3} Правило")
    print("-" * 118)

    for raw, country, want_type, want_vip in TEST_SET:
        got = classify(raw)
        type_ok = got.ticket_type is want_type
        vip_ok = got.is_vip == want_vip
        ok_type += type_ok
        ok_vip += vip_ok
        want = want_type.value + (" + VIP" if want_vip else "")
        mark = "ok" if type_ok and vip_ok else "ПОМИЛКА"
        print(f"{raw:<34} {country:<7} {want:<16} {str(got):<16} {mark:<3} {got.matched_rule}")

    total = len(TEST_SET)
    acc = ok_type / total
    print("-" * 118)
    print(f"Тип квитка:  {ok_type}/{total} = {acc:.0%}  (критерій приймання: не нижче 80%)")
    print(f"Ознака VIP:  {ok_vip}/{total} = {ok_vip / total:.0%}")
    return acc


if __name__ == "__main__":
    accuracy = run()
    raise SystemExit(0 if accuracy >= 0.8 else 1)


def test_accuracy_meets_acceptance_criterion():
    assert run() >= 0.8
