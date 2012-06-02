from jazzr.tools import commandline
import sys, os, math, re, csv

books = ['RB1','RB2','RB3','NRB1', 'NRB2', 'NRB3']

def load_file(data):
  index = {}
  reader = csv.reader(open(data, 'rb'))
  # Skip header
  reader.next()

  for row in reader:
    items = {}
    i = 1
    for book in books:
      if row[i] is '':
        items[book] = None
      else:
        items[book] = int(row[i])
      i += 1
    index[row[0]] = items

  for book in books:
    ordered = sorted([(key, index[key][book]) for key in index.keys()], key=lambda x: x[1])
    for i in range(0, len(ordered)):
      (song, page) = ordered[i]
      if not page: continue
      nextpage = page
      if i < len(ordered) - 1:
        nextpage = ordered[i+1][1]
      index[song][book] = (page, page + (nextpage - page - 1))
  return index

def find(index, query):
  results = []
  for item in index.keys():
    if re.search(query, item.lower()):
      results.append(item)
    elif re.search(query, item.lower().replace('\'', '')):
      results.append(item)
  return results

def save(index, bookspath, song, book, path, uninterrupted=False):
  (begin, end) = index[song][book]
  command = "pdftk A={0}{1}.pdf cat {2}-{3} output {4}".format(bookspath, book, str(begin), str(end), path)
  exitstatus = os.system(command)
  if exitstatus:
    print command
    if not uninterrupted:
      if raw_input('Process unsuccesful (exit status {0}), abort? (y/n) '.format(exitstatus)) is 'y':
        exit(0)

# This works if songs are stored as separate files in songpath
def view(song, book, songpath): 
  filename = '{0}-{1}.pdf'.format(song.replace(' ', '_').replace('\'', '\\\''), book)
  os.system('evince {0}{1} &'.format(songpath, filename))

def choose_book(index, results):
  song = results[commandline.menu("Select a song", results)]
  locations = zip(books, index[song])

  bookhits = []
  for book in books:
    if index[song][book]:
      bookhits.append(book)
  book = bookhits[commandline.menu("Select a book", bookhits)]
  return (song, book)

def interactive(datafile, bookspath):
  index = load_file(datafile)
  while True:
    query = raw_input('Say a name! ').lower()
    results = find(index, query)
    if len(results) > 0:
      (song, book) = choose_book(index, results)

      print "What would you like to do?"
      while True:
        choice = commandline.menu("Please select", ["Export pdf", "Continue", "Quit"])
        if choice is 0:
          save(index, bookspath, song, book, '{0}-{1}.pdf'.format(song.replace(' ', '_'), book))
        if choice is 1: break
        if choice is 2: exit(0)

# This was a run-once function  
def parse_file(inf, out):
  infile = open(inf)
  ofile = csv.writer(open(out, 'wb'))
  books = ['RB1','RB2','RB3','NRB1', 'NRB2', 'NRB3']
  offsets = {'RB1':13,'RB2':7,'RB3':7,'NRB1':13, 'NRB2':12, 'NRB3':10}
  infile.next()
  ofile.writerow(['Song'] + books)
  for line in infile:
    name = line[:43].strip()
    pages = {}
    values = []
    for i in range(len(books)):
      left = 43+i*7
      right = 43+i*7+7
      if right >= len(line): right = len(line) - 1
      page = line[left:right].strip()
      m = re.match('S([0-9]+)', page)
      if m:
        page = m.group(1)
      if not page is '':
        values.append(int(page) + offsets[books[i]])
      else:
        values.append(None)

    ofile.writerow([name] + values)

