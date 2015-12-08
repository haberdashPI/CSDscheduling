// Declare app level module which depends on views, and components
angular.module('CSDschedule',['datatables']).
controller('ScheduleController',
           ['$scope','$filter','$http','DTOptionsBuilder','DTColumnDefBuilder',
            function($scope,$filter,$http,DTOptionsBuilder,DTColumnBuilder){
  var schedule = this
  schedule.data = {times: {}, valid_times: [], agents: []}

  // schedule.options = DTOptionsBuilder.newOptions()
  //   .withOption('paging',false)
  //   .withOption('ordering',false)
  //   .withDisplayLength(30)
  //   .withFixedHeader({bottom: false})
  schedule.options = DTOptionsBuilder.newOptions()
    .withDOM('ft')
    .withOption('paging',false)
    .withOption('scrollY','60vh')
    .withOption('ordering',false)

  // schedule.find_columns = function(){
  //   times = $filter('orderBy')(schedule.data.valid_times,'-start',true)

  //   defs = times .map(function(item,i){
  //     start_str = $filter('date')(item.start,'h:mm','UTC')
  //     end_str = $filter('date')(item.end,'h:mm','UTC')

  //     return DTColumnDefBuilder.newColumn(i+1).withTitle(start_str+"-"+end_str)
  //   })

  //   return [DTColumnDefBuilder.newColumn(0).withTitle("")].concat(defs)
  // }

  // schedule.columns = schedule.find_columns()

  $http.get('/request_data')
  .then(function(event){
    schedule.data = event.data
    console.log("Loaded data!")
  },function(){
    console.error("Data load failed!")
  })

  schedule.updateData = function(){
    $http.post('/update_data',scheudle.data).then(function(event.data){
      
      console.log("Data udpated!")
    },function(){
      console.error("Server failed to update!")
    })
  }

  schedule.toggleAvailability = function(agent,time){
    time.available = !time.available
    updateData()
  }

  schedule.newAgent = function(event,name){
    agents.push(name)
    times[name] = valid_times.map(function(range){
      return {
        start: range.start,
        end: range.end,
        available: true
      }})
    updateData()
  }

  // $scope.selection = null
  // $scope.select = function(agent,time){
  //   time_index = schedule.data.valid_times.findIndex(function(t){
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

  $scope.same_time = function(time1,time2){
    return time1.start === time2.start &&
      time1.end === time2.end
  }

  // var source = new EventSource('/data');
  // source.onmessage = function(event){
  //   $scope.$apply(function(){
  //     schedule.data = angular.fromJson(event.data)
  //     schedule.columns = schedule.find_columns()
  //   })
  // }
}])
