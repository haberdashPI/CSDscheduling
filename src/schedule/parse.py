from pyrsistent import pmap, pset
import re
import pandas as pd
import numpy as np
from datetime import datetime
from schedule import (AllOfRequirement, NOfRequirement, time_sparsity,
                      time_density, Schedule, TimeRange)


def parse_student_meetings(meetings,N,offset=0):
  requirements = []
  i = offset
  for _,student_meetings in meetings.iterrows():
    student = student_meetings.values[0]
    for faculty in clean_up(student_meetings[1:N].values):
      requirements.append(AllOfRequirement(i,[student,faculty]))
      i += 1

    optional = map(lambda x: x.strip(),student_meetings[N+1].split(","))
    requirements.append(AllOfRequirement(i,[student]))
    requirements.append(NOfRequirement(i,1,clean_up(optional)))
    i += 1

  return requirements


def parse_lab_meetings(meetings,offset=0):
  requirements = []
  for i,lab_meeting in meetings.iterrows():
    students = np.array(meetings.columns[2:])
    students = list(students[np.where(lab_meeting[students] == 1)])
    if lab_meeting['pi required'] == 1:
      requirement = AllOfRequirement(i+offset,
                                     students + clean_up([lab_meeting['lab']]))
      requirements.append(requirement)

  return requirements


__base = datetime.strptime("12:00am","%I:%M%p")

def parse_time(time):
  start,end = time.split("-")

  start_am = datetime.strptime(start+"am","%I:%M%p")
  start_pm = datetime.strptime(start+"pm","%I:%M%p")
  end = datetime.strptime(end,"%I:%M%p")

  if (abs((start_am - end).total_seconds()) <
      abs((start_pm - end).total_seconds())):
    start = start_am
  else: start = start_pm

  return TimeRange(start=(start-__base).total_seconds()/60.,
                   end=(end-__base).total_seconds()/60.)

def parse_schedule(schedule):
  times = {}
  for col in schedule.columns:
    times[col] = pset(map(parse_time,
                          clean_up(schedule[schedule[col] != 1].index.values)))

  return (times, schedule.columns)


def parse_costs(costs):
  fns = [time_sparsity,time_density]
  return dict(zip(clean_up(costs.name),
                  [fns[int(is_dense == 1)] for is_dense in costs['dense?']]))


def clean_up(strs):
  return [re.sub(r'\s',' ',str.strip().lower()) for str in strs]


def parse_file(excel_file):
  excel = pd.ExcelFile(excel_file)

  df = excel.parse('Schedule',index_col=0)
  df.columns = clean_up(df.columns)
  times,agents = parse_schedule(df)

  df = excel.parse('Meetings',index_col=None)
  df.columns = clean_up(df.columns)
  del df['area']
  df.name = clean_up(df.name)
  meetings = parse_student_meetings(df,3)

  offset = meetings[-1].mid+1
  df = excel.parse('Lab Meetings',index_col=None)
  df.columns = clean_up(df.columns)
  meetings += parse_lab_meetings(df,offset=offset)

  df = excel.parse('Schedule Preferences')
  df.columns = clean_up(df.columns)
  costs = parse_costs(df)

  final_meetings = {}
  for requirement in meetings:
    old = final_meetings.get(requirement.mid,pset())
    final_meetings[requirement.mid] = old.add(requirement)

  return Schedule(list(agents),pmap(),pmap(times),costs,
                  pmap(final_meetings),pmap())
