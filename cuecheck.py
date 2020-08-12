#!/usr/bin/env python3
# coding: utf-8

import sys, os, re
import argparse

class cuecheckError(Exception):
  def __init__(self, filename, message):
    super().__init__(filename, message)
    self.filename = filename
    self.message = message
  def __str__(self):
    return '"' + self.filename + '" ' + self.message
  def __repr__(self):
    return '<cuemodError: filename={0.filename}, message={0.message}>'.format(self)

class cueSyntaxError(object):
  def __init__(self, line_num, line, message):
    self.line_num = line_num
    self.line = line
    self.message = [message]
  def __str__(self):
    s = 'line ' + str(self.line_num) + ': '
    sm = ''
    for i in self.message:
      sm += ' ' * len(s) + i + '\n'
    s += sm.strip() + '\n  -->' + self.line
    return s
  def __eq__(self, other):
    if isinstance(other, cueSyntaxError):
      return self.line_num == other.line_num
  def __lt__(self, other):
    if isinstance(other, cueSyntaxError):
      return self.line_num < other.line_num

class cueSynerrList(object):
  def __init__(self):
    self.errlist = []
  def __len__(self):
    return len(self.errlist)
  def add(self, e):
    if not isinstance(e, cueSyntaxError):
      raise cuecheckError('', 'cueSyntaxError type error.')
    try:
      i = self.errlist.index(e)
    except ValueError:
      self.errlist.append(e)
      self.errlist.sort()
    else:
      self.errlist[i].message.extend(e.message)
  def __str__(self):
    s = ''
    for i in self.errlist:
      s += str(i) + '\n'
    return s

class CMD(object):
  def __init__(self, linenum, key, line, parent, indent):
    self.linenum = linenum
    self.key = key
    self.line = line
    self.parent = parent
    self.indent = indent
    self.children = []
    if parent:
      parent.children.append(self)
  def __getattr__(self, attr):
    if attr in ('file', 'type', 'content'):
      return ''
    if attr in ('number', 'time'):
      return -1
    raise AttributeError("'CMD' object has no attribute '%s'" % attr)
  def __str__(self):
    s = ' ' * self.indent + 'key: ' + str(self.key) + '\n'
    s += ' ' * self.indent + 'line number: ' + str(self.linenum) + '\n'
    s += ' ' * self.indent + 'line: ' + self.line + '\n'
    s += ' ' * self.indent + 'parent: ' + (str(self.parent.key) if self.parent else str(self.parent)) + '\n'
    s += ' ' * self.indent + 'children: ['
    for c in self.children:
      s += c.key + ','
    s = s.strip(',') + ']\n'
    if self.key == 'FILE':
      s += ' ' * self.indent + '*file: ' + self.file + '\n'
    elif self.key == 'TRACK':
      s += ' ' * self.indent + '*number: ' + str(self.number) + '\n'
      s += ' ' * self.indent + '*type: ' + self.type + '\n'
    elif self.key == 'INDEX':
      s += ' ' * self.indent + '*number: ' + str(self.number) + '\n'
      s += ' ' * self.indent + '*time: ' + str(self.time) + '\n'
    elif self.key in ('TITLE', 'PERFORMER', 'SONGWRITER', 'CATALOG', 'ISRC'):
      s += ' ' * self.indent + '*content: ' + self.content + '\n'
    elif self.key in ('PREGAP', 'POSTGAP'):
      s += ' ' * self.indent + '*time: ' + str(self.time) + '\n'
    elif self.key == 'REM':
      s += ' ' * self.indent + '*tag: ' + self.tag + ' -> ' + '*content: ' + self.content + '\n'
    return s
  def tree(self):
    s = str(self)
    for c in self.children:
      s += '\n' + c.tree()
    return s

commands = {
  'CATALOG': {
    'syntax': r'CATALOG (\d{13})$',
    'parents': (None,),
    'multiple': False,
    'children': (None,),
    'position': {
      None: {
        'after': (),
        'before': ('CDTEXTFILE', 'TITLE', 'PERFORMER', 'SONGWRITER', 'FILE')
        }
      },
    'indent': (0,)
    },
  'CDTEXTFILE': {
    'syntax': r'CDTEXTFILE (")?(?(1)[^"]|[^\s|"])+(?(1)")$',
    'parents': (None,),
    'multiple': False,
    'children': (None,),
    'position': {
      None: {
        'after': ('CATALOG',),
        'before': ('TITLE', 'PERFORMER', 'SONGWRITER', 'FILE')
        }
      },
    'indent': (0,)
    },
  'TITLE': {
    'syntax': r'TITLE (")?((?(1)[^"]|[^\s|"])+)(?(1)")$',
    'parents': (None, 'TRACK'),
    'multiple': False,
    'children': (None,),
    'position': {
      None: {
        'after': ('CATALOG', 'CDTEXTFILE'),
        'before': ('FILE',)
        },
      'TRACK': {
        'after': (),
        'before': ('INDEX',)
        }
      },
    'indent': (0,4)
    },
  'PERFORMER': {
    'syntax': r'PERFORMER (")?((?(1)[^"]|[^\s|"])+)(?(1)")$',
    'parents': (None, 'TRACK'),
    'multiple': False,
    'children': (None,),
    'position': {
      None: {
        'after': ('CATALOG', 'CDTEXTFILE'),
        'before': ('FILE',)
        },
      'TRACK': {
        'after': (),
        'before': ('INDEX',)
        }
      },
    'indent': (0,4)
    },
  'SONGWRITER': {
    'syntax': r'SONGWRITER (")?((?(1)[^"]|[^\s|"])+)(?(1)")$',
    'parents': (None, 'TRACK'),
    'multiple': False,
    'children': (None,),
    'position': {
      None: {
        'after': ('CATALOG', 'CDTEXTFILE'),
        'before': ('FILE',)
        },
      'TRACK': {
        'after': (),
        'before': ('INDEX',)
        }
      },
    'indent': (0,4)
    },
  'FILE': {
    'syntax': r'FILE (")?((?(1)[^"]|[^\s|"])+)(?(1)") (BINARY|MOTOROLA|AIFF|WAVE|MP3)$',
    'parents': (None,),
    'multiple': True,
    'children': ('TRACK',),
    'position': {
      None: {
        'after': ('CATALOG','CDTEXTFILE'),
        'before': ()
        }
      },
    'indent': (0,)
    },
  'TRACK': {
    'syntax': r'TRACK (\d\d) (AUDIO|CDG|MODE1/2048|MODE1/2352|MODE2/2048|MODE2/2324|MODE2/2336|MODE2/2352|CDI/2336|CDI/2352)$',
    'parents': ('FILE',),
    'multiple': True,
    'children': ('FLAGS', 'ISRC', 'TITLE', 'PERFORMER', 'SONGWRITER', 'PREGAP', 'INDEX', 'POSTGAP'),
    'position': {
      'FILE': {
        'after': (),
        'before': ()
        }
      },
    'indent': (2,)
    },
  'FLAGS': {
    'syntax': r'FLAGS( (DCP|4CH|PRE|SCMS))+$',
    'parents': ('TRACK',),
    'multiple': False,
    'children': (None,),
    'position': {
      'TRACK': {
        'after': (),
        'before': ('INDEX',)
        }
      },
    'indent': (4,)
    },
  'ISRC': {
    'syntax': r'ISRC ([0-9A-Z]{5}[0-9]{7})$',
    'parents': ('TRACK',),
    'multiple': False,
    'children': (None,),
    'position': {
      'TRACK': {
        'after': (),
        'before': ('INDEX',)
        }
      },
    'indent': (4,)
    },
  'PREGAP': {
    'syntax': r'PREGAP (\d\d):(\d\d):(\d\d)$',
    'parents': ('TRACK',),
    'multiple': False,
    'children': (None,),
    'position': {
      'TRACK': {
        'after': (),
        'before': ('INDEX',)
        }
      },
    'indent': (4,)
    },
  'INDEX': {
    'syntax': r'INDEX (\d\d) (\d\d):(\d\d):(\d\d)$',
    'parents': ('TRACK',),
    'multiple': True,
    'children': (None,),
    'position': {
      'TRACK': {
        'after': ('FLAGS', 'ISRC', 'TITLE', 'PERFORMER', 'SONGWRITER', 'PREGAP'),
        'before': ('POSTGAP',)
        }
      },
    'indent': (4,)
    },
  'POSTGAP': {
    'syntax': r'POSTGAP (\d\d):(\d\d):(\d\d)$',
    'parents': ('TRACK',),
    'multiple': False,
    'children': (None,),
    'position': {
      'TRACK': {
        'after': ('INDEX',),
        'before': ()
        }
      },
    'indent': (4,)
    },
  'REM': {
    'syntax': r'REM .+$',
    'parents': (None,),
    'multiple': True,
    'children': (None,),
    'position': {
      None: {
        'after': (),
        'before': ()
        }
      },
    'indent': (0,)
    }
}

def cuecheck(filename):
  # 检查文件扩展名是否 .cue，文件是否存在，否则 raise
  if os.path.splitext(filename)[1] != '.cue':
    raise cuecheckError(filename, 'is not cue.')
  if not os.path.isfile(filename):
    raise cuecheckError(filename, 'is not exists.')
  
  errorlist = cueSynerrList()
  warnlist = cueSynerrList()
  # 文件读入列表 d
  with open(filename) as f:
    try:
      d = f.read().splitlines()
    except UnicodeDecodeError:
      raise cuecheckError(filename, 'Decode Error')
    if d[0].startswith('\ufeff'):
      d[0] = d[0][1:]

  def getSpace(line):
    snum = 0
    for c in line:
      if c == ' ':
        snum += 1
      else:
        break
    return snum
  def checkCmdSyntax(cmd):
    if cmd.key:
      m = re.match(' ' * cmd.indent + commands[cmd.key]['syntax'], cmd.line)
      if m:
        if cmd.key in ('TITLE', 'PERFORMER', 'SONGWRITER'):
          if len(m.group(2)) > 80:
            warnlist.add(cueSyntaxError(cmd.linenum, cmd.line, cmd.key + ' should not contain more than 80 characters'))
          cmd.content = ' '.join(cmd.line.split()[1:]).replace('"', '')
        elif cmd.key in ('CATALOG', 'ISRC'):
          cmd.content = m.group(1)
        elif cmd.key == 'FILE':
          if not os.path.isfile(os.path.join(os.path.split(filename)[0], m.group(2))):
            errorlist.add(cueSyntaxError(cmd.linenum, cmd.line, m.group(2) + ' FILE not found'))
          cmd.file = m.group(2)
        elif cmd.key == 'TRACK':
          cmd.number = int(m.group(1))
          cmd.type = m.group(2)
        elif cmd.key in ('PREGAP', 'POSTGAP'):
          if int(m.group(2)) >= 60 or int(m.group(3)) >= 75:
            errorlist.add(cueSyntaxError(cmd.linenum, cmd.line, 'time error (second >= 60 or frame >= 75)'))
          cmd.time = int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3)) / 75
        elif cmd.key == 'INDEX':
          if int(m.group(3)) >= 60 or int(m.group(4)) >= 75:
            errorlist.add(cueSyntaxError(cmd.linenum, cmd.line, 'time error (second >= 60 or frame >= 75)'))
          cmd.number = int(m.group(1))
          cmd.time = int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 75
        elif cmd.key == 'REM':
          ss = cmd.line.split()
          if len(ss) >= 3 and ss[1].isupper():
            cmd.tag = ss[1]
            cmd.content = ' '.join(ss[2:]).replace('"', '')
          else:
            cmd.tag = ''
            cmd.content = cmd.line[4:]
      else:
        errorlist.add(cueSyntaxError(cmd.linenum, cmd.line, 'command syntax error'))
    for c in cmd.children:
      checkCmdSyntax(c)
  def checkCmdChildren(cmd):
    def findChildCmd(cmd, key):
      found = False
      for c in cmd.children:
        if c.key == key:
          found = True
          break
      return found
    for c in cmd.children:
      if cmd.key and not c.key in commands[cmd.key]['children']:
        errorlist.add(cueSyntaxError(cmd.linenum, cmd.line, 'have error child ' + c.key))
      if cmd.key == 'FILE':
        if not findChildCmd(cmd, 'TRACK'):
          errorlist.add(cueSyntaxError(cmd.linenum, cmd.line, 'FILE not have TRACK'))
      elif cmd.key == 'TRACK':
        if not findChildCmd(cmd, 'INDEX'):
          errorlist.add(cueSyntaxError(cmd.linenum, cmd.line, 'TRACK not have INDEX'))
        if not findChildCmd(cmd, 'TITLE'):
          warnlist.add(cueSyntaxError(cmd.linenum, cmd.line, 'TRACK not have TITLE'))
      checkCmdChildren(c)
  def checkCmdOrder(cmd):
    if cmd.key and commands[cmd.key]['position'][cmd.parent.key]['after']:
      me = False
      for c in cmd.parent.children:
        if me and c.key in commands[cmd.key]['position'][cmd.parent.key]['after']:
          errorlist.add(cueSyntaxError(cmd.linenum, cmd.line, 'command order error'))
        if c == cmd:
          me = True
    if cmd.key and commands[cmd.key]['position'][cmd.parent.key]['before']:
      for c in cmd.parent.children:
        if c.key in commands[cmd.key]['position'][cmd.parent.key]['before']:
          errorlist.add(cueSyntaxError(cmd.linenum, cmd.line, 'command order error'))
        if c == cmd:
          break
    for c in cmd.children:
      checkCmdOrder(c)
  def checkCmdMul(cmd):
    if cmd.key and not commands[cmd.key]['multiple']:
      mul = 0
      for c in cmd.parent.children:
        if c.key == cmd.key:
          mul += 1
          if mul > 1:
            errorlist.add(cueSyntaxError(cmd.linenum, cmd.line, 'multiple command error'))
            break
    for c in cmd.children:
      checkCmdMul(c)

  root = CMD(0, None, os.path.realpath(filename), None, 0)
  current = [root, None, None, None]
  #print(d)
  for i in range(len(d)):
    s = re.sub(r'\s+', ' ', d[i]).strip()
    if s == '':
      errorlist.add(cueSyntaxError(i+1, d[i], 'is blank'))
      continue
    ss = s.split()
    if not ss[0].isupper():
      errorlist.add(cueSyntaxError(i+1, d[i], 'command not is capital'))
    ss[0] = ss[0].upper()
    if not ss[0] in commands.keys():
      errorlist.add(cueSyntaxError(i+1, d[i], 'command not found'))
      continue
    indent = getSpace(d[i])
    if not indent in commands[ss[0]]['indent']:
      errorlist.add(cueSyntaxError(i+1, d[i], 'indent error'))
      if len(commands[ss[0]]['indent']) == 1:
        indent = commands[ss[0]]['indent'][0]
      else:
        indent = commands[ss[0]]['indent'][1]
    if current[indent//2]:
      c = CMD(i+1, ss[0], d[i], current[indent//2], indent)
      if c.key == 'FILE':
        current[1] = c
      elif c.key == 'TRACK':
        current[2] = c
    else:
      raise cuecheckError(filename, str(cueSyntaxError(i+1, d[i], 'parent error')))

  #print(root)
  checkCmdSyntax(root)
  checkCmdChildren(root)
  checkCmdMul(root)
  checkCmdOrder(root)
  
  def getCmds(cmd, key):
    if cmd.key == key:
      yield cmd
    for c in cmd.children:
      yield from getCmds(c, key)
  
  tracklist = [x for x in getCmds(root, 'TRACK')]
  if tracklist and tracklist[0].number != 1:
    warnlist.add(cueSyntaxError(tracklist[0].linenum, tracklist[0].line, 'first TRACK number not is 1'))
  for i in range(len(tracklist) - 1):
    if tracklist[i].number + 1 != tracklist[i+1].number:
      errorlist.add(cueSyntaxError(tracklist[i].linenum, tracklist[i].line, 'TRACK number error, ' + str(tracklist[i].number) + ' -> ' + str(tracklist[i+1].number)))
  
  for c in getCmds(root, 'FILE'):
    findex  = [x for x in getCmds(c, 'INDEX')]
    if findex and findex[0].time != 0:
      errorlist.add(cueSyntaxError(findex[0].linenum, findex[0].line, 'first INDEX time not is 0 of FILE'))
    for i in range(len(findex) - 1):
      if findex[i].time >= findex[i+1].time:
        errorlist.add(cueSyntaxError(findex[i].linenum, findex[i].line, 'INDEX time error, ' + str(findex[i].time) + ' >= ' + str(findex[i+1].time)))
  
  for c in tracklist:
    tindex = [x for x in getCmds(c, 'INDEX')]
    if tindex and not (tindex[0].number == 0 or tindex[0].number == 1):
      errorlist.add(cueSyntaxError(tindex[0].linenum, tindex[0].line, 'first INDEX number not is 0 or 1 of TRACK'))
    for i in range(len(tindex) - 1):
      if tindex[i].number + 1 != tindex[i+1].number:
        errorlist.add(cueSyntaxError(tindex[i].linenum, tindex[i].line, 'INDEX number error, ' + str(tindex[i].number) + ' -> ' + str(tindex[i+1].number)))

  return errorlist, warnlist, root

if __name__ == '__main__':
  parse = argparse.ArgumentParser(description='check cue file and print error list')
  parse.add_argument('filename', nargs='+', help='cue file name')
  parse.add_argument('-p', '--print', help='print cue meta info', action='store_true')
  parse.add_argument('-w', '--warn', help='print warn list', action='store_true')
  args = parse.parse_args()

  for arg in args.filename:
    try:
      err, warn, root = cuecheck(arg)
      if err:
        print('ERROR:', arg)
        print(err)
      if args.warn and warn:
        print('WARN:', arg)
        print(warn)
      if args.print and root:
        print(root.tree())
    except cuecheckError as e:
      print(e, file=sys.stderr)
      continue
