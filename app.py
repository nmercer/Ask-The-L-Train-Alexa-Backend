# coding: utf-8
"""
    mta-api-sanity
    ~~~~~~

    Expose the MTA's real-time subway feed as a json api

    :copyright: (c) 2014 by Jon Thornton.
    :license: BSD, see LICENSE for more details.
"""
import mta_realtime
from flask import Flask, request, jsonify, render_template, abort
from flask.json import JSONEncoder
from datetime import datetime
from functools import wraps
import logging
import pytz
import sqlite3

app = Flask(__name__)
app.config.update(
    MAX_TRAINS=10,
    MAX_MINUTES=30,
    CACHE_SECONDS=60,
    THREADED=True
)
app.config.from_envvar('MTA_SETTINGS')


# set debug logging
if app.debug:
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

class CustomJSONEncoder(JSONEncoder):

    def default(self, obj):
        try:
            if isinstance(obj, datetime):
                return obj.isoformat()
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return JSONEncoder.default(self, obj)
app.json_encoder = CustomJSONEncoder

mta = mta_realtime.MtaSanitizer(
    app.config['MTA_KEY'],
    app.config['STATIONS_FILE'],
    max_trains=app.config['MAX_TRAINS'],
    max_minutes=app.config['MAX_MINUTES'],
    expires_seconds=app.config['CACHE_SECONDS'],
    threaded=app.config['THREADED'])

def cross_origin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        resp = f(*args, **kwargs)

        if app.config['DEBUG']:
            resp.headers['Access-Control-Allow-Origin'] = '*'
        elif 'CROSS_ORIGIN' in app.config:
            resp.headers['Access-Control-Allow-Origin'] = app.config['CROSS_ORIGIN']

        return resp

    return decorated_function

def get_user_data(user_id):
    conn = sqlite3.connect('mta.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = '%s'" % user_id)
    user = c.fetchone()
    conn.close()
    return user

def create_new_user(user_id):
    conn = sqlite3.connect('mta.db')
    c = conn.cursor()
    c.execute("INSERT INTO users (date_created, date_updated, id) VALUES ('%s','%s', '%s')" % (datetime.now(pytz.utc), datetime.now(pytz.utc), user_id))
    conn.commit()
    conn.close()

def delete_user(user_id):
    conn = sqlite3.connect('mta.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id='%s'" % (user_id))
    conn.commit()
    conn.close()

def update_station(user_id, station):
    conn = sqlite3.connect('mta.db')
    c = conn.cursor()
    c.execute("UPDATE users set station = '%s' where id='%s'" % (station, user_id))
    conn.commit()
    conn.close()

def update_direction(user_id, direction):
    conn = sqlite3.connect('mta.db')
    c = conn.cursor()
    c.execute("UPDATE users set direction = '%s' where id='%s'" % (direction, user_id))
    conn.commit()
    conn.close()

def get_time_data(time):
   time_dif = time.replace(tzinfo=pytz.utc) - datetime.now(pytz.utc) 
   seconds = time_dif.total_seconds()
   hours = seconds // 3600
   minutes = int((seconds % 3600) // 60)
   seconds = int(seconds % 60)

   if minutes == 0 and seconds == 0:
       return "Right Now"
   if seconds == 1:
       seconds_str = "1 Second"
   elif seconds == 0:
       seconds_str = ""
   else:
        seconds_str = str(seconds) + " Seconds"

   if minutes in [59, 58, 57, 56, 55, 54, 53, 52, 51, 50]:
        return False
   elif minutes == 1:
       min_str = "1 Minute"
   elif minutes == 0:
       min_str = ""
   else:
       min_str = str(minutes) + " Minutes"

   if min_str and seconds_str:
        return min_str + " And " + seconds_str
   elif min_str and not seconds_str:
        return min_str
   else:
        return seconds_str

@app.route('/')
@cross_origin
def index():
    user_id = request.args.get('user')
    if not user_id or len(user_id) < 8:
        return jsonify({'fail':'not valid user'})
    user = get_user_data(user_id)
    print "---- user ----"
    print user

    if not user:
        user = create_new_user(user_id)
        return jsonify({'function':'intro'})

    station = request.args.get('station')
    direction = request.args.get('direction')

    if request.args.get('reset'):
        delete_user(user_id)
        user = create_new_user(user_id)
        return jsonify({'function':'reset', 'say':'Your settings have been reset. What is the station you would like train times for? For example: Jefferson Street Or Union Square.'})

    print "----- station -----"
    print station
    print type(station)

    if station:
        try:
            station = int(station)
            update_station(user_id, station)
        except:
            print "---- STATION UPDATED BROKE ----"
            pass
    if direction:
        if station == '184' and direction == 'N':
            return jsonify({"say":"You cannot travel that direction from the 8th Avenue stop. What direction do you travel? For example: Towards Manhattan, or to Brooklyn.", 'function':'getDirection'})
        elif station == '399' and direction == 'S':
            return jsonify({"say":"You cannot travel that direction from the Canarsie Rockaway Parkway stop. What direction do you travel? For example: Towards Manhattan, or to Brooklyn.", 'function':'getDirection'})
        update_direction(user_id, direction)

    if station or direction:
        user = get_user_data(user_id)

    try:
        station = user[3]
    except:
        station = None
    try:
        direction = user[4]
    except:
        direction = None

    if not station:
        print "No Station <-----"
        return jsonify({"say":"What is the station you would like train times for? For example: Jefferson Street Or Union Square.", 'function':'getStation'})
    if not direction:
        print "No Direction <-----"
        return jsonify({"say":"What direction do you travel? For example: Towards Manhattan, or to Brooklyn.", 'function':'getDirection'})

    data = mta.get_by_id([user[3]])
    print data[0]
    print direction

    # Todo - This is hilariously bad, the entire thing...
    train_counter = 0
    try:
        first_train = get_time_data(data[0][direction][train_counter]['time'])
    except:
        first_train = False

    if not first_train:
        train_counter += 1
        try:
            first_train = get_time_data(data[0][direction][train_counter]['time'])
        except:
            first_train = False

        train_counter += 1 
        if not first_train:
            try:
                first_train = get_time_data(data[0][direction][train_counter]['time'])
            except:
                first_train = False

    if not first_train:
        return jsonify({
            'say': "We cannot find live train data for your station.",
            'function':'trainTime',
        })
    elif train_counter == 2:
        say = first_train
    else:
        train_counter += 1
        try:
            second_train = get_time_data(data[0][direction][train_counter]['time'])
            say = "%s. The following train is coming in %s" % (first_train, second_train)
        except:
            say = first_train

    return jsonify({
        'say': say,
        'function':'trainTime',
    })

@app.route('/by-location', methods=['GET'])
@cross_origin
def by_location():
    try:
        location = (float(request.args['lat']), float(request.args['lon']))
    except KeyError as e:
        print e
        response = jsonify({
            'error': 'Missing lat/lon parameter'
            })
        response.status_code = 400
        return response

    return jsonify({
        'updated': mta.last_update(),
        'data': mta.get_by_point(location, 5)
        })

@app.route('/by-route/<route>', methods=['GET'])
@cross_origin
def by_route(route):
    try:
        return jsonify({
            'updated': mta.last_update(),
            'data': mta.get_by_route(route)
            })
    except KeyError as e:
        abort(404)

@app.route('/by-id/<id_string>', methods=['GET'])
@cross_origin
def by_index(id_string):
    ids = [ int(i) for i in id_string.split(',') ]
    try:
        return jsonify({
            'updated': mta.last_update(),
            'data': mta.get_by_id(ids)
            })
    except KeyError as e:
        abort(404)

@app.route('/routes', methods=['GET'])
@cross_origin
def routes():
    return jsonify({
        'updated': mta.last_update(),
        'data': mta.get_routes()
        })

if __name__ == '__main__':
    app.run(use_reloader=True, port=8888)
