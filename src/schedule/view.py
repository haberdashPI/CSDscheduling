from flask import (Flask, send_from_directory, redirect, Response, request,
                   jsonify)
import os
import schedule as s
import schedule.new_schedule as sn
import tempfile
import numpy as np
from itertools import islice
from datetime import datetime, timedelta

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
    return Response(sn.FastScheduleProblem().tojson())
  elif os.path.isfile(params['file']):
    return Response(sn.read_problem(params['file']).tojson(),
                    mimetype='application/json')
  else:
    return jsonify(nofile=True)


@app.route('/update_data',methods=['POST'])
def update_data():
  params = request.get_json()
  try:
    problem = sn.read_problem_json(params['schedules'])
    if 'working_file' in params:
      problem.save(params['working_file'])
    else:
      problem.save(tempfile.gettempdir() + '/' + 'schedule_problem')
    return Response(problem.tojson(),mimetype='application/json')

  except s.RequirementException as e:
    if 'working_file' in params and os.path.isfile(params['working_file']):
      problem = sn.read_problem(params['working_file'])
    else:
      problem = sn.read_problem(tempfile.gettempdir() + '/' + 'schedule_problem')

    obj = problem.tojson(ammend={'unsatisfiable_meeting': e.mids[e.mindex]})
    return Response(obj,mimetype='application/json')
  except sn.AvailableTimesException as e:
    if 'working_file' in params and os.path.isfile(params['working_file']):
      problem = sn.read_problem(params['working_file'])
    else:
      problem = sn.read_problem(tempfile.gettempdir() + '/' + 'schedule_problem')

    obj = problem.tojson(ammend={'not_enough_times_agent': e.agents[e.aindex]})
    return Response(obj,mimetype='application/json')


class FailedSearchException(Exception):
  pass


def search(schedule,max_time):
  miss_counts = np.ones(len(schedule.mids))
  end_time = datetime.now() + timedelta(0,max_time)
  n_solutions = 0

  while datetime.now() < end_time:
    if schedule.satisfied():
      yield schedule.copy()
      n_solutions += 1
      schedule.clear_meetings()
    else:
      try:
        schedule.sample_update(miss_counts)
      except sn.RequirementException as e:
        schedule.clear_meetings()
        miss_counts[e.mindex] += 1

  if n_solutions == 0:
    raise FailedSearchException(schedule.mids,miss_counts)


@app.route('/request_solutions',methods=["POST"])
def request_solutions():
  params = request.get_json()
  try:
    return Response(sn.FastScheduleProblem(request_solutions_helper(params)).tojson(),
                    mimetype='application/json')
  except FailedSearchException as e:
    # find the most difficult to schedule meetings
    mids, counts = e.args
    order = np.argsort(counts)
    cpf = np.cumsum(counts[order])
    cpf /= cpf[len(cpf)-1].astype('float_')
    worst_mids = reversed([mids[i] for i in order[cpf > 0.05]])

    return Response(sn.FastScheduleProblem([]).tojson(ammend=[worst_mids]))


def request_solutions_helper(params):
  n_solutions = params['n_solutions']
  take_best = params['take_best']
  max_time = params['max_time_s']
  schedule = sn.read_schedule_json(params['schedule'])

  solutions = islice(sorted(islice(search(schedule,max_time),n_solutions),
                            key=lambda x: x.cost()),take_best)
  return list(solutions)

  
# def data_stream():
#   while True: yield 'data: %s\n\n' % data_queue.get()

# @app.route('/data')
# def data():
#   return Response(data_stream(),mimetype='text/event-stream')
