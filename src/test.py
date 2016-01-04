import schedule
import json

with open("/Users/davidlittle/Downloads/console.json") as f:
  obj = json.load(f)

s = schedule.read_json(obj)