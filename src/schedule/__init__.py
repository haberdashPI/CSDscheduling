from datetime import datetime, timedelta
import sys
import json
from pyrsistent import pset, PRecord, field, thaw, freeze, pmap, pvector
import scipy
import numpy as np
from copy import copy

# time: time is expressd in units of mintues from midnight
# for ease of expressing time cost funtions. The javascript
# code understands times expressed in milliseconds from
# midnight of Jan 1st 1970, so I have to convert between these two.

near_time = 25


def time_density(times):
  ts = np.array(t.start for t in times)
  np.mean(scipy.spatial.pdist(ts,'cityblock'))


def time_sparsity(times):
  ts = np.array(t.start for t in times)
  dists = scipy.spatial.pdist(ts,'cityblock')
  return np.mean(1.0 / (1.0+np.exp(-(near_time-dists))))

__epoch = datetime.utcfromtimestamp(0)
__epoch_base = datetime(2000,1,1)

def epoch_seconds(time):
  dt = __epoch_base + timedelta(minutes=time)
  return (dt - __epoch).total_seconds() * 1000.0


__base = datetime.strptime("12:00am","%I:%M%p")


def as_timerange(json):
  start = datetime.utcfromtimestamp(json['start'] / 1000.0,)
  end = datetime.utcfromtimestamp(json['end'] / 1000.0)

  return TimeRange(start=(start-__epoch_base).total_seconds()/60.,
                   end=(end-__epoch_base).total_seconds()/60.)


class TimeRange(PRecord):
  start = field()
  end = field()

  def __lt__(self,other):
    return self.start < other.start

  def JSONable(self):
    obj = thaw(self)
    obj['start'] = int(epoch_seconds(obj['start']))
    obj['end'] = int(epoch_seconds(obj['end']))
    return obj


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


class PRecordEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj,set):
      return sorted(list(obj))
    elif isinstance(obj,TimeRange):
      return obj.JSONable()
    elif isinstance(obj,PRecord):
      return thaw(obj)

    return json.JSONEncoder.default(self, obj)


def cached(fn):
  cached_name = fn.__name__

  def cached_fn(self,*args):
    try:
      return self.cache[cached_name]

    except KeyError:
      result = fn(self,*args)
      self.__dict__[cached_name] = result
      return result

  return cached_fn


def empty_schedule():
  return __empty


class Schedule(object):
  def __init__(self,agents,valid_times,meetings,times,available_times,
               costs,unsatisfied,satisfied):
    self.cache = {}

    # schedule constraints
    self.agents = agents  # vector of agents
    self.valid_times = valid_times  # set of valid times
    self.available_times = available_times  # map of agents to available times (as a set)

    # meetings
    self.times = times  # map from agents to available times minus meeting times
    self.meetings = meetings  # map from mids to meeting record (agents and time)
    self.unsatisfied = unsatisfied  # map from mids to unsatisified requirements
    self.satisfied = satisfied  # map from mids to satisified requirements
    self.costs = costs  # map from agents to meeting time costs fucntions


  def copy(self,**changes):
    result = copy(self)
    result.cache = {}
    for name,value in changes:
      result.__dict__[name] = value

    return result

  @cached
  def invert_meetings(self):
    inverted = {}
    for meeting in self.meetings:
      for agent in meeting.agents:
        times = inverted.get(agent,default={})
        times[meeting.time] = meeting.mid
        inverted[agent] = times

    return inverted

  @cached
  def schedule_cost(self):
    return sum([self.costs[agent](times) for agent,times in self.times.items()])

  @cached
  def tojson(self):
    def setup_time(time,agent_times):
      result = time.JSONable()
      result['available'] = time in agent_times
      return result

    valid_times = sorted(thaw(self.valid_times))
    result = {'agents': self.agents,
              'valid_times': valid_times,
              'available_times': {a: [setup_time(t,ts) for t in valid_times]
                                  for a,ts in self.times.iteritems()}}
    return json.dumps(result,cls=PRecordEncoder)

  def json_update(self,obj):
    new_agents = pvector(obj['agents'])
    new_valid_times = pset(obj['valid_times'])
    new_times = pmap({agent: pset([as_timerange(time)
                                   for time in times
                                   if time['available']])
                      for agent,times in obj['times']})

    # remove any meetings that with a no longer present agent
    new_satisfied = self.satisfied.evolver()
    new_unsatisfied = self.unsatisfied.evolver()
    new_meetings = self.meetings.evolver()
    for mid,requirements in (self.satisfied.iteritems() +
                             self.unsatisfied.iteritems()):
      for requirement in requirements:
        for agent in requirement.agents:
          if agent not in new_agents:
            if isinstance(AllOfRequirement,requirement):
              if mid in new_satisfied: new_satisfied.remove(mid)
              if mid in new_unsatisfied: new_unsatisfied.remove(mid)
              if mid in new_meetings: new_meetings.remove(mid)
            if (isinstance(NOfRequirement,requirement) and
                len(requirement.agents - agent) < requirement.N):
              if mid in new_satisfied: new_satisfied.remove(mid)
              if mid in new_unsatisfied: new_unsatisfied.remove(mid)
              if mid in new_meetings: new_meetings.remove(mid)

    # remove any meetings that now occur at an unavailable time
    for mid,meeting in new_meetings:
      if any(meeting.time not in new_times[agent]
             for agent in meeting.agents):
        if mid in new_satisfied:
          new_unsatisfied

  def add_time(self,time):
    return self.copy()

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

  def add_meeting_time(self,mid,agents,time,requirement):
    meeting = Meeting(mid,agents,time)
    return self.__add_helper(meeting,requirement)

  def add_agent_to_meeting(self,mid,agent,requirement):
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

    return self.copy(meetings=new_meetings,times=new_times.persistent(),
                     satisfied=new_satisfied,unsatisfied=new_unsatisfied)

  def remove_meeting(self,mid):
    meeting = self.meetings[mid]

    new_meetings = self.meetings.remove(mid)
    new_times = self.times.evolver()
    for a in meeting.agents:
      new_times[a] = new_times.get(a,default=pset([])).add(meeting.time)

    requirements = self.satisfied[mid]
    new_satisfied = self.satisfied.remove(mid)
    new_unsatisfied = self.unsatisfied.set(mid,requirements)

    return self.copy(meetings=new_meetings,times=new_times.persistent(),
                     satisfied=new_satisfied,unsatisfied=new_unsatisfied)

  def schedule_satisfied(self):
    return not len(self.unsatisfied)

  def valid_updates(self):
    valid = []
    for r in self.unsatisfied:
      result = r.valid_updates()
      if result: valid += result
      else: return []

    return valid


__empty = Schedule(agents=pvector([]),valid_times=pset({}),
                   meetings=pmap({}),times=pmap({}),
                   costs=pmap({}),unsatisified=pmap({}),
                   satisfied=pmap({}))