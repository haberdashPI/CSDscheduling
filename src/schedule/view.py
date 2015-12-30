from flask import (Flask, send_from_directory, redirect, Response, request,
                   jsonify)
import os
import schedule as s

app = Flask("schedule")
js_root = os.path.dirname(os.path.abspath(s.__file__))+'/js'
schedule = s.empty_schedule()


def show(sch):
  global schedule
  schedule = sch


@app.route("/")
def app_index():
  return redirect('app/index.html')


@app.route("/app/<path:path>")
def app_source(path):
  return send_from_directory(js_root,path)


@app.route('/request_data')
def request_data():
  return Response(schedule.tojson(),mimetype='application/json')


@app.route('/update_data',methods=['POST'])
def update_data():
  params = request.get_json()
  show(s.read_json(params['schedule']))
  if 'working_file' in params:
    schedule.save(params['working_file'])
  return Response(schedule.tojson(),mimetype='application/json')


@app.route('/load_file',methods=['POST'])
def load_file():
  params = request.get_json()
  if os.path.isfile(params['file']):
    show(s.read_schedule(params['file']))
    return Response(schedule.tojson(),mimetype='application/json')

  return jsonify(nofile=True)


# def data_stream():
#   while True: yield 'data: %s\n\n' % data_queue.get()

# @app.route('/data')
# def data():
#   return Response(data_stream(),mimetype='text/event-stream')
