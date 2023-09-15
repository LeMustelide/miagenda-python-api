from flask import Flask, jsonify
from icalendar import Calendar, Event
import requests
from pytz import UTC, timezone

app = Flask(__name__)

ICAL_URL = "https://aderead2022.univ-orleans.fr/jsp/custom/modules/plannings/anonymous_cal.jsp?data=83909bcb789af69dbb59d201976f55300d3b4c68a7820e99c53ca46537bc18bd982bf381b1007d5c58e581d9e50ed9f0bc00c78efe4716ebce40ad91eb0ec69148c2240b7941c7dd7e7dea10fc53247e,1"  # Remplacez par l'URL de votre fichier iCal

@app.route('/events', methods=['GET'])
def events():
    events_data = fetch_ical_events(ICAL_URL)
    return jsonify(events_data)

def fetch_ical_events(url):
    response = requests.get(url)
    response.raise_for_status()

    cal = Calendar.from_ical(response.text)
    events = []
    for component in cal.walk('vevent'):
        description_lines = component.get('description').split('\n')
        
        # La ligne qui contient le professeur semble être celle avant "Exporté le"
        # mais il n'y a pas toujours un nom de professeur.
        professor_index = next((i for i, line in enumerate(description_lines) if "Exporté le:" in line), None) - 1

        if professor_index and professor_index > 0:
            possible_professor = description_lines[professor_index]
            # Vérifier si le "possible_professor" est en réalité un groupe ou non
            if any(keyword in possible_professor for keyword in ["Gr ", "Gr TP", "ANG", "M1"]):
                professor = ""
            else:
                professor = possible_professor
        else:
            professor = ""

        groups = [line for line in description_lines if "Gr " in line or "Gr TP" in line or "ANG" in line or "M1" in line]

        local_timezone = timezone('Europe/Paris')  # Remplacez par votre fuseau horaire
        start_time_utc = component.get('dtstart').dt
        end_time_utc = component.get('dtend').dt

        # Convertissez en heure locale
        local_start_time = start_time_utc.astimezone(local_timezone)
        local_end_time = end_time_utc.astimezone(local_timezone)

        events.append({
            "date": local_start_time.strftime('%d/%m/%Y'),
            "start_time": local_start_time.strftime('%Hh%M'),
            "end_time": local_end_time.strftime('%Hh%M'),
            "title": component.get('summary', ''),
            "location": component.get('location', '').replace(',', '\n'),
            "professor": professor,
            "groups": groups,
            "timestamp": component.get('dtstart').dt.timestamp()
        })

    # Triez les événements par 'timestamp'
    sorted_events = sorted(events, key=lambda x: x['timestamp'])
    # Supprimez le champ 'timestamp' des événements triés
    for event in sorted_events:
        del event['timestamp']

    return sorted_events

if __name__ == '__main__':
    app.run(debug=True)
