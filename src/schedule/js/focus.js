app.directive('focusOn', function($timeout, $parse) {
  return {
    link: function(scope, element, attrs) {
      var model = $parse(attrs.focusOn);
      scope.$watch(model, function(value) {
        if(value === true) { 
          $timeout(function() {
            element[0].focus(); 
          });
        }
      });
    }
  };
});

app.directive('focusOnNot', function($timeout, $parse) {
  return {
    link: function(scope, element, attrs) {
      var model = $parse(attrs.focusOnNot);
      scope.$watch(model, function(value) {
        if(value === false) { 
          $timeout(function() {
            element[0].focus(); 
          });
        }
      });
    }
  };
});