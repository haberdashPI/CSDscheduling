import pprint
from datetime import datetime, timedelta
import json
from pyrsistent import pset, PRecord, field, thaw, pmap, pvector
import scipy
import numpy as np
from copy import copy

# time: time is expressd in units of mintues from midnight
# for ease of expressing time cost funtions. The javascript
# code understands times expressed in milliseconds from
# midnight of Jan 1st 1970, so I have to convert between these two.


# TODO: work on seperating the scheudle constraints
# from the schedule solution, so that I can have multiple
# solutions in the same scheudle object. 

near_time = 25


def time_density(times):
  ts = np.array(t.start for t in times)
  np.mean(scipy.spatial.pdist(ts,'cityblock'))


def time_sparsity(times):
  ts = np.array(t.start for t in times)
  dists = scipy.spatial.pdist(ts,'cityblock')
  return np.mean(1.0 / (1.0+np.exp(-(near_time-dists))))


costs_fns = {'density': time_density, 'sparsity': time_sparsity}

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


def timestring(timerange):
  timerange.start.strftime('%I:%M %p',)


class Meeting(PRecord):
  mid = field()
  agents = field()
  time = field()


class OneOfRequirement(object):
  def __init__(self,mid,agents):
    self.mid = mid
    self.agents = pset(agents)
    self.type = 'oneof'

  def valid_updates(self,schedule):
    meeting = schedule.backward.get(self.mid,default=None)
    if meeting:
      updates = [schedule.add_meeting(meeting,a,self)
                 for a in self.agents if schedule.available(a,meeting.time)]
      if len(updates): return updates
    else: return []

  def satisfied(self,schedule):
    return (self.mid in schedule.backward and
            len(self.agents | schedule.backward[self.mid].agents))

  def satisfiable(self,schedule):
    return len(self.agents | pset(schedule.agents))

  def __repr__(self):
    return "OneOfRequirement("+repr(self.mid)+","+repr(self.agents)+")"

  def JSONable(self):
    return {'mid': self.mid, 'agents': sorted(list(self.agents)), 
           'type': self.type}


class AllOfRequirement(object):
  def __init__(self,mid,agents):
    self.mid = mid
    self.agents = pset(agents)
    self.type = 'allof'

  def valid_updates(self,schedule):
    meeting = Meeting(mid=self.mid,agents=None,time=None)
    times = schedule.times - pset([t for a in schedule.agents
                                   for t in a.keys()])
    if len(times):
      return [schedule.add_meeting(meeting.set(time=t),self.agents,self)
              for t in times]

  def satisfied(self,schedule):
    return (self.mid in schedule.backward and
            self.agents <= schedule.backward[self.mid].agents)

  def satisfiable(self,schedule):
    return self.agents <= pset(schedule.agents)

  def __repr__(self):
    return "AllOfRequirement("+repr(self.mid)+","+repr(self.agents)+")"

  def JSONable(self):
    return {'mid': self.mid, 'agents': sorted(list(self.agents)), 
           'type': self.type}


def read_jsonable_requirement(obj):
  if obj['type'] == "allof":
    if len(obj['agents']):
      return AllOfRequirement(obj['mid'],obj['agents'])
  elif obj['type'] == "oneof":
    if len(obj['agents']):
      return OneOfRequirement(obj['mid'],obj['agents'])
  else:
    raise RuntimeError("Unknown requirement type: "+str(obj['type']))


class PRecordEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj,set):
      return sorted(list(obj))
    elif isinstance(obj,TimeRange):
      return obj.JSONable()
    elif isinstance(obj,AllOfRequirement):
      obj = obj.JSONable()
      return obj
    elif isinstance(obj,OneOfRequirement):
      obj = obj.JSONable()
      return obj
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


def read_schedule(file):
  with open(file,'rt') as f:
    results = eval(f.read())
    agents = results['agents']
    times = results['times']
    forward = results['forward']
    backward = results['backward']
    unsatisfied = results['unsatisfied']
    requirements = results.get('requirements',pmap({}))
    costs = results['costs']

    return Schedule(agents=agents,times=times,forward=forward,
                    backward=backward,costs=costs,unsatisfied=unsatisfied,
                    requirements=requirements)


def read_json(obj):
    # reconstruct schedule information from json
    agents = pvector(obj['agents'])
    times = pset(map(as_timerange,obj['times']))
    forward = pmap({a: pmap({as_timerange(t): t['mid']
                             for t in obj['meetings'][a] if t['mid'] != -1})
                    for a in agents})

    mids = pset([mid for ts in forward.values() for mid in ts.values()])

    # remove the mid 0, which marks an empty meeting (for unavailable times)
    if 0 in mids:
      mids = mids.remove(0)

    # update meetings and their requirements
    requirements = pmap({mid: pmap({r['type']: read_jsonable_requirement(r)
                                    for r in rs.values()})
                         for mid,rs in obj['requirements'].iteritems()})

    schedule = Schedule(agents=agents,times=times,forward=forward,
                        requirements=requirements)

    new_unsatisfied = schedule.unsatisfied
    for mid,rs in schedule.unsatisfied.iteritems():
      for rtype in rs:
        r = schedule.requirements[mid][rtype]
        if r.satisfied(schedule):
          new_unsatisfied = _mark_satisfied(new_unsatisfied,r)
    schedule.unsatisfied = new_unsatisfied

    # TODO: check for any requirements that cannot be satisfied

    return schedule


def _backward_from_forward(forward):
  backward = {}
  for agent,meetings in forward.iteritems():
    for time,mid in meetings:
      backward[mid] = \
        backward.get(mid,Meeting(mid=mid,agents=pset([]),time=time))
      backward[mid].set(agents=backward[mid].agents.add(agent))
  return pmap(backward)


def _mark_satisfied(unsatisfied,r):
    reqs = unsatisfied.get(r.mid).remove(r.type)
    if len(reqs):
      return unsatisfied.set(r.mid,reqs)
    else:
      return unsatisfied.remove(r.mid)


class Schedule(object):
  def __init__(self,agents=pvector([]),times=pset([]),forward=pmap({}),
               costs=pmap({}),requirements=pmap({}),backward=None,
               unsatisfied=None):
    self.cache = {}

    #### schedule bounds
    self.agents = agents  # vector of valid agents
    self.times = times  # set of valid times

    #### the schedule itself
    self.forward = forward  # agents -> times -> meeting ids

    # mids -> meeting (times, agents)
    if backward is None: self.backward = _backward_from_forward(self.forward)
    else: self.backward = backward

    #### schedule constraints
    self.requirements = requirements  # mids -> requirement type -> requirement

    # mids -> requirement type
    if unsatisfied is None:
      self.unsatisfied = pmap({mid: pset(self.requirements[mid].keys())
                               for mid in self.requirements.keys()})
    else: self.unsatisfied = unsatisfied

    self.costs = costs  # map from agents to meeting time costs functions

  def copy(self,**changes):
    result = copy(self)
    result.cache = {}
    for name,value in changes.iteritems():
      result.__dict__[name] = value

    return result

  def available(self,agent,time):
    return time not in self.forward[agent][time]

  def add_meeting(self,meeting,agents,requirement):
    new_forward = self.new_forward.evolver()
    for agent in agents:
      new_forward[agent] = new_forward[agent].set(meeting.time,meeting.mid)
    new_backward = self.backward.set(meeting.mid,meeting)

    new_unsatisfied = self.mark_satisfied(requirement)

    return self.copy(forward=new_forward.persistent(),backward=new_backward,
                     unsatisfied=new_unsatisfied)

  def remove_meeting(self,mid):
    meeting = self.backward[mid]
    new_forward = self.new_forward.evolver()
    for agent in meeting.agents:
      new_forward[agent] = new_forward[agent].remove(meeting.time)
    new_backward = self.backward.remove(mid)

    new_requirements = pset({r.type for r in self.requirements[mid]})

    return self.copy(forward=new_forward.persistent(),backward=new_backward,
                     unsatisfied=self.unsatisfied.set(mid,new_requirements))

  def schedule_satisfied(self):
    return not len(self.unsatisfied)

  def valid_updates(self):
    valid = []
    for (mid,rtype),r in self.unsatisfied:
      result = r.valid_updates(self)
      if result is not None: valid += result
      else: return []

    return valid

  @cached
  def schedule_cost(self):
    return sum([costs_fns[self.costs[agent](times)]
                for agent,times in self.times.items()])

  @cached
  def tojson(self):
    def setup_time(time,scheduled):
      result = time.JSONable()
      result['mid'] = scheduled
      return result

    result = {'agents': thaw(self.agents),
              'times': thaw(self.times),
              'requirements': thaw({mid: {r.type: r for r in rs.values()}
                                    for mid,rs in
                                    self.requirements.iteritems()}),
              'meetings': {a: [setup_time(t,ts.get(t,default=-1))
                               for t in self.times]
                           for a,ts in self.forward.iteritems()}}
    return json.dumps(result,cls=PRecordEncoder)

  def save(self,file):
    with open(file,'wb') as f:
      pprint.pprint({'agents': self.agents,
                     'times': self.times,
                     'forward': self.forward,
                     'backward': self.backward,
                     'requirements': self.requirements,
                     'unsatisfied': self.unsatisfied,
                     'costs': self.costs},f)

  def lookup_requirements(self,mid):
    return self.requirement[mid]

  def mids(self):
    return self.requirements.keys()

__empty = Schedule(agents=pvector([]),times=pset([]),
                   forward=pmap({}),backward=pmap({}),
                   unsatisfied=pmap({}),costs={})
