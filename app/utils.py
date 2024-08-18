import pytz
import redis
import requests
from icalendar import Calendar
from datetime import datetime
from .config import Config
# import spacy

def get_redis_connection():
    return redis.StrictRedis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB,
        password=Config.REDIS_PASSWORD
    )

def fetch_ical_events(url):
    response = requests.get(url)
    response.raise_for_status()

    cal = Calendar.from_ical(response.text)
    events = []
    for component in cal.walk('vevent'):
        description_lines = component.get('description').split('\n')
        
        professor_index = next((i for i, line in enumerate(description_lines) if "Exporté le:" in line), None) - 1

        if professor_index and professor_index > 0:
            possible_professor = description_lines[professor_index]
            if any(keyword in possible_professor for keyword in ["Gr ", "Gr TP", "ANG", "M2", "ALT", "SIR", "SIMSAB"]):
                professor = ""
            else:
                professor = possible_professor
        else:
            professor = ""

        groups = [line for line in description_lines if "Gr " in line or "Gr TP" in line or "ANG" in line or "M2" in line or "ALT" in line or "GR" in line or "SIR" in line or "SIMSAB" in line]

        local_timezone = pytz.timezone('Europe/Paris')
        start_time_utc = component.get('dtstart').dt
        end_time_utc = component.get('dtend').dt

        local_start_time = start_time_utc.astimezone(local_timezone)
        local_end_time = end_time_utc.astimezone(local_timezone)

        group_from_summary, subject = get_groups_and_subject_from_summary(component.get('summary', ''))

        groups.append(group_from_summary)

        events.append({
            "date": local_start_time.strftime('%d/%m/%Y'),
            "start_time": local_start_time.strftime('%Hh%M'),
            "end_time": local_end_time.strftime('%Hh%M'),
            "title": subject,
            "location": component.get('location', '').replace(',', '\n'),
            "professor": professor,
            "groups": groups,
            "timestamp": component.get('dtstart').dt.timestamp()
        })

    sorted_events = sorted(events, key=lambda x: x['timestamp'])
    for event in sorted_events:
        del event['timestamp']

    return sorted_events

# def get_groups_and_subject_from_summary_ai(summary):
#     nlp = spacy.load('app\modele')
#     doc = nlp(str(summary))
#     groups = [ent.text for ent in doc.ents if ent.label_ == 'GROUP']
#     subjects = [ent.text for ent in doc.ents if ent.label_ == 'SUBJECT']
#     return groups, subjects

def get_groups_and_subject_from_summary(summary):
    
    subject = summary.split("-")[0].strip() if "-" in summary else summary

    group = summary.split("-")[1].strip() if "-" in summary else ""
    return group, subject