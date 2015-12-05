from datetime import datetime, timedelta
import sys
import json
from pyrsistent import pset, PRecord, field, thaw, freeze, pmap
import scipy
import numpy as np

near_time = 25


def time_density(times):
  ts = np.array(t.start for t in times)
  np.mean(scipy.spatial.pdist(ts,'cityblock'))


def time_sparsity(times):
  ts = np.array(t.start for t in times)
  dists = scipy.spatial.pdist(ts,'cityblock')
  return np.mean(1.0 / (1.0+np.exp(-(near_time-dists))))

# time is measured in minutes from 12:00am
class TimeRange(PRecord):
  start = field()
  end = field()

  def __lt__(self,other):
    return self.start < other.start


class Meeting(PRecord):
  mid = field()
  agents = field()
  time = field()


class NOfRequirement(object):
  def __init__(self,mid,N,agents):
    self.mid = mid
    self.N = N
    self.agents = pset(agents)

  def __repr__(self):
    return ("NOfRequirement("+repr(self.mid)+","+
            repr(self.N)+","+repr(self.agents)+")")

  def valid_updates(self,schedule):
    meeting = schedule.meetings.get(self.mid,default=None)
    if meeting:
      updates = [schedule.add_agent(self.mid,a,self)
                 for a in self.agents if schedule.available(a,meeting.time)]
      if len(updates): return updates
    else: return []

  def satisfied(self,schedule):
    meeting = schedule.meetings.get(self.mid,None)
    return meeting and len(self.agents & meeting.agents) > self.N


class AllOfRequirement(object):
  def __init__(self,mid,agents):
    self.mid = mid
    self.agents = pset(agents)

  def __repr__(self):
    return "AllOfRequirement("+repr(self.mid)+","+repr(self.agents)+")"

  def valid_updates(self,schedule):
    times = reduce(lambda x,y: x & y,[schedule.times[a] for a in self.agents])
    if len(times):
      return [schedule.add_meeting(self.mid,self.agents,t,self) for t in times]

  def satisfied(self,schedule):
    return self.mid in schedule.meetings

epoch = datetime.utcfromtimestamp(0)
def epoch_seconds(time):
  dt = datetime(2000,1,1) + timedelta(minutes=time)
  return (dt - epoch).total_seconds() * 1000.0

class PRecordEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj,set):
      return sorted(list(obj))
    elif isinstance(obj,TimeRange):
      obj = thaw(obj)
      obj['start'] = int(epoch_seconds(obj['start']))
      obj['end'] = int(epoch_seconds(obj['end']))
      return obj
    elif isinstance(obj,PRecord):
      return thaw(obj)

    return json.JSONEncoder.default(self, obj)

def cached(fn):
  cached_name = fn.__name__+'_cache'

  def cached_fn(self,*args):
    try:
      return self.__dict__[cached_name]

    except KeyError:
      result = fn(self,*args)
      self.__dict__[cached_name] = result
      return result

  return cached_fn


class Schedule(object):
  def __init__(self,agents,meetings,times,costs,unsatisfied,satisfied):
    self.unsatisfied = unsatisfied
    self.satisfied = satisfied
    self.costs = costs

    # a vector of agents, in an appropriate order
    self.agents = agents

    # map from meeting ids to meetings (holding the agents and time of the
    # meeting)
    self.meetings = meetings

    # map from agents to available times (as a set)
    self.times = times

  @cached
  def invert_meetings(self):
    inverted = {}
    for meeting in self.meetings:
      for agent in meeting.agents:
        times = inverted.get(agent,default={})
        times[meeting.time] = meeting.mid
        inverted[agent] = times

    return freeze(inverted)

  @cached
  def schedule_cost(self):
    return sum([self.costs[agent](times) for agent,times in self.times.items()])

  @cached
  def valid_times(self):
    return reduce(lambda a,b: a | b,self.times.values())

  @cached
  def tojson(self):
    def setup_time(time,agent_times):
      result = thaw(time)
      result['start'] = int(epoch_seconds(result['start']))
      result['end'] = int(epoch_seconds(result['end']))
      result['available'] = time in agent_times
      return result

    valid_times = sorted(thaw(self.valid_times()))
    result = {'meetings': thaw(self.meetings),
              'agents': self.agents,
              'times': {a: [setup_time(t,ts) for t in valid_times] 
                        for a,ts in self.times.iteritems()},
              'valid_times': valid_times,
              'meetings_inv': thaw(self.invert_meetings())}
    return json.dumps(result,cls=PRecordEncoder)

  def __repr__(self):
    return ("Assigned Meetings:\n" +
            "-----------------------\n" +
            repr(self.meetings) +
            "\nTimes:\n" +
            "-----------------------\n" +
            repr(self.times) +
            "\nUnsatisfied:\n" +
            "-----------------------\n" +
            repr(self.unsatisfied) +
            "\nsatisfied:\n" +
            "-----------------------\n" +
            repr(self.satisfied))

  def available(self,a,time):
    return time in self.times[a]

  def add_meeting(self,mid,agents,time,requirement):
    meeting = Meeting(mid,agents,time)
    return self.__add_helper(meeting,requirement)

  def add_agent(self,mid,agent,requirement):
    meeting = self.meetings.get(mid,default=None)
    meeting.set(agents=meeting.agents.add(agent))

    return self.__add_helper(meeting,requirement)

  def __add_helper(self,meeting,requirement):
    new_meetings = self.meetings.set(meeting.mid,meeting)
    new_times = self.times.evolver()
    for a in meeting.agents: new_times = new_times[a] - meeting.time

    if requirement.satisfied():
      old_value = self.satisfied.get(self.mid,default=pset([]))
      new_satisfied = self.satisfied.set(self.mid,old_value.add(requirement))

      new_value = self.unsatisfied.get(self.mid) - requirement
      if len(new_value):
        new_unsatisfied = self.unsatisfied.set(self.mid,new_value)
      else:
        new_unsatisfied = self.unsatisfied.remove(self.mid)
    else:
      new_unsatisfied = self.unsatisfied
      new_satisfied = self.satisfied

    return Schedule(self.agents,new_meetings,new_times,self.costs,
                    new_unsatisfied,new_satisfied)

  def remove_meeting(self,mid):
    meeting = self.meetings[mid]

    new_meetings = self.meetings.remove(mid)
    new_times = self.times.evolver()
    for a in meeting.agents:
      new_times[a] = new_times.get(a,default=pset([])).add(meeting.time)

    requirements = self.satisfied[mid]
    new_satisfied = self.satisfied.remove(mid)
    new_unsatisfied = self.unsatisfied.set(mid,requirements)

    return Schedule(self.agents,new_meetings,new_times,self.costs,
                    new_unsatisfied,new_satisfied)

  def schedule_satisfied(self):
    return not len(self.unsatisfied)

  def valid_updates(self):
    valid = []
    for r in self.unsatisfied:
      result = r.valid_updates()
      if result: valid += result
      else: return []

    return valid
