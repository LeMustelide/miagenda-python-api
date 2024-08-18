from flask import Blueprint, jsonify, request
from .utils import fetch_ical_events, get_redis_connection
from datetime import datetime
from .config import Config
import pytz
import json

main = Blueprint('main', __name__)

@main.route('/fetch_schedule', methods=['GET'])
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

    redis_conn = get_redis_connection()
    
    if redis_conn.get(last_successful_fetch_key):
        last_successful_fetch = paris_tz.localize(datetime.strptime(redis_conn.get(last_successful_fetch_key).decode('utf-8'), Config.DATE_FORMAT))
        delta = datetime.now(paris_tz) - last_successful_fetch
        if delta.total_seconds() < 0:  # Si la dernière requête a été faite il y a moins de 5 minutes, on renvoie le cache
            print("loading from cache")
            events_data = json.loads(redis_conn.get(last_successful_events_key).decode('utf-8'))
            timestamp = last_successful_fetch.strftime(Config.DATE_FORMAT)
        else:
            try:
                print("fetching from ical")
                events_data = fetch_ical_events(ical_url)
                redis_conn.set(last_successful_fetch_key, datetime.now(paris_tz).strftime(Config.DATE_FORMAT))
                redis_conn.set(last_successful_events_key, json.dumps(events_data))
                timestamp = datetime.now(paris_tz).strftime(Config.DATE_FORMAT)
            except Exception as e:
                if redis_conn.get(last_successful_events_key):
                    print("exception"+str(e))
                    print("loading from cache because of exception in first fetch")
                    events_data = json.loads(redis_conn.get(last_successful_events_key).decode('utf-8'))
                    timestamp = last_successful_fetch.strftime(Config.DATE_FORMAT)
                else:
                    return jsonify({"error": str(e)}), 500
    else:
        try:
            print("fetching from ical")
            events_data = fetch_ical_events(ical_url)
        except Exception as e:
            if redis_conn.get(last_successful_events_key):
                print("loading from cache because of exception in second fetch")
                events_data = json.loads(redis_conn.get(last_successful_events_key).decode('utf-8'))
                timestamp = last_successful_fetch.strftime(Config.DATE_FORMAT)
            else:
                return jsonify({"error": str(e)}), 500
        redis_conn.set(last_successful_fetch_key, datetime.now(paris_tz).strftime(Config.DATE_FORMAT))
        redis_conn.set(last_successful_events_key, json.dumps(events_data))
        timestamp = datetime.now(paris_tz).strftime(Config.DATE_FORMAT)
    filtered_events = [event for event in events_data if (not start_date or datetime.strptime(event['date'], '%d/%m/%Y').date() >= start_date.date()) and (not end_date or datetime.strptime(event['date'], '%d/%m/%Y').date() <= end_date.date())]
    print(jsonify(filtered_events[0]).data)
    return jsonify({
        'data': filtered_events,
        'timestamp': timestamp,
    })

@main.route('/next_event', methods=['GET'])
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
    redis_conn = get_redis_connection()
    
    if redis_conn.get(last_successful_fetch_key):
        last_successful_fetch = paris_tz.localize(datetime.strptime(redis_conn.get(last_successful_fetch_key).decode('utf-8'), Config.DATE_FORMAT))
        delta = datetime.now(paris_tz) - last_successful_fetch
        if delta.total_seconds() < 300:
            events_data = json.loads(redis_conn.get(last_successful_events_key).decode('utf-8'))
            timestamp = last_successful_fetch.strftime(Config.DATE_FORMAT)
        else:
            events_data = fetch_ical_events(ical_url)
            redis_conn.set(last_successful_fetch_key, datetime.now(paris_tz).strftime(Config.DATE_FORMAT))
            redis_conn.set(last_successful_events_key, json.dumps(events_data))
            timestamp = datetime.now(paris_tz).strftime(Config.DATE_FORMAT)
    else:
        events_data = fetch_ical_events(ical_url)
        redis_conn.set(last_successful_fetch_key, datetime.now(paris_tz).strftime(Config.DATE_FORMAT))
        redis_conn.set(last_successful_events_key, json.dumps(events_data))
        timestamp = datetime.now(paris_tz).strftime(Config.DATE_FORMAT)

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
