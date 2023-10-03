from flask import Flask, jsonify, request
from flask_cors import CORS
from icalendar import Calendar
from pytz import timezone
import pytz
import redis
import requests
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

redis_conn = redis.StrictRedis(host='cache', port=6379, db=0, password='eYVX7EwVmmxKPCDmwMtyKVge8oLd2t81')

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

@app.route('/fetch_schedule', methods=['GET'])
def events():
    ical_url = request.args.get('ical_url')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')

    # Convertir les dates en objets datetime si elles sont fournies
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    else:
        start_date = None

    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    else:
        end_date = None
    if not ical_url:
        return jsonify({"error": "ical_url parameter is missing!"}), 400

    cache_prefix = "ical:" + ical_url
    last_successful_fetch_key = cache_prefix + ":last_successful_fetch"
    last_successful_events_key = cache_prefix + ":last_successful_events"

    paris_tz = pytz.timezone('Europe/Paris')
    
    if redis_conn.get(last_successful_fetch_key):
        last_successful_fetch = paris_tz.localize(datetime.strptime(redis_conn.get(last_successful_fetch_key).decode('utf-8'), DATE_FORMAT))
        delta = datetime.now(paris_tz) - last_successful_fetch
        if delta.total_seconds() < 300:  # Si la dernière requête a été faite il y a moins de 5 minutes, on renvoie le cache
            events_data = json.loads(redis_conn.get(last_successful_events_key).decode('utf-8'))
            timestamp = last_successful_fetch.strftime(DATE_FORMAT)
        else:
            events_data = fetch_ical_events(ical_url)
            redis_conn.set(last_successful_fetch_key, datetime.now(paris_tz).strftime(DATE_FORMAT))
            redis_conn.set(last_successful_events_key, json.dumps(events_data))
            timestamp = datetime.now(paris_tz).strftime(DATE_FORMAT)
    else:
        events_data = fetch_ical_events(ical_url)
        redis_conn.set(last_successful_fetch_key, datetime.now(paris_tz).strftime(DATE_FORMAT))
        redis_conn.set(last_successful_events_key, json.dumps(events_data))
        timestamp = datetime.now(paris_tz).strftime(DATE_FORMAT)

    filtered_events = [event for event in events_data if (not start_date or datetime.strptime(event['date'], '%d/%m/%Y').date() >= start_date.date()) and (not end_date or datetime.strptime(event['date'], '%d/%m/%Y').date() <= end_date.date())]
    return jsonify({
        'data': filtered_events,
        'timestamp': timestamp,
    })

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
            if any(keyword in possible_professor for keyword in ["Gr ", "Gr TP", "ANG", "M1", "G "]):
                professor = ""
            else:
                professor = possible_professor
        else:
            professor = ""

        groups = [line for line in description_lines if "Gr " in line or "Gr TP" in line or "ANG" in line or "M1" in line or "G " in line]

        local_timezone = timezone('Europe/Paris')
        start_time_utc = component.get('dtstart').dt
        end_time_utc = component.get('dtend').dt

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

    sorted_events = sorted(events, key=lambda x: x['timestamp'])
    for event in sorted_events:
        del event['timestamp']

    return sorted_events

# Retourne le prochain event a partir de la date fournie
@app.route('/next_event', methods=['GET'])
def next_event():
    ical_url = request.args.get('ical_url')
    start_date_str = request.args.get('start_date', '')

    # Convertir les dates en objets datetime si elles sont fournies
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    else:
        start_date = None

    if not ical_url:
        return jsonify({"error": "ical_url parameter is missing!"}), 400

    cache_prefix = "ical:" + ical_url
    last_successful_fetch_key = cache_prefix + ":last_successful_fetch"
    last_successful_events_key = cache_prefix + ":last_successful_events"

    paris_tz = pytz.timezone('Europe/Paris')
    
    if redis_conn.get(last_successful_fetch_key):
        last_successful_fetch = paris_tz.localize(datetime.strptime(redis_conn.get(last_successful_fetch_key).decode('utf-8'), DATE_FORMAT))
        delta = datetime.now(paris_tz) - last_successful_fetch
        if delta.total_seconds() < 300:
            events_data = json.loads(redis_conn.get(last_successful_events_key).decode('utf-8'))
            timestamp = last_successful_fetch.strftime(DATE_FORMAT)
        else:
            events_data = fetch_ical_events(ical_url)
            redis_conn.set(last_successful_fetch_key, datetime.now(paris_tz).strftime(DATE_FORMAT))
            redis_conn.set(last_successful_events_key, json.dumps(events_data))
            timestamp = datetime.now(paris_tz).strftime(DATE_FORMAT)
    else:
        events_data = fetch_ical_events(ical_url)
        redis_conn.set(last_successful_fetch_key, datetime.now(paris_tz).strftime(DATE_FORMAT))
        redis_conn.set(last_successful_events_key, json.dumps(events_data))
        timestamp = datetime.now(paris_tz).strftime(DATE_FORMAT)

    filtered_events = [event for event in events_data if (not start_date or datetime.strptime(event['date'], '%d/%m/%Y').date() >= start_date.date())]
    if len(filtered_events) > 0:
        return jsonify({
            'data': filtered_events[0],
            'timestamp': timestamp,
        })
    else:
        return jsonify({
            'data': None,
            'timestamp': timestamp,
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
