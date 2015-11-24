import json
from pyrsistent import pset, PRecord, field, thaw
import scipy
import numpy as np

near_time = 25


def time_density(times):
  np.mean(scipy.spatial.pdist(times,'cityblock'))


def time_sparsity(times):
  dists = scipy.spatial.pdist(times,'cityblock')
  return np.mean(1.0 / (1.0+np.exp(-(near_time-dists))))


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
    return "NOfRequirement("+repr(self.mid)+","+repr(self.N)+","+repr(self.agents)+")"

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


class SetEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj, set):
      return list(obj)

    return json.JSONEncoder.default(self, obj)


class Schedule(object):
  def __init__(self,meetings,times,costs,unsatisfied,satisfied):
    self.unsatisfied = unsatisfied
    self.satisfied = satisfied
    self.costs = costs
    self.cost_cache = None

    self.meetings = meetings
    self.times = times

  def tojson(self):
    result = {'meetings': thaw(self.meetings),
              'times': thaw(self.times)}
    return json.dumps(result,cls=SetEncoder)

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
    return self.__add_helper__(mid,agents,time,requirement,False)

  def add_agent(self,mid,agents,requirement):
    return self.__add_helper__(mid,agents,None,requirement,True)

  def __add_helper__(self,mid,agents,time,requirement,ammend):
    meeting = self.meetings.get(mid,default=None)
    if ammend:
      assert meeting is not None
      meeting.set(agents=meeting.agents.add(agents))
    else:
      assert time is not None
      assert meeting is None
      meeting = Meeting(mid,agents,time)

    new_meetings = self.meetings.set(meeting.mid,meeting)
    new_times = self.times.evolver()
    for a in agents: new_times = new_times[a] - meeting.time

    if requirement.satisfied():
      old_value = self.satisfied.get(self.mid,default=pset([]))
      new_satisfied = self.satisfied.set(self.mid,old_value.add(requirement))

      new_value = self.unsatisfied.get(self.mid) - requirement
      if len(new_value):
        new_unsatisfied = self.unsatisfied.set(self.mid,new_value)
      else:
        new_unsatisfied = self.unsatisfied.remove(self.mid)

    return Schedule(new_meetings,new_times,self.costs,
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

    return Schedule(new_meetings,new_times,self.costs,
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

  def schedule_cost(self,schedule):
    if self.cost_cache is None:
      self.cost_cache = sum([self.costs[agent](times)
                             for agent,times in self.times.items()])
    return self.cost_cache
