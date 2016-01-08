import schedule
import json
import schedule.view as view

with open("/Users/davidlittle/Downloads/console.json") as f:
  obj = json.load(f)

xs = view.request_solutions_helper(obj)