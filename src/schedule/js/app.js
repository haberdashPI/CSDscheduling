// Declare app level module which depends on views, and components
app = angular.module('CSDschedule',['datatables'])

app.controller('ScheduleController',
           ['$scope','$filter','$http','$timeout','DTOptionsBuilder','DTColumnDefBuilder',
            function($scope,$filter,$http,$timeout,DTOptionsBuilder,DTColumnBuilder){
  var control = this
  control.dt = {}
  $scope.edit = {mode: {type: "none"}}
  control.schedules = []
  $scope.schedule_index = -1

  // control.options = DTOptionsBuilder.newOptions()
  //   .withOption('paging',false)
  //   .withOption('ordering',false)
  //   .withDisplayLength(30)
  //   .withFixedHeader({bottom: false})
  control.options = DTOptionsBuilder.newOptions()
    .withDOM('ft')
    .withOption('paging',false)
    .withOption('scrollY','40vh')
    .withOption('ordering',false)

  $scope.range = function(n){
    if(n > 0){
      result = new Array(n)
      for(i=0;i<result.length;i++) result[i] = i
      return result
    }else return []
  }

  // control.find_columns = function(){
  //   times = $filter('orderBy')(control.data.valid_times,'-start',true)

  //   defs = times .map(function(item,i){
  //     start_str = $filter('date')(item.start,'h:mm','UTC')
  //     end_str = $filter('date')(item.end,'h:mm','UTC')

  //     return DTColumnDefBuilder.newColumn(i+1).withTitle(start_str+"-"+end_str)
  //   })

  //   return [DTColumnDefBuilder.newColumn(0).withTitle("")].concat(defs)
  // }

  // control.columns = control.find_columns()

  $http.post('/request_data',{newfile: true})
  .then(function(event){
    control.schedule_index = 0
    control.schedules = event.data.schedules

    $scope.schedule = event.data.schedules[0]

    console.log("Loaded data!")
  },function(){
    console.error("Data load failed!")
  })

  control.load_file = function(file){
    console.log("loading...")
    $http.post('/request_data',{file: file})
    .then(function(event){
      if(event.data.nofile)
        alert("No file found!")
      else{
        control.schedules = event.data.schedules
        $scope.schedule = control.schedules[control.schedule_index]
        // $timeout(function(){
        //   control.dt.rerender()
        // },100)
        console.log("Loaded data!")
      }
    })
  }

  control.update_data = function(){
    control.schedules[control.schedule_index] = $scope.schedule
    $http.post('/update_data',{'schedules': control.schedules,
                               'working_file': $scope.working_file}).
    then(function(event){
      if(event.data.ammend &&
         (mid = event.data.ammend.unsatisfiable_meeting)){
        alert("That change makes Meeting "+mid+" impossible to schedule!")
        control.schedules = event.data.schedules
        $scope.schedule = control.schedules[control.schedule_index]
      }else{
        control.schedules = event.data.schedules
        meetings = control.schedules[control.schedule_index].meetings
        angular.forEach(meetings,function(times,agent){
          angular.forEach(times,function(newtime){
            viewtime = control.get_time($scope.schedule.meetings[agent],newtime)
            if(newtime.mid !== viewtime.mid){
              viewtime.mid = newtime.mid
            }
          })
        })
        $scope.schedule.unsatisfied = control.schedules[control.schedule_index].unsatisfied

        console.log("Data updated!")
      }
    },function(){
      console.error("Server failed to update!")
    })
  }

  control.show_schedule = function(index){
    control.schedule_index = index
    $scope.schedule = control.schedules[control.schedule_index]
    $timeout(function(){
      control.dt.rerender()
    },100)
  }

  control.copy_schedule = function(index){
    control.schedules.push(control.schedules[index])
    if(index == control.schedule_index)
      control.show_schedule(control.schedules.length-1)
    control.update_data()
  }

  control.remove_schedule = function(index){
    control.schedules.splice(index,1)
    if(index == control.schedule_index)
      control.show_schedule(Math.min(control.schedules.length-1,index))
    control.update_data()
  }

  control.find_solution = function(index){
    $scope.solve_message = "Awaiting solution..."
    var num_steps = Object.keys($scope.schedule.requirements).length*2
    $http.post('/request_solutions',{'n_solutions': 20, 'take_best': 5,
                                     'max_cycles': num_steps*10*25,
                                     'schedule': $scope.schedule}).
    then(function(event){
      solutions = event.data.schedules
      if(solutions.length > 0){
        $scope.solve_message = ""
        control.schedules = control.schedules.concat(solutions)
        $scope.schedule = control.schedules[control.schedule_index]
        control.update_data()

        alert("Solutions found: placing in schedules "+
              ((control.schedules.length - solutions.length))+
              " - "+
              (control.schedules.length-1))

      }else{
        $scope.solve_message = ""        
        alert("Could not find any solutions in time. Trying again might help...")
      }
    },function(){
      console.error("Server failed to respond!")
    })
  }

  control.add_allof_time = function(mid,time){
    // remove old meeting location (if present)
    control.remove_meeting_time(mid,time,true)

    // add new meeting location
    var requirement = $scope.schedule.requirements[mid]
    angular.forEach(requirement.allof.agents,function(agent){
      var times = $scope.schedule.meetings[agent]
      var t = control.get_time(times,time)
      t.mid = mid
    })

  }

  control.get_time = function(times,time){
    return $.grep(times,function(t){return control.same_time(t,time)})[0]
  }

  control.add_oneof_time = function(mid,agent,time){
    control.add_allof_time(mid,time)

    // remove any old oneof agents
    var requirement = $scope.schedule.requirements[$scope.edit.mode.mid]
    angular.forEach(requirement.oneof.agents,function(agent){
      var times = $scope.schedule.meetings[agent]
      angular.forEach(times,function(t){
        if(t.mid == $scope.edit.mode.mlist) t.mid = -1
      })
    })

    // add the new one
    t = control.get_time($scope.schedule.meetings[agent],time)
    t.mid = $scope.edit.mode.mid
  }

  control.remove_meeting_time = function(mid,time,child){
    angular.forEach($scope.schedule.meetings,function(times){
      angular.forEach(times,function(t){
        if(t.mid == mid) t.mid = -1
      })
    })
    if(!child) control.update_data()
  }

  control.schedule_click = function(agent,time){
    meeting_time = control.get_time($scope.schedule.meetings[agent],time)
    if(meeting_time.mid > 0){
      // select meeting requirements
      $scope.edit.mode = 
        {type: 'meetings', adding: true, mid: meeting_time.mid, mandatory: true}

      // make the requirements visible
      var mlist = angular.element('#meetings')
      var meetingRow = angular.element('#meeting'+meeting_time.mid)
      var scrollTo = mlist.scrollTop() + (meetingRow.offset().top - mlist.offset().top)
      mlist.animate({scrollTop: scrollTo},400)
    }else if($scope.edit.mode.mid){
      if(control.is_valid_allof(agent,time)){
        control.add_allof_time($scope.edit.mode.mid,time)
        control.update_data()
      }else if(control.is_valid_oneof(agent,time)){
        control.add_oneof_time($scope.edit.mode.mid,agent,time)
        control.update_data()
      }
    }else if(time.mid == -1){
      time.mid = 0
      control.update_data()
    }else if(time.mid == 0){
      time.mid = -1
      control.update_data()
    }
    // TODO handle meetings
  }

  control.time_to_string = function(time){
    start_str = $filter('date')(time.start,'h:mm a','UTC')
    end_str = $filter('date')(time.end,'h:mm a','UTC')
    return start_str + "-" + end_str
  }

  control.add_meeting_requirement = function(mid,agent,agent_index,
                                             is_mandatory){
    requirement = $scope.schedule.requirements[mid]
    if(!requirement){
      requirement = {}
      $scope.schedule.requirements[mid] = requirement
      // wait until the page rerenders and then move to the new meeting.
      $timeout(function(){
        var mlist = angular.element('#meetings')
        mlist.scrollTop(mlist[0].scrollHeight)
      })
    }
    if(is_mandatory){
      if(!requirement.allof)
        requirement.allof = {mid: mid, agents: [], type: "allof"}
      requirement.allof.agents.push(agent)
    } 
    else{
      if(!requirement.oneof)
        requirement.oneof = {mid: mid, agents: [], type: "oneof"}
      requirement.oneof.agents.push(agent)
    }

    control.update_data()
  }

  control.remove_agent_requirement = function(agent,type,mid){
    if(confirm("Remove "+agent+"?")){
      requirement = $scope.schedule.requirements[mid]
      i = requirement[type].agents.indexOf(agent)
      if(i >= 0) requirement[type].agents.splice(i,1)

      control.update_data()
    }
  }

  control.remove_meeting = function(mid){
    if(confirm("Remove Meeting "+mid+"?")){
      delete $scope.schedule.requirements[mid]
      angular.forEach($scope.schedule.meetings,function(agent){
        angular.forEach(agent,function(time){
          if(time.mid == mid){
            time.mid == -1
          }
        })
      })

      $scope.edit = {mode: {type: "meetings"}}

      control.update_data()
    }
  }

  control.is_valid_allof_time = function(mid,time){
    var requirement = $scope.schedule.requirements[mid]
    if(!requirement.allof) return false
    return requirement.allof.agents.every(function(agent){
        var meeting = control.get_time($scope.schedule.meetings[agent],time)
        return meeting.mid < 0 || meeting.mid == mid
      })
  }

  control.is_valid_allof = function(agent,time){
    var mode = $scope.edit.mode
    if(mode.mid && $scope.schedule.requirements[mode.mid] &&
       $scope.schedule.requirements[mode.mid].allof){
      var requirement = $scope.schedule.requirements[mode.mid]
      var has_agent = requirement.allof.agents.indexOf(agent) >= 0

      return has_agent && control.is_valid_allof_time(mode.mid,time)
    }else return false
  }

  control.is_valid_oneof = function(agent,time){
    var mode = $scope.edit.mode
    if(mode.mid && $scope.schedule.requirements[mode.mid] &&
       $scope.schedule.requirements[mode.mid].oneof){
      var requirement = $scope.schedule.requirements[mode.mid]
      var has_agent = requirement.oneof.agents.indexOf(agent) >= 0
      var meeting = control.get_time($scope.schedule.meetings[agent],time)

      return has_agent && (meeting.mid < 0 || meeting.mid == mode.mid) &&
        control.is_valid_allof_time(mode.mid,time)
    }
  }

  control.select_requirements = function(mid){
    $scope.edit.mode = 
      {type: 'meetings', adding: true, mid: mid, mandatory: true}

    var requirement = $scope.schedule.requirements[mid]
    var agent = $.grep($scope.schedule.agents,function(agent){
      if(requirement.oneof)
        return requirement.oneof.agents.indexOf(agent) >= 0
      else return requirement.allof.agents.indexOf(agent) >= 0
    })[0]

    var agentRowId = '#agent'+$scope.schedule.agents.indexOf(agent)
    var agentRow = angular.element(agentRowId)
    var dataScroll = angular.element('.dataTables_scrollBody')
    var scrollTo = agentRow.prop('offsetTop') - dataScroll.height()/2
    dataScroll.animate({scrollTop: scrollTo},400)
  }

  // $scope.$watchCollection("schedule.requirements",function(newr,oldr){
  //   if(newr && oldr && Object.keys(newr).length > Object.keys(oldr).length){

  //   }
  // },true)

  control.select_agent = function(agent,index){
    if($scope.edit.mode.type == "meetings" && 
       $scope.edit.mode.adding){
      if(!$scope.edit.mode.mid)
        $scope.edit.mode.mid = 
         Math.max(0,...Object.keys($scope.schedule.requirements))+1
        
      control.add_meeting_requirement($scope.edit.mode.mid,agent,index,
                                      $scope.edit.mode.mandatory)

    }else if($scope.edit.mode.type === "agent" && 
             $scope.edit.mode.index === index){
      $scope.edit.mode = {type: 'none'}

    }else $scope.edit.mode = {type: 'agent', index: index, agent: agent}
  }

  control.new_agent = function(event,name,index){
    if(event.keyCode == 13){
      console.log("Entered!")
      if($scope.schedule.agents.indexOf(name) > 0){
        alert("All names must be unique!")
        return
      }

      $scope.schedule.agents.splice(index,0,name)
      $scope.schedule.meetings[name] = 
        $scope.schedule.times.map(function(time){
          return {
            start: time.start,
            end: time.end,
            mid: -1
          }
        })

      control.update_data()
      new_agent = ""
    }
  }

  control.remove_agent = function(agent){
    if(confirm("This will remove any meetings "+agent+" must be a part of."+
               " Is that OK?")){
      if($scope.edit.mode === "agent" && $scope.edit.mode.agent === agent)
        $scope.edit = {mode: {type: "none"}}

      index = $scope.schedule.agents.indexOf(agent)
      $scope.schedule.agents.splice(index,1)
      delete $scope.schedule.meetings[agent]

      remove_mids = []
      angular.forEach($scope.schedule.requirements,function(reqs,index){
        if(reqs.allof){
          if(reqs.allof.agents.indexOf(agent) >= 0)
            remove_mids.push(index)
        }
        if(reqs.oneof){
          if((ai = reqs.oneof.agents.indexOf(agent)) >= 0)
            reqs.oneof.agents.splice(ai,1)
        }
      })
      angular.forEach(remove_mids,function(i){
        delete $scope.schedule.requirements[i]
      })

      angular.forEach($scope.schedule.meetings,function(times){
        angular.forEach(times,function(t){
          if(remove_mids.indexOf(t.mid) >= 0)
            t.mid = -1
        })
      })

      control.update_data()
    }
  }

  control.rename_agent = function(event,edit_mode,newagent){
    if(event.keyCode == 13){
      edit_mode.agent = newagent
      oldagent = $scope.schedule.agents[edit_mode.index]
      $scope.schedule.agents[edit_mode.index] = newagent
      $scope.schedule.meetings[newagent] = $scope.schedule.meetings[oldagent]
      delete $scope.schedule.meetings[oldagent]
      
      angular.forEach($scope.schedule.requirements,function(reqs){
        angular.forEach(reqs,function(req,type){
          i = req.agents.indexOf(oldagent)
          if(i >= 0) req.agents[i] = newagent
        })
      })

      $scope.is_agent_edit = false
      control.update_data()
    }
  }

  control.reorder_agent = function(edit_mode,offset){
    old = $scope.schedule.agents[edit_mode.index]
    $scope.schedule.agents[edit_mode.index] = 
      $scope.schedule.agents[edit_mode.index+offset]
    $scope.schedule.agents[edit_mode.index+offset] = old
    edit_mode.index += offset

    control.update_data()
  }

  control.parse_time = function(str){
    var d = new Date(Date.UTC(2000,1,1));
     var time = str.match(/(\d+)(?::(\d\d))?\s*(p|a?)/)

    d.setUTCHours(parseInt(time[1]) + (time[3].toLowerCase() == "p" ? 12 : 0))
    d.setUTCMinutes(parseInt(time[2]) || 0)

    // infer am or pm if it is absent, assuming
    // that times past 7pm and times before 7am will not occur.
    if(!time[3]){
      if(d.getUTCHours() >= 19){
        d.setUTCHours(d.getUTCHours() - 12)
      }if(d.getUTCHours() <= 7){
        d.setUTCHours(d.getUTCHours() + 12)
      }
    }

    return d.getTime()
  }

  control.parse_time_range = function(time_range){
    try{
        parts = time_range.split("-")
        if(parts.length != 2){
          alert("You must have one '-' between two times")
          return false
        }
        time_range = {
          start: control.parse_time(parts[0].trim()),
          end: control.parse_time(parts[1].trim())
        }
      }catch(err){
        alert("Could not interpret string as a range of times: \n"+err.message)
        return false
      }

      return time_range
  }

  control.no_duplicate_times = function(time){
    if(control.get_time($scope.schedule.times,time)){
      alert("All times must be unique!")
      return false
    }
    return true
  }

  control.replace_time = function(event,oldtime,newtime){
    if(event.keyCode == 13){
      if(newtime === ""){
        // remove the time if there's no new time
        index = $.grep($scope.schedule.times,function(t){
          control.same_time(t,oldtime)
        })[1]
        $scope.schedule.times.splice(index,1)

        angular.forEach($scope.schedule.meetings,function(meetings){
          index = $.grep(meetings,function(t){
            control.same_time(t,oldtime)
          })[1]
          meetings.splice(index,1)
        })

        control.dt.rerender()
        control.update_data()

        return true
      }

      if(!(newtime = control.parse_time_range(newtime))) return false
      if(!control.same_time(newtime,oldtime) &&
         !control.no_duplicate_times(newtime)) return false

      oldtime.start = newtime.start
      oldtime.end = newtime.end

      angular.forEach($scope.schedule.meetings,function(agent_meetings){
        angular.forEach(agent_meetings,function(meeting){
          if(control.same_time(oldtime,meeting)){
            meeting.start = newtime.start
            meeting.end = newtime.end
          }
        })
      })

      control.dt.rerender()

      control.update_data()
      console.log("Updated!")

      return true
    }
    return false
  }

  control.new_time = function(event,time_range_str){
    if(event.keyCode == 13){
      if(!(time_range = control.parse_time_range(time_range_str))) return
      if(!control.no_duplicate_times(time_range)) return

      $scope.schedule.times.splice(0,0,time_range)
      angular.forEach($scope.schedule.agents,function(agent){
        times = $scope.schedule.meetings[agent]
        times.splice(0,0,{
          start: time_range.start,
          end: time_range.end,
          mid: -1
        })
      })

      // update the model
      control.dt.rerender()
      $scope.added_time = ""
      $scope.adding_time = false

      control.update_data()
      console.log("Updated!")
    }
  }

  // $scope.selection = null
  // $scope.select = function(agent,time){
  //   time_index = control.data.valid_times.findIndex(function(t){
  //     $scope.same_time(time,t)
  //   })

  //   $scope.selection = {agent: agent, time: time, time_index: time_index}
  // }

  // $scope.isSelected = function(agent,time){
  //   if($scope.selection){
  //     turn $scope.selection.agent === agent &&
  //       $scope.same_time($scope.selection.time,time)
  //   }
  //   return false
  // }

  control.same_time = function(time1,time2){
    return time1.start === time2.start &&
      time1.end === time2.end
  }

  // var source = new EventSource('/data');
  // source.onmessage = function(event){
  //   $scope.$apply(function(){
  //     control.data = angular.fromJson(event.data)
  //     control.columns = control.find_columns()
  //   })
  // }
}])
