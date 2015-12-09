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
  requirements = field()

  def satisified(self,schedule):
    return all([r.satisified(schedule) for r in self.requirements])


class OneOfRequirement(object):
  def __init__(self,mid,N,agents):
    self.mid = mid
    self.agents = pset(agents)

  def valid_updates(self,schedule,meeting):
    meeting = schedule.backward.get(self.mid,default=None)
    if meeting:
      updates = [schedule.add_meeting(meeting,a,self)
                 for a in self.agents if schedule.available(a,meeting.time)]
      if len(updates): return updates
    else: return []

  def satisified(self,schedule):
    return len(self.agents | schedule.backward[self.mid].agents)

  def satisfiable(self,schedule):
    return len(self.agents | pset(schedule.agents))


class AllOfRequirement(object):
  def __init__(self,mid,agents):
    self.mid = mid
    self.agents = pset(agents)

  def valid_updates(self,schedule,meeting):
    times = schedule.times - pset([t for a in schedule.agents 
                                   for t in a.keys()])
    if len(times):
      return [schedule.add_meeting(meeting.set(time=t),self.agents,self)
              for t in times]

  def satisfied(self,schedule):
    return self.agents <= schedule.backward[self.mid].agents

  def satisfiable(self,schedule):
    return self.agents <= pset(schedule.agents)


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
      self.cache[cached_name] = result
      return result

  return cached_fn


def empty_schedule():
  return __empty


class Schedule(object):
  def __init__(self,agents,times,forward,backward,
               costs,unsatisfied):
    self.cache = {}

    # schedule bounds
    self.agents = agents  # vector of valid agents
    self.times = times  # set of valid times

    # the schedule itself
    self.forward = forward  # agents -> times -> meeting ids
    self.backward = backward  # mids -> (times, agents)

    # schedule constraints
    self.unsatisfied = unsatisfied  # map from mids to unsatisified meetings
    self.costs = costs  # map from agents to meeting time costs functions


  def copy(self,**changes):
    result = copy(self)
    result.cache = {}
    for name,value in changes.iteritems():
      result.__dict__[name] = value

    return result

  def available(self,agent,time):
    return time not in self.forward[agent][time]

  def add_meeting(self,meeting,agents,new_satisified):
    new_forward = self.new_forward.evolver()
    for agent in agents:
      new_forward[agent] = new_forward[agent].set(meeting.time,meeting.mid)
    new_backward = self.backward.set(meeting.mid,meeting)

    new_requirements = self.unsatisfied.get(meeting.mid) - new_satisified
    new_unsatisfied = self.unsatisfied.set(meeting.mid,new_requirements)

    return self.copy(forward=new_forward.persistent(),backward=new_backward,
                     unsatisfied=new_unsatisfied)

  def remove_meeting(self,mid):
    meeting = self.backward[mid]
    new_forward = self.new_forward.evolver()
    for agent in meeting.agents:
      new_forward[agent] = new_forward[agent].remove(meeting.time)
    new_backward = self.backward.remove(mid)
    new_unsatisfied = self.unsatisfied.set(mid,meeting.requirements)

    return self.copy(forward=new_forward.persistent(),backward=new_backward,
                     unsatisfied=new_unsatisfied)

  def schedule_satisfied(self):
    return not len(self.unsatisfied)

  def valid_updates(self):
    valid = []
    for meeting in self.unsatisfied:
      for r in meeting.requirements:
        result = r.valid_updates(self,meeting)
        if result is not None: valid += result
        else: return []

    return valid

  @cached
  def schedule_cost(self):
    return sum([self.costs[agent](times) for agent,times in self.times.items()])

  @cached
  def tojson(self):
    def setup_time(time,scheduled):
      result = time.JSONable()
      if scheduled is not None:
        result['mid'] = scheduled
      else:
        result['mid'] = -1
      return result

    result = {'agents': thaw(self.agents),
              'times': thaw(self.times),
              'meetings': {a: [setup_time(t,ts.get(t,default=None))
                               for t in self.times]
                           for a,ts in self.forward.iteritems()}}
    return json.dumps(result,cls=PRecordEncoder)

  def lookup_meeting(self,mid):
    if mid in self.backward:
      return self.backward[mid]
    else:
      return self.unsatisfied[mid]

  def mids(self):
    return self.backward.keys() + self.unsatisfied.keys()

  def json_update(self,obj):
    # reconstruct schedule information from json
    new_agents = pvector(obj['agents'])
    new_times = pset(map(as_timerange,obj['times']))
    new_forward = pmap({a: pmap({as_timerange(t): t.mid
                                 for t in obj['meetings'][a] if t.mid != -1})
                        for a in new_agents})

    mids = pset([mid for times in new_forward.values()
                 for mid in times.values()])

    # update organization of meetings
    new_backward = pmap({mid: self.lookup_meeting(mid) for mid in mids})
    new_unsatisfied = pmap({mid: self.lookup_meeting(mid) for mid in self.mids()
                            if mid not in mids})
    new_self = self.copy(agents=new_agents,times=new_times,forward=new_forward,
                         backward=new_backward,unsatisifed=new_unsatisfied)

    # move any meetings back to unsatisifed if they aren't satisified anymore
    for meeting in new_self.backward.values():
      if not meeting.satisified(new_self):
        new_self = new_self.remove_meeting(meeting.mid)

    # remove any meetings that can never be satisified
    final_unsatisfied = new_self.unsatisfied.evolver()
    for meeting in new_self.unsatisfied.values():
      if not meeting.satisifiable(new_self):
        del final_unsatisfied[meeting.mid]

    return new_self.copy(unsatisfied=final_unsatisfied.persistent())

__empty = Schedule(agents=pvector([]),times=pset([]),
                   forward=pmap({}),backward=pmap({}),
                   unsatisfied=pmap({}),costs={})