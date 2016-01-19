from numba import jit
import numpy as np
import schedule as sch
import json
# TODO: handle multiple schedules from json
# TODO: read and write multiple schedules from a file (hdf5 probably)
# TODO: perform functions as part of numba loop

@jit(nopython=True)
def time_sparsity(time_indices):
  n_contiguous = 0
  max_contiguous = 0
  for i in range(1,len(time_indices)):
    if time_indices[i] == time_indices[i-1]+1:
      n_contiguous += 1
    else:
      if max_contiguous < n_contiguous:
        max_contiguous = n_contiguous
      n_contiguous = 0
  return max_contiguous


@jit(nopython=True)
def time_density(time_indices):
  n_noncontiguous = 0
  for i in range(1,len(time_indices)):
    if time_indices[i] != time_indices[i-1]+1:
      n_noncontiguous += 1
  return n_noncontiguous


cost_fns = {'density': time_density,
            'sparsity': time_sparsity,
            'none': lambda xs: 0.0}

def read_problem(file):
  with open(file,'r') as f:
    return FastScheduleProblem([read_schedule_json(s) for s in json.load(f)])


class FastScheduleProblem(sch.ScheduleProblem):
  def save(self,file):
    with open(file,'w') as f:
      return json.dump([s._tojson_helper() for s in self.solutions],f,
                       cls=sch.PRecordEncoder)

def read_problem_json(obj):
  return FastScheduleProblem([read_schedule_json(s) for s in obj])


def read_schedule_json(obj):
  agents = obj['agents']
  costs = obj['costs']
  times = sorted(map(sch.as_timerange,obj['times']))
  mids = obj['requirements'].keys()

  schedule = FastSchedule(agents,costs,times,mids)

  mindices = {mid: mindex for mindex,mid in enumerate(mids)}
  aindices = {agent: aindex for aindex,agent in enumerate(agents)}

  for mid,r in obj['requirements'].iteritems():
    mindex = mindices[mid]
    if 'allof' in r:
      for i,agent in enumerate(r['allof']['agents']):
        schedule.allof[mindex,i] = aindices[agent]
      schedule.allof_len[mindex] = len(r['allof']['agents'])

    if 'oneof' in r:
      for i,agent in enumerate(r['oneof']['agents']):
        schedule.oneof[mindex,i] = aindices[agent]
      schedule.oneof_len[mindex] = len(r['oneof']['agents'])

  for aindex,agent in enumerate(agents):
    atimes = sorted(obj['meetings'][agent],key=sch.as_timerange)
    for j,time in enumerate(atimes):
      if 'mid' in time:
        if time['mid'] >= 1:
          mindex = mindices[time['mid']]
          schedule.meetings[aindex,j] = mindex+1
          schedule.mtimes[mindex] = j

          oneofs = schedule.oneof[mindex,:schedule.oneof_len[mindex]]
          if aindex in oneofs:
            schedule.oneof_selected[mindex] = aindex

        elif time['mid'] == 0:
          schedule.meetings[aindex,j] = 0

  unsatisfied = set(range(len(mids)))
  for mindex,mid in enumerate(mids):
    if (mid not in obj['unsatisfied'] or
        len(obj['unsatisfied'][mid]) == 0):
      unsatisfied.remove(mindex)
  schedule.unsatisfied[:len(unsatisfied)] = sorted(unsatisfied)
  schedule.unsatisfied_len = len(unsatisfied)

  schedule.calculate_possible_times()
  return schedule


class AvailableTimesException(Exception):
  def __init__(self,aindex,agents):
    self.aindex = aindex
    self.agents = agents

    msg = "Not enough available times for " + str(self.agents[self.aindex])
    super(AvailableTimesException,self).__init__(msg)


class RequirementException(Exception):
  def __init__(self,mindex,mids):
    self.mindex = mindex
    self.mids = mids
    msg = "Unsatisfiable requirement " + str(self.mids[self.mindex])
    super(RequirementException,self).__init__(msg)


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


class FastSchedule(object):
  def __init__(self,agents,costs,times,mids):
    self.cache = {}
    self.agents = agents
    self.times = times
    self.mids = mids
    self.costs = costs

    # array of meetings for each agent and time
    # -1: no meeting
    # 0: unavailable meeting time
    # n>0: meeting with meeting index = n-1
    self.meetings = -np.ones((len(self.agents),len(self.times)),dtype='int_')

    # the times of all meetings
    # -1: no meeting at this time
    # n>-1: meeting at time index n
    self.mtimes = -np.ones(len(self.mids),dtype='int_')

    # array of possible times for each meeting
    # row n: times for nth meeting
    # col m: the mth time for nth meeting
    self.possible_times = None
    # length of each list of possible times for each meeting
    # row n: the number of times for nth meeting
    self.possible_times_len = None

    # array of agents that all must be at a meeting
    # row n: agents for nth meeting
    # col m: mth agent for nth meeting
    self.allof = -np.ones((len(self.mids),len(self.agents)),dtype='int_')
    # array of number of agents that all must be at a meeting
    # row n: number of agents that must be at the nth meeting
    self.allof_len = np.zeros(len(self.mids),dtype='int_')
    # array of agents, one of which must be at a meeting
    # row n: agents for nth meeting
    # col m: mth agent for nth meeting
    self.oneof = -np.ones((len(self.mids),len(self.agents)),dtype='int_')
    # array of number of agents, one of which must be at a meeting
    # row n: number of agents, one of which must be at the nth meeting
    self.oneof_len = np.zeros(len(self.mids),dtype='int_')
    # row n: the agent who is assigned to be at meeting n
    # -1: no agent assigned
    # i>-1: ith agent assigned
    self.oneof_selected = -np.ones((len(self.mids)),dtype='int_')

    # array of unsatisfied meeting indices
    self.unsatisfied = np.arange(len(self.mids))
    # number of unsatisfied meetings
    self.unsatisfied_len = len(self.mids)

  def copy(self):
    schedule = FastSchedule(self.agents,self.costs,self.times,self.mids)

    schedule.meetings = self.meetings.copy()
    schedule.mtimes = self.mtimes.copy()

    schedule.possible_times = self.possible_times.copy()
    schedule.possible_times_len = self.possible_times_len.copy()

    schedule.allof = self.allof.copy()
    schedule.allof_len = self.allof_len.copy()
    schedule.oneof = self.oneof.copy()
    schedule.oneof_len = self.oneof_len.copy()
    schedule.oneof_selected = self.oneof_selected.copy()

    schedule.unsatisfied = self.unsatisfied.copy()
    schedule.unsatisfied_len = self.unsatisfied_len

    return schedule

  def _tojson_helper(self):
    result = {}
    result['agents'] = self.agents
    result['times'] = self.times

    result['requirements'] = {}
    result['unsatisfied'] = {}
    for mindex,mid in enumerate(self.mids):
      result['requirements'][mid] = {}
      result['unsatisfied'][mid] = []
      if self.allof_len[mindex] > 0:
        allof = [self.agents[i]
                 for i in self.allof[mindex,:self.allof_len[mindex]]]
        result['requirements'][mid]['allof'] = \
          {'agents': allof, 'type': 'allof'}
        if (len(allof) and self.mtimes[mindex] < 0):
          result['unsatisfied'][mid].append('allof')
      if self.oneof_len[mindex] > 0:
        oneof = [self.agents[i]
                 for i in self.oneof[mindex,:self.oneof_len[mindex]]]
        result['requirements'][mid]['oneof'] = \
          {'agents': oneof, 'type': 'oneof'}
        if (len(oneof) and self.oneof_selected[mindex] < 0):
          result['unsatisfied'][mid].append('oneof')

    result['costs'] = self.costs

    result['cost_values'] = {}
    for aindex,agent in enumerate(self.agents):
      if agent in self.costs:
        times = np.where(self.meetings[aindex,:] > 0)[0]
        result['cost_values'][agent] = cost_fns[self.costs[agent]](times)
      else:
        result['cost_values'][agent] = 0

    result['cost'] = self.cost()

    result['meetings'] = {}
    for aindex,agent in enumerate(self.agents):
      result['meetings'][agent] = []
      for tindex,time in enumerate(self.times):
        entry = time.JSONable()
        mindex_p1 = self.meetings[aindex,tindex]

        if mindex_p1 == 0: entry['mid'] = 0
        elif mindex_p1 > 0: entry['mid'] = self.mids[mindex_p1-1]
        else: entry['mid'] = -1
        result['meetings'][agent].append(entry)

    return result

  @cached
  def cost(self):
    cost = 0
    # how much do all scheduled meetings cost?
    for i,agent in enumerate(self.agents):
      if agent in self.costs:
        times = np.where(self.meetings[i,:] > 0)[0]
        cost += cost_fns[self.costs[agent]](times)

    # guess how much unsatisfied meetings will cost
    unsatisfied = self.unsatisfied[:self.unsatisfied_len]
    cost += np.sum(self.allof_len[unsatisfied])
    cost += np.sum(self.oneof_len[unsatisfied] > 0)

    return cost

  def satisfied(self):
    return self.unsatisfied_len == 0

  def calculate_possible_times(self):
    self.possible_times = np.zeros((len(self.mids),
                                    len(self.times)),dtype='int_')
    self.possible_times_len = np.zeros(len(self.mids),dtype='int_')
    for mindex in xrange(len(self.mids)):
      allofs = self.allof[mindex,:self.allof_len[mindex]]
      oneofs = self.oneof[mindex,:self.oneof_len[mindex]]
      times = np.where((len(allofs) == 0 or
                        np.all(self.meetings[allofs,:] < 0,axis=0)) &
                       (len(oneofs) == 0 or
                        np.any(self.meetings[oneofs,:] < 0,axis=0)))[0]

      if not len(times) and mindex in self.unsatisfied[:self.unsatisfied_len]:
        raise RequirementException(mindex,self.mids)
      else:
        self.possible_times[mindex,:len(times)] = times
        self.possible_times_len[mindex] = len(times)

    # verify that there are enough times available for each
    # individual that must be in a meeting for them
    # to go to all meetings
    for aindex in xrange(len(self.agents)):
      nmeetings = np.sum(np.any(self.allof == aindex,axis=1))
      if nmeetings > np.sum(self.meetings[aindex,:] != 0):
        raise AvailableTimesException(aindex,self.agents)

  def clear_meetings(self):
    self.cache = {}
    self.meetings[:,:] = np.where(self.meetings == 0,0,-1)
    self.mtimes[:] = -1
    self.oneof_selected[:] = -1
    self.unsatisfied = np.arange(len(self.mids))
    self.unsatisfied_len = len(self.mids)

    self.calculate_possible_times()

    return self

  def sample_update(self,miss_counts=None,mindex=None):
    # randomly select an unsatisfied meeting
    if mindex is None:

      # if there is a meeting with only one option, schedule that meeting.
      unsatisfied = self.unsatisfied[:self.unsatisfied_len]
      one_option = np.where(self.possible_times_len[unsatisfied] == 1)[0]
      if len(one_option):
        unsatisfied_i = one_option[0]
        mindex = self.unsatisfied[unsatisfied_i]
        tindex = self.possible_times[mindex,0]

      # otherwise, schedule a meeting weighted by  how few options it has (fewer
      # -> more likely to pick) and how often it is a meeting whose requirement
      # could not be satisified on a previous scheduling attempt (more misses ->
      # more likely to pick).
      else:
        weights = 1.0/self.possible_times_len
        if miss_counts is not None:
          weights = weights/np.sum(weights) + miss_counts / np.max(miss_counts)

        weights = weights[self.unsatisfied[:self.unsatisfied_len]]
        unsatisfied_i = \
          np.random.choice(self.unsatisfied_len,
                           p=weights.astype('float_')/np.sum(weights))
        mindex = self.unsatisfied[unsatisfied_i]

        # randomly select one of the possible times...
        times = self.possible_times[mindex,:self.possible_times_len[mindex]]
        tindex = np.random.choice(times)
    else:
      unsatisfied_i = \
        np.where(mindex == self.unsatisfied[:self.unsatisfied_len])[0][0]

      # randomly select one of the possible times...
      times = self.possible_times[mindex,:self.possible_times_len[mindex]]
      tindex = np.random.choice(times)

    return self.update_schedule(mindex,tindex,unsatisfied_i)

  def update_schedule(self,mindex,tindex,unsatisfied_i):
    self.cache = {}

    oneofs = self.oneof[mindex,:self.oneof_len[mindex]]
    allofs = self.allof[mindex,:self.allof_len[mindex]]

    # print "Chose time:",self.times[tindex], "for Meeting",self.mids[mindex]

    # schedule the meeting at this time
    self.mtimes[mindex] = tindex
    if len(allofs):
      self.meetings[allofs,tindex] = mindex+1
    if len(oneofs):
      oneof = np.random.choice(oneofs[self.meetings[oneofs,tindex] < 0])
      self.meetings[oneof,tindex] = mindex+1
      self.oneof_selected[mindex] = oneof

    # mark the meeting as satisfied
    if unsatisfied_i < self.unsatisfied_len-1:
      self.unsatisfied[unsatisfied_i] = self.unsatisfied[self.unsatisfied_len-1]
    self.unsatisfied_len -= 1

    # update the available times for the remaining, unscheduled meetings
    for mindexB in xrange(len(self.mids)):
      # if this is an unscheduled meeting that is impossible to schedule  at
      # this time now, remove it
      if self.mtimes[mindexB] < 0:
        ts = self.possible_times[mindexB,:self.possible_times_len[mindexB]]
        if np.any(ts == tindex):
          allofB = self.allof[mindexB,:self.allof_len[mindexB]]
          oneofB = self.oneof[mindexB,:self.oneof_len[mindexB]]

          if (np.any(self.meetings[allofB,tindex] >= 0) or
              (len(oneofB) > 0 and np.all(self.meetings[oneofB,tindex] >= 0))):

            # remove the meeting time
            t = np.where(ts == tindex)[0]
            if len(t):
              if t < self.possible_times_len[mindexB]-1:
                self.possible_times[mindexB,t] = \
                  self.possible_times[mindexB,self.possible_times_len[mindexB]-1]
              self.possible_times_len[mindexB] -= 1

            # if this meeting cannot be satisified, then give up.
            if self.possible_times_len[mindexB] <= 0:
              raise RequirementException(mindexB,self.mids)

    return self

  def sample_remove(self,weights=None):
    self.cache = {}
    # find all satisified meetings
    satisfied = np.where(self.oneof_selected >= 0)[0]

    if not len(satisfied):
      raise RuntimeError("No meetings left to remove")

      # randomly select a satisfied meeting
    if weights is None:
      mindex = np.random.choice(satisfied)
    else:
      weights = weights[satisfied]
      inv_weights = 1.0/weights.astype('float_')
      mindex = np.random.choice(satisfied,p=inv_weights/np.sum(inv_weights))

    allofs = self.allof[mindex,:self.allof_len[mindex]]
    oneofs = self.oneof[mindex,:self.oneof_len[mindex]]
    tindex = self.mtimes[mindex]

    # remove the meeting from the schedule
    self.meetings[allofs,tindex] = -1
    self.meetings[oneofs,tindex] = -1
    self.mtimes[mindex] = -1

    self.unsatisfied[self.unsatisfied_len] = mindex
    self.unsatisfied_len += 1

    # add back any times that have now become possible for other meetings
    for mindex in xrange(len(self.mids)):
      allofs = self.allof[mindex,self.allof_len[mindex]]
      oneofs = self.oneof[mindex,self.oneof_len[mindex]]

      # is this time now valid for this meeting?
      if ((len(allofs) == 0 or np.all(self.meetings[allofs,tindex] <= 0)) and
          np.any(self.meetings[oneofs,tindex] <= 0)):

        self.possible_times[mindex,self.possible_times_len[mindex]] = tindex
        self.possible_times_len[mindex] += 1

    return self
