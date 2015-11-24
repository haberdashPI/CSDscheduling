// Declare app level module which depends on views, and components
angular.module('CSDschedule',[]).
controller('ScheduleController',['$scope', function($scope){
  var schedule = this
  schedule.data = {"meetings": {}, "times": {}}

  var source = new EventSource('/data');
  source.onmessage = function(event){
    $scope.$apply(function(){
      schedule.data = JSON.parse(event.data)
    })
  }
}]);
