// Declare app level module which depends on views, and components
angular.module('CSDschedule',['datatables']).
controller('ScheduleController',['$scope', function($scope){
  var schedule = this
  schedule.data = {meetings: {}, times: {}, valid_times: {}, agents: []}

  $scope.active_agent = null
  $scope.active_time = null

  $scope.same_time = function(time1,time2){
    return time1.start === time2.start &&
           time1.end === time2.end
  }

  $scope.cell_click = function(agent,time){
    $scope.active_agent = agent;
    $scope.active_time = time;
  }

  var source = new EventSource('/data');
  source.onmessage = function(event){
    $scope.$apply(function(){
      schedule.data = angular.fromJson(event.data)
    })
  }
}])
