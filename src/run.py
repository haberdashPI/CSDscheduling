import time
from logging import DEBUG, FileHandler
from schedule.view import app, show
from schedule.parse import parse_file
import schedule.view as view
from schedule import TimeRange


show(parse_file('../schedule2015.xlsx'))

app.logger.setLevel(DEBUG)
app.logger.addHandler(FileHandler('flask.log'))

try:
  import webview
  import multiprocessing

  p = multiprocessing.Process(target=lambda: app.run(),args=())
  p.start()

  print "Opening view"
  time.sleep(1)
  webview.create_window("CSD Schedule","http://localhost:5000")

  p.join()

except ImportError:
  import webbrowser

  print "Opening browser"
  webbrowser.open("http://localhost:5000")

  app.run(debug=True)
