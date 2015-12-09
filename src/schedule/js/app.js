// Declare app level module which depends on views, and components
app = angular.module('CSDschedule',['datatables'])

app.controller('ScheduleController',
           ['$scope','$filter','$http','DTOptionsBuilder','DTColumnDefBuilder',
            function($scope,$filter,$http,DTOptionsBuilder,DTColumnBuilder){
  var control = this
  control.dt = {}

  // control.options = DTOptionsBuilder.newOptions()
  //   .withOption('paging',false)
  //   .withOption('ordering',false)
  //   .withDisplayLength(30)
  //   .withFixedHeader({bottom: false})
  control.options = DTOptionsBuilder.newOptions()
    .withDOM('ft')
    .withOption('paging',false)
    .withOption('scrollY','60vh')
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

  control.updateData = function(){
    $http.post('/update_data',$scope.schedule).then(function(event){
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

  control.toggleAvailability = function(agent,time){
    if(time.mid > 0)
      time.mid = -1
    else
      time.mid = 0

    control.updateData()
  }

  control.newAgent = function(event,name,index){
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

      control.updateData()
      new_agent = ""
    }
  }

  control.parseTime = function(str){
    var d = new Date(Date.UTC(2000,1,1));
    var time = str.match(/(\d+)(?::(\d\d))?\s*(p?)/)

    d.setUTCHours(parseInt(time[1]) + (time[3] ? 12 : 0))
    d.setUTCMinutes(parseInt(time[2]) || 0)

    return d.getTime()
  }

  control.newTime = function(event,time,index){
    if(event.keyCode == 13){
      console.log("ENTERED!")
      if(index == -1){
        index = $scope.schedule.times.length
      }
      try{
        parts = time.split("-")
        if(parts.length != 2){
          alert("You must have one '-' between two times")
          return
        }
        time = {
          start: control.parseTime(parts[0].trim()),
          end: control.parseTime(parts[1].trim())
        }
      }catch(err){
        alert("Could not interpret string as a range of times: \n"+err.message)
        return
      }

      duplicate = $.grep($scope.schedule.times,function(t){
        control.same_time(t,time)
      })
      if(duplicate.length > 0){
        alert("All times must be unique!")
        return
      }

      $scope.schedule.times.splice(index,0,time)
      angular.forEach($scope.schedule.agents,function(agent){
        times = $scope.schedule.meetings[agent]
        $scope.schedule.meetings[agent] = times.splice(index,0,{
          start: time.start,
          end: time.end,
          mid: -1
        })
      })

      control.updateData()
      console.log("Updated!")

      // update the model
      control.dt.rerender()
      $scope.new_time = ""      
      $scope.adding_time = false
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
