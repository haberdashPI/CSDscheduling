from flask import Flask, send_from_directory, redirect, Response
import os
import schedule
from Queue import Queue

app = Flask("schedule")
data_queue = Queue()
js_root = os.path.dirname(os.path.abspath(schedule.__file__))+'/js'


@app.route("/")
def app_index():
  return redirect('app/index.html')


@app.route("/app/<path:path>")
def app_source(path):
  return send_from_directory(js_root,path)


def data_stream():
  while True: yield 'data: %s\n\n' % data_queue.get()


@app.route('/data')
def data():
  return Response(data_stream(),mimetype='text/event-stream')
