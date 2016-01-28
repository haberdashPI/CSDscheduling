import numpy as np
import schedule
import json
import schedule.view as view
import schedule.new_schedule as sn

# with open("/Users/davidlittle/Downloads/console.json") as f:
#   obj = json.load(f)

with open("2016Schedule") as f:
  obj = json.load(f)

xs = sn.read_problem_json(obj)
xs.solutions[0].to_csv('schedule2016.csv')
# xs = sn.read_schedule_json(obj['schedules'][0])
# xs.save('schedule2015.f.json')
# xs = view.request_solutions_helper(obj)
# xs = sn.read_schedule_json(obj[0])
# x1 = xs.copy()
# miss_counts = np.ones(len(x1.mids))

# TODO: this should work, but it doesn't, figure out why
# x1.clear_meetings()
# x1.sample_update(miss_counts,2)
# x1.sample_update(miss_counts,45)

# count = 0
# for i in range(10000):
#   count += 1
#   if x1.satisfied():
#     print "TADA!"
#     break
#   else:
#     try:
#       x1.sample_update(miss_counts)
#     except schedule.RequirementException as e:
#       print "No space for meeting: ",str(x1.mids[e.requirement])," (step ",str(count),")"
#       x1.clear_meetings()
#       miss_counts[e.requirement] += 1
#       count = 0
