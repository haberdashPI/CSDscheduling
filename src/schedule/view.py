from flask import (Flask, send_from_directory, redirect, Response, request,
                   jsonify)
import os
import schedule as s
import numpy as np
import tempfile
from itertools import islice
import sys

app = Flask("schedule")
js_root = os.path.dirname(os.path.abspath(s.__file__))+'/js'

@app.route("/")
def app_index():
  return redirect('app/index.html')


@app.route("/app/<path:path>")
def app_source(path):
  return send_from_directory(js_root,path)


@app.route('/request_data',methods=['POST'])
def request_data():
  params = request.get_json()
  if 'newfile' in params:
    return Response(s.ScheduleProblem().tojson())
  elif os.path.isfile(params['file']):
    return Response(s.read_problem(params['file']).tojson(),
                    mimetype='application/json')
  else:
    return jsonify(nofile=True)


@app.route('/update_data',methods=['POST'])
def update_data():
  params = request.get_json()
  try:
    problem = s.read_problem_json(params['schedules'])
    if 'working_file' in params:
      problem.save(params['working_file'])
    else:
      problem.save(tempfile.gettempdir() + '/' + 'schedule_problem')
    return Response(problem.tojson(),mimetype='application/json')

  except s.RequirementException as e:
    if 'working_file' in params and os.path.isfile(params['working_file']):
      problem = s.read_problem(params['working_file'])
    else:
      problem = s.read_problem(tempfile.gettempdir() + '/' + 'schedule_problem')

    obj = problem.tojson(ammend={'unsatisfiable_meeting': e.requirement.mid})
    return Response(obj,mimetype='application/json')

def search(schedule,max_cycle):
  path = schedule
  last_mid = -1
  meeting_weights = {}
  for cycle in xrange(max_cycle):

    mid,path = path.sample_update(meeting_weights)
    if path is None: 
      meeting_weights[last_mid] = meeting_weights.get(last_mid,1.0) + 1.0
      print "meeting weights",meeting_weights
      last_mid = -1
      path = schedule
    elif path.satisfied():
      print ":D"
      sys.stdout.flush()

      yield path
      path = schedule
      last_mid = -1
    else:
      last_mid = mid

@app.route('/request_solutions',methods=["POST"])
def request_solutions():
  params = request.get_json()
  return Response(s.ScheduleProblem(request_solutions_helper(params)).tojson(),
                  mimetype='application/json')

def request_solutions_helper(params):
  n_solutions = params['n_solutions']
  take_best = params['take_best']
  max_cycles = params['max_cycles']
  schedule = s.read_schedule_json(params['schedule'])

  solutions = islice(sorted(islice(search(schedule,max_cycles),
                                   n_solutions),
                            key=lambda x: x.cost()),
                     take_best)

  return list(solutions)
  
# def data_stream():
#   while True: yield 'data: %s\n\n' % data_queue.get()

# @app.route('/data')
# def data():
#   return Response(data_stream(),mimetype='text/event-stream')
