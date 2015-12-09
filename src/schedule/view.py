from flask import Flask, send_from_directory, redirect, Response, request
import os
import schedule as s
from Queue import Queue, Empty

app = Flask("schedule")
data_queue = Queue()
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
  show(schedule.json_update(params))
  return Response(schedule.tojson(),mimetype='application/json')


# def data_stream():
#   while True: yield 'data: %s\n\n' % data_queue.get()

# @app.route('/data')
# def data():
#   return Response(data_stream(),mimetype='text/event-stream')
