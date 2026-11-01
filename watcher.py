
import os
import json
import re
import urllib.request
import urllib.error
from html import unescape

URL = (
    "https://krasserstoff.com/events/"
    "zurueck-zuhause-2026-xoxo-zwei-naechte-in-voller-laenge-"
    "lokschuppen-sonntag?tab=resale"
)
STATE_FILE = "ticket_state.json"


def get_page():
    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; CasperTicketWatcher/1.0)"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def resale_status(html):
    # HTML-Tags entfernen und Text normalisieren.
    html = re.sub(
        r"<(script|style)\b[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.I | re.S,
    )
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", unescape(text)).lower()

    # Nur eindeutige Hinweise auf Verfügbarkeit werten.
    no_tickets = (
        "aktuell sind keine re:sale tickets verfügbar",
        "zzt. nicht verfügbar",
    )
    sold_out = ("ausverkauft",)

    if any(phrase in text for phrase in no_tickets):
        return "unavailable"

    # Kein Treffer bedeutet NICHT automatisch verfügbar.
    # Der Shoptext kann sich ändern; unbekannte Zustände
    # werden deshalb als unklar behandelt.
    if "re:sale" in text and any(
        phrase in text for phrase in sold_out
    ):
        return "unavailable"

    return "unknown"


def notify(message):
    topic = os.environ["NTFY_TOPIC"]
    server = os.getenv("NTFY_SERVER", "https://ntfy.sh").rstrip("/")

    req = urllib.request.Request(
        f"{server}/{topic}",
        data=message.encode("utf-8"),
        headers={
            "Title": "Casper re:sale – Ticketcheck",
            "Priority": "urgent",
            "Click": URL,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status >= 300:
            raise RuntimeError("Push-Mitteilung fehlgeschlagen")


def main():
    # Den vorherigen Status aus dem GitHub-Cache laden.
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        state = {"status": "unknown", "alerted": False}

    html = get_page()
    status = resale_status(html)
    previous = state.get("status", "unknown")

    print(f"Vorher: {previous}; jetzt: {status}")

    if status == "unknown":
        print("Status nicht eindeutig; keine Verfügbarkeit behauptet.")
        return

    if status == "available" and previous != "available":
        notify(
            "Mögliche Casper-re:sale-Tickets sind verfügbar! "
            "Jetzt prüfen und schnell sein: " + URL
        )
        state["alerted"] = True

    state["status"] = status

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
