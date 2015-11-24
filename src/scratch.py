from logging import DEBUG, FileHandler
from schedule.view import app, data_queue
from schedule.parse import parse_file
from pyrsistent import *

s = parse_file('../schedule2015.xlsx')

data_queue.put(s.tojson())
app.logger.setLevel(DEBUG)
app.logger.addHandler(FileHandler('view.log'))
app.run(debug=True)
