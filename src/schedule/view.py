from flask import (Flask, send_from_directory, redirect, Response, request,
                   jsonify)
import os
import schedule as s
import numpy as np
import tempfile
from itertools import islice

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


def search(schedule,breadth):
  paths = np.array(schedule for i in xrange(breadth))
  queue = []

  while len(paths):
    for i in xrange(len(paths)):
      choices = []
      for path in paths[i].valid_updates():
        if path.satisfied(): yield path
        else: choices.push(path)

      costs = map(lambda x: x.cost(),choices)
      softmax = np.exp(costs/(s.near_time*s.near_time))

      paths[i] = np.random.choice(choices,p=softmax)


@app.route('/request_solution')
def request_solutions():
  global solutions

  params = request.get_json()
  n_solutions = params['n_solutions']
  breadth = params['breadth']

  solutions = iter(search(schedule,breadth))

  return Response([s.tojson() for s in islice(n_solutions,solutions)],
                  mimetype='application/json')


# TODO: implement retrieval of more solutions
# TODO: implement retrieval of best solutions




# def data_stream():
#   while True: yield 'data: %s\n\n' % data_queue.get()

# @app.route('/data')
# def data():
#   return Response(data_stream(),mimetype='text/event-stream')
