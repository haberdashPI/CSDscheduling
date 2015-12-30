// Declare app level module which depends on views, and components
app = angular.module('CSDschedule',['datatables'])

app.controller('ScheduleController',
           ['$scope','$filter','$http','$timeout','DTOptionsBuilder','DTColumnDefBuilder',
            function($scope,$filter,$http,$timeout,DTOptionsBuilder,DTColumnBuilder){
  var control = this
  control.dt = {}
  $scope.edit = {mode: {type: "none"}}

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

  $http.get('/request_data')
  .then(function(event){
    $scope.schedule = event.data
    console.log("Loaded data!")
  },function(){
    console.error("Data load failed!")
  })

  control.load_file = function(file){
    console.log("loading...")
    $http.post('/load_file',{file: file})
    .then(function(event){
      if(event.data.nofile)
        alert("No file found!")
      else{
        $scope.schedule = event.data
        control.dt.rerender()
        console.log("Loaded data!")
      }
    })
  }

  control.update_data = function(){
    $http.post('/update_data',{'schedule': $scope.schedule,
                               'working_file': $scope.working_file}).
    then(function(event){
      angular.forEach(event.data.schedule,function(times,agent){
        angular.forEach(times,function(time,index){
          if(time.mid !== $scope.schedule.meetings[agent][index].mid){
            $scope.schedule.meetings[agent][index].mid = mid
          }
        })
      })
      console.log("Data updated!")
    },function(){
      console.error("Server failed to update!")
    })
  }

  control.schedule_click = function(agent,time){
    if(time.mid == -1){
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
    requirement = $scope.schedule.requirements[mid]
    i = requirement[type].agents.indexOf(agent)
    if(i >= 0) requirement[type].agents.splice(i,1)

    control.update_data()
  }

  control.remove_meeting = function(mid){
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
    duplicate = $.grep($scope.schedule.times,function(t){
      control.same_time(t,time)
    })
    if(duplicate.length > 0){
      alert("All times must be unique!")
      return false
    }
    return true
  }

  control.replace_time = function(event,oldtime,newtime){
    if(event.keyCode == 13){
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
        times.splice(index,0,{
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
