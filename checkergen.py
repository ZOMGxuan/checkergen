#! /usr/bin/env python

import os
import sys
import copy
import textwrap
import readline
import argparse
import cmd
import shlex
import threading
import math
from decimal import *

import pygame
from pygame.locals import *

CKG_FMT = 'ckg'
DEFAULT_NAME = 'untitled'
DEFAULT_FPS = 60
DEFAULT_RES = 800, 600
DEFAULT_BG = Color(127, 127, 127)
EXPORT_FMTS = ['bmp', 'tga', 'jpg', 'png']
DEFAULT_EXPORT_FMT = 'png'
MAX_EXPORT_FRAMES = 10000

def gcd(a, b):
    """Return greatest common divisor using Euclid's Algorithm."""
    while b > 0:      
        a, b = b, a % b
    return a

def lcm(a, b):
    """Return lowest common multiple."""
    return a * b // gcd(a, b)

def numdigits(x):
    """Returns number of digits in a decimal integer."""
    if x == 0:
        return 1
    elif x < 0:
        x = -x
    return int(math.log(x, 10)) + 1

def public_dir(obj):
    """Returns all 'public' attributes of an object"""
    names = dir(obj)
    for name in names[:]:
        if name[0] == '_' or name[-1] == '_':
            names.remove(name)
    return names

def yn_parse(s):
    if s in ['y', 'Y', 'yes', 'YES', 'Yes']:
        return True
    elif s in ['n', 'N', 'no', 'NO', 'No']:
        return False
    else:
        msg = "only 'y','n' or variants accepted"
        raise TypeError(msg)

def col_cast(s, sep=','):
    """Tries to cast a string to a Color"""
    try:
        c = Color(s)
    except ValueError:
        c = Color(*[int(x) for x in s.split(sep)])
    return c                        

def store_tuple(nargs, sep, typecast=None, castargs=[]):
    """Retuns argparse action that stores a tuple."""
    class TupleAction(argparse.Action):
        def __call__(self, parser, args, values, option_string=None):
            vallist = values.split(sep)
            if len(vallist) != nargs:
                msg = ("argument '{f}' should be a list of " + 
                       "{nargs} values separated by '{sep}'").\
                       format(f=self.dest,nargs=nargs,sep=sep)
                raise argparse.ArgumentTypeError(msg)
            if typecast != None:
                for n, val in enumerate(vallist):
                    try:
                        val = typecast(*([val] + castargs))
                        vallist[n] = val
                    except (ValueError, TypeError, InvalidOperation):
                        msg = ("element '{val}' of argument '{f}' " +
                               "is of the wrong type").\
                               format(val=vallist[n],f=self.dest)
                        raise argparse.ArgumentTypeError(msg)
            setattr(args, self.dest, tuple(vallist))
    return TupleAction

class CkgProj:
    
    def __init__(self, name=DEFAULT_NAME, fps=DEFAULT_FPS, res=DEFAULT_RES, 
                 bg=DEFAULT_BG, export_fmt=DEFAULT_EXPORT_FMT, path=None):
        if path != None:
            self.load(path)
            return
        self.name = str(name)
        self.fps = Decimal(str(fps))
        self.res = tuple([int(d) for d in res])
        self.bg = bg
        self.bg.set_length(3)
        if export_fmt in EXPORT_FMTS:
            self.export_fmt = export_fmt
        else:
            msg = 'image format not recognized or supported'
            raise TypeError(msg)
        self.boards = []
        self.dirty = True

    def load(self, path):
        # TODO: Extension checking
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.dirty = False        

    def save(self, path):
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.dirty = False
        
class CheckerBoard:

    locations = {'topleft': (1, 1), 'topright': (-1, 1),
                 'btmleft': (1, -1), 'btmright': (-1, -1),
                 'topcenter': (0, 1), 'btmcenter': (0, -1),
                 'centerleft': (1, 0), 'centerright': (-1, 0),
                 'center': (0, 0)}

    def __init__(self, dims, init_unit, end_unit, position, origin, 
                 cols, freq, phase=0):
        self.dims = tuple([int(x) for x in dims])
        self.init_unit = tuple([Decimal(str(x)) for x in init_unit])
        self.end_unit = tuple([Decimal(str(x)) for x in end_unit])
        self.position = tuple([Decimal(str(x)) for x in position])
        if origin in CheckerBoard.locations and type(origin) == str:
            self.origin = origin
        else:
            raise TypeError
        self.cols = tuple(cols)
        self.freq = Decimal(str(freq))
        self.phase = Decimal(str(phase))
        self.cur_phase = self.phase
        self.unit_grad = tuple([(2 if (flag == 0) else 1) * 
                                (y2 - y1) / dx for y1, y2, dx, flag in 
                                zip(self.init_unit, self.end_unit, self.dims,
                                    CheckerBoard.locations[self.origin])])

    def edit(self, attr, val):
        setattr(self, attr, val)
        if attr in ['dims','init_unit','end_unit','origin']:
            self.unit_grad = tuple([(2 if (flag == 0) else 1) * 
                                    (y2 - y1) / dx for y1, y2, dx, flag in 
                                    zip(self.init_unit, self.end_unit, 
                                        self.dims, 
                                        CheckerBoard.locations[self.origin])])

    # TODO: Compute draw model for quicker drawing (IMPORTANT!)

    def draw(self, Surface, position=None):
        Surface.lock()
        if position == None:
            position = self.position
        else:
            position = tuple([Decimal(str(x)) for x in position])
        # Set initial values
        init_unit = [c + m/2 for c, m in zip(self.init_unit, self.unit_grad)]
        init_pos = list(position)
        for n, v in enumerate(CheckerBoard.locations[self.origin]):
            if v == 0:
                init_unit[n] = self.end_unit[n] - (self.unit_grad[n] / 2)
                init_pos[n] -= ((self.init_unit[n] + self.end_unit[n]) / 2 *
                                self.dims[n] / Decimal(2))
        cur_unit = list(init_unit)
        cur_unit_pos = list(init_pos)
        # Draw unit cells in nested for loop
        for j in range(self.dims[1]):
            for i in range(self.dims[0]):
                cur_unit_rect = cur_unit_pos + cur_unit
                # Ensure unit cells are drawn in the right place
                for n, v in enumerate(CheckerBoard.locations[self.origin]):
                    if v < 0:
                        cur_unit_rect[n] -= cur_unit[n]                
                cur_unit_rect = [int(round(x)) for x in cur_unit_rect]
                if 180 <= self.cur_phase < 360:
                    cur_cols = list(reversed(self.cols)) 
                else:
                    cur_cols = list(self.cols)
                Surface.fill(cur_cols[(i + j) % 2], tuple(cur_unit_rect))
                # Increase x values
                if CheckerBoard.locations[self.origin][0] == 0:
                    cur_unit_pos[0] += cur_unit[0]
                    if Decimal(i + 1) < (self.dims[0] / Decimal(2)):
                        cur_unit[0] -= self.unit_grad[0]
                    elif Decimal(i + 1) > (self.dims[0] / Decimal(2)):
                        cur_unit[0] += self.unit_grad[0]
                    else:
                        pass
                else:
                    cur_unit_pos[0] += CheckerBoard.locations[self.origin][0]*\
                                       cur_unit[0]
                    cur_unit[0] += self.unit_grad[0]
            # Reset x values
            cur_unit_pos[0] = init_pos[0]
            cur_unit[0] = init_unit[0]
            # Increase y values
            if CheckerBoard.locations[self.origin][1] == 0:
                cur_unit_pos[1] += cur_unit[1]
                if Decimal(j + 1) < (self.dims[1] / Decimal(2)):
                    cur_unit[1] -= self.unit_grad[1]
                elif Decimal(j + 1) > (self.dims[1] / Decimal(2)):
                    cur_unit[1] += self.unit_grad[1]
                else:
                    pass
            else:
                cur_unit_pos[1] += CheckerBoard.locations[self.origin][1]*\
                                   cur_unit[1]
                cur_unit[1] += self.unit_grad[1]
        Surface.unlock()

    def reset(self, cur_phase=None):
        if cur_phase == None:
            cur_phase = self.phase
        self.cur_phase = cur_phase

    def anim(self, Surface, position=None, fps=DEFAULT_FPS):
        self.draw(Surface, position)
        if self.freq != 0:
            fpp = fps / self.freq
            self.cur_phase += 360 / fpp
            if self.cur_phase >= 360:
                self.cur_phase -= 360

def display_anim(proj, fullscreen=False):
    pygame.display.init()
    if fullscreen:
        screen = pygame.display.set_mode(proj.res,
                                         FULLSCREEN | HWSURFACE | DOUBLEBUF)
    else:
        screen = pygame.display.set_mode(proj.res)
    screen.fill(proj.bg)
    pygame.display.set_caption('checkergen')    
    clock = pygame.time.Clock()

    for board in proj.boards:
        board.reset()

    while True:
        clock.tick(proj.fps)
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.display.quit()
                return
            if event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    pygame.display.quit()
                    return                
        screen.lock()
        for board in proj.boards:
            board.anim(screen, fps=proj.fps)
        screen.unlock()
        pygame.display.flip()
        pygame.time.wait(0)

def export_anim(proj, export_dir, export_fmt=None, folder=True, cmd_mode=True):
    if not os.path.isdir(export_dir):
        if cmd_mode:
            print "error: export path is not a directory"
        return
    if cmd_mode:
        print "Exporting..."
    if export_fmt == None:
        export_fmt = proj.export_fmt
    pygame.display.init()
    screen = pygame.Surface(proj.res)
    screen.fill(proj.bg)
    fpps = [proj.fps / board.freq for board in proj.boards if board.freq != 0]
    frames = reduce(lcm, fpps)
    count = 0

    if frames > MAX_EXPORT_FRAMES:
        if not cmd_mode:
            pygame.display.quit()
            return
        else:
            print "More than", MAX_EXPORT_FRAMES, "are going to be exported."
            print "Are you sure you want to continue? (y/n)"
            if not yn_parser(raw_input()):
                print "Export cancelled."
                pygame.display.quit()
                return
            
    if folder:
        export_dir = os.path.join(export_dir, proj.name)
        if not os.path.isdir(export_dir):
            os.mkdir(export_dir)

    for board in proj.boards:
        board.reset()

    while count < frames:
        screen.lock()
        for board in proj.boards:
            board.anim(screen, fps=proj.fps)
        screen.unlock()
        savepath = os.path.join(export_dir, 
                                '{0}{2}.{1}'.
                                format(proj.name, export_fmt,
                                       repr(count).zfill(numdigits(frames-1))))
        pygame.image.save(screen, savepath)
        count += 1
    if cmd_mode:
        print "Export done."
        pygame.display.quit()

class CmdParser(argparse.ArgumentParser):
    def error(self, message):
        raise SyntaxError(message)
        
class CkgCmd(cmd.Cmd):

    def save_check(self, msg=None):
        """Checks and prompts the user to save if necessary."""
        if self.cur_proj == None:
            return
        if not self.cur_proj.dirty:
            return
        if msg == None:
            msg = 'Would you like to save the current project first? (y/n)'
        print msg
        while True:
            try:
                if yn_parse(raw_input()):
                    self.do_save('')
                break
            except TypeError:
                print str(sys.exc_info()[1])
            except EOFError:
                return True

    def do_new(self, line):
        """Creates new project with given name (can contain whitespace)."""
        name = line.strip().strip('"\'')
        if len(name) == 0:
            name = 'untitled'
        if self.save_check():
            return
        self.cur_proj = CkgProj(name=name)
        print 'project \'{0}\' created'.format(self.cur_proj.name)

    def do_open(self, line):
        """Open specified project file."""
        path = line.strip().strip('"\'') 
        if len(path) == 0:
            print 'error: no path specified'
            return
        if not os.path.isfile(path):
            print 'error: path specified is not a file'
            return
        if self.save_check():
            return
        self.cur_proj = CkgProj(path=path)
        os.chdir(os.path.dirname(os.path.abspath(path)))
        print 'project \'{0}\' loaded'.format(self.cur_proj.name)

    def do_close(self, line):
        """Prompts the user to save, then closes current project."""
        if self.cur_proj == None:
            print 'no project to close'
            return
        if self.save_check():
            return
        self.cur_proj = None
        print 'project closed'

    def do_save(self, line):
        """Saves the current project to the specified path."""
        if self.cur_proj == None:
            print 'no project to save'
            return
        path = line.strip().strip('"\'') 
        if len(path) == 0:
            path = os.getcwd()
        path = os.path.abspath(path)
        if os.path.isdir(path):
            path = os.path.join(path, '.'.join([self.cur_proj.name, CKG_FMT]))
        elif os.path.isdir(os.path.dirname(path)):
            if path[-4:] != ('.' + CKG_FMT):
                print 'error: specified filepath lacks \'.{0}\' extension'.\
                      format(CKG_FMT)
                return
        else:
            print 'error: specified directory does not exist'
            return
        self.cur_proj.save(path)
        print 'project saved to "{0}"'.format(path)

    set_parser = CmdParser(add_help=False, prog='set',
                          description='''Sets various project settings.''')
    set_parser.add_argument('--name', help='''project name, always the same as
                                              the filename without
                                              the extension''')
    set_parser.add_argument('--fps', type=Decimal,
                            help='''number of animation frames
                                    rendered per second''')
    set_parser.add_argument('--res', action=store_tuple(2, ',', int),
                            help='animation canvas size/resolution in pixels',
                            metavar='WIDTH,HEIGHT')
    set_parser.add_argument('--bg', metavar='COLOR', type=col_cast,
                            help='''background color of the canvas
                                    (color format: R,G,B or name, 
                                    component range from 0-255)''')
    set_parser.add_argument('--fmt', dest='export_fmt', choices=EXPORT_FMTS,
                            help='''image format for animation
                                    to be exported as''')

    def help_set(self):
        CkgCmd.set_parser.print_help()

    def do_set(self, line):
        if self.cur_proj == None:
            print 'no project open, automatically creating project...'
            self.do_new('')
        try:
            args = CkgCmd.set_parser.parse_args(shlex.split(line))
        except (SyntaxError, InvalidOperation,
                argparse.ArgumentError, argparse.ArgumentTypeError):
            print "error:", str(sys.exc_info()[1])
            if sys.exc_info()[0] in (SyntaxError, argparse.ArgumentError):
                CkgCmd.set_parser.print_usage()
            return
        names = public_dir(args)
        noflags = True
        for name in names:
            val = getattr(args, name)
            if val != None:
                setattr(self.cur_proj, name, val)
                noflags = False
        if noflags:
            print "no options specified, please specify at least one"
            CkgCmd.set_parser.print_usage()
        else:
            self.cur_proj.dirty = True

    mk_parser = CmdParser(add_help=False, prog='mk',
                          description='''Makes a new checkerboard with the 
                                         given parameters.''')
    mk_parser.add_argument('dims', action=store_tuple(2, ',', Decimal),
                           help='''width,height of checkerboard in no. of 
                                   unit cells''')
    mk_parser.add_argument('init_unit', action=store_tuple(2, ',', Decimal),
                           help='width,height of initial unit cell in pixels')
    mk_parser.add_argument('end_unit', action=store_tuple(2, ',', Decimal),
                           help='width,height of final unit cell in pixels')
    mk_parser.add_argument('position', action=store_tuple(2, ',', Decimal),
                           help='x,y position of checkerboard in pixels')
    mk_parser.add_argument('origin', choices=CheckerBoard.locations,
                           help='''location of origin point of checkerboard
                                   (choices: %(choices)s)''',
                           metavar='origin')
    mk_parser.add_argument('cols', action=store_tuple(2, ',', col_cast, [';']),
                           help='''color1,color2 of the checkerboard
                                   (color format: R;G;B or name, 
                                   component range from 0-255)''')
    mk_parser.add_argument('freq', type=Decimal,
                           help='frequency of color reversal in Hz')
    mk_parser.add_argument('phase', type=Decimal, nargs='?', default='0',
                           help='initial phase of animation in degrees')

    def help_mk(self):
        CkgCmd.mk_parser.print_help()

    def do_mk(self, line):
        """Makes a checkerboard with the given parameters."""
        if self.cur_proj == None:
            print 'no project open, automatically creating project...'
            self.do_new('')
        try:
            args = CkgCmd.mk_parser.parse_args(shlex.split(line))
        except (SyntaxError, InvalidOperation,
                argparse.ArgumentError, argparse.ArgumentTypeError):
            print "error:", str(sys.exc_info()[1])
            if sys.exc_info()[0] in (SyntaxError, argparse.ArgumentError):
                CkgCmd.mk_parser.print_usage()
            return
        newboard = CheckerBoard(dims=args.dims,
                                init_unit=args.init_unit,
                                end_unit=args.end_unit,
                                position=args.position,
                                origin=args.origin,
                                cols=args.cols,
                                freq=args.freq,
                                phase=args.phase)
        self.cur_proj.boards.append(newboard)
        self.cur_proj.dirty = True
        print "checkerboard", len(self.cur_proj.boards)-1, "added"

    ed_parser = CmdParser(add_help=False, prog='ed',
                          description='''Edits attributes of checkerboards
                                         specified by ids.''')
    ed_parser.add_argument('idlist', nargs='+', metavar='id', type=int,
                           help='ids of checkerboards to be edited')
    ed_parser.add_argument('--dims', action=store_tuple(2, ',', Decimal),
                           help='checkerboard dimensions in unit cells',
                           metavar='WIDTH,HEIGHT')
    ed_parser.add_argument('--init_unit', action=store_tuple(2, ',', Decimal),
                           help='initial unit cell dimensions in pixels',
                           metavar='WIDTH,HEIGHT')
    ed_parser.add_argument('--end_unit', action=store_tuple(2, ',', Decimal),
                           help='final unit cell dimensions in pixels',
                           metavar='WIDTH,HEIGHT')
    ed_parser.add_argument('--position', action=store_tuple(2, ',', Decimal),
                           help='position of checkerboard in pixels',
                           metavar='X,Y')
    ed_parser.add_argument('--origin', choices=CheckerBoard.locations,
                           help='''location of origin point of checkerboard
                                   (choices: %(choices)s)''',
                           metavar='LOCATION')
    ed_parser.add_argument('--cols', metavar='COLOR1,COLOR2',
                           action=store_tuple(2, ',', col_cast, [';']),
                           help='''checkerboard colors (color format:
                                   R;G;B or name, component range 
                                   from 0-255)''')
    ed_parser.add_argument('--freq', type=Decimal,
                           help='frequency of color reversal in Hz')
    ed_parser.add_argument('--phase', type=Decimal,
                           help='initial phase of animation in degrees')

    def help_ed(self):
        CkgCmd.ed_parser.print_help()

    def do_ed(self, line):
        """Edits attributes of checkerboards specified by ids."""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = CkgCmd.ed_parser.parse_args(shlex.split(line))
        except (SyntaxError, InvalidOperation,
                argparse.ArgumentError, argparse.ArgumentTypeError):
            print "error:", str(sys.exc_info()[1])
            if sys.exc_info()[0] in (SyntaxError, argparse.ArgumentError):
                CkgCmd.ed_parser.print_usage()
            return
        for x in args.idlist[:]:
            if x >= len(self.cur_proj.boards) or x < 0:
                args.idlist.remove(x)
                print "checkerboard", x, "does not exist"
        if args.idlist == []:
            return
        names = public_dir(args)
        names.remove('idlist')
        noflags = True
        for name in names:
            val = getattr(args, name)
            if val != None:
                for x in args.idlist:
                    self.cur_proj.boards[x].edit(name, val)
                noflags = False
        if noflags:
            print "no options specified, please specify at least one"
            CkgCmd.ed_parser.print_usage()
        else:
            self.cur_proj.dirty = True

    rm_parser = CmdParser(add_help=False, prog='rm',
                          description='''Removes checkerboards specified
                                         by ids.''')
    rm_parser.add_argument('idlist', nargs='*', metavar='id', type=int,
                           help='ids of checkerboards to be removed')
    rm_parser.add_argument('-a', '--all', action='store_true',
                           help='remove all checkerboards')

    def help_rm(self):
        CkgCmd.rm_parser.print_help()

    def do_rm(self, line):
        """Removes checkerboards specified by ids"""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = CkgCmd.rm_parser.parse_args(shlex.split(line))
        except (SyntaxError, InvalidOperation,
                argparse.ArgumentError, argparse.ArgumentTypeError):
            print "error:", str(sys.exc_info()[1])
            if sys.exc_info()[0] in (SyntaxError, argparse.ArgumentError):
                CkgCmd.rm_parser.print_usage()
            return
        rmlist = []
        if args.all:
            del self.cur_proj.boards[:]
            print "all checkerboards removed"
            return
        elif len(args.idlist) == 0:
            print "please specify at least one id"
        for x in args.idlist:
            if x >= len(self.cur_proj.boards) or x < 0:
                print "checkerboard", x, "does not exist"
                continue
            rmlist.append(self.cur_proj.boards[x])
            print "checkerboard", x, "removed"
        for board in rmlist:
            self.cur_proj.boards.remove(board)
        self.cur_proj.dirty = True
        del rmlist[:]

    ls_parser = CmdParser(add_help=False, prog='ls',
                          description='''Lists project settings, checkerboards
                                         and their attributes.''')
    ls_parser.add_argument('idlist', nargs='*', metavar='id', type=int,
                           help='''ids of checkerboards to be listed, all
                                   are listed if not specified''')
    ls_group = ls_parser.add_mutually_exclusive_group()
    ls_group.add_argument('-s', '--settings', action='store_true',
                           help='list only settings')
    ls_group.add_argument('-b', '--boards', action='store_true',
                           help='list only checkerboards')

    def help_ls(self):
        CkgCmd.ls_parser.print_help()

    def do_ls(self, line):
        """Lists project settings, checkerboards and their attributes."""

        def ls_str(s, sep=','):
            """Special space-saving output formatter."""
            if type(s) in [tuple, list]:
                return sep.join([ls_str(i) for i in s])
            elif type(s) == pygame.Color:
                return str((s.r, s.b, s.g)).translate(None,' ')
            else:
                return str(s)

        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = CkgCmd.ls_parser.parse_args(shlex.split(line))
        except (SyntaxError, InvalidOperation,
                argparse.ArgumentError, argparse.ArgumentTypeError):
            print "error:", str(sys.exc_info()[1])
            if sys.exc_info()[0] in (SyntaxError, argparse.ArgumentError):
                CkgCmd.ls_parser.print_usage()
            return

        for x in args.idlist[:]:
            if x >= len(self.cur_proj.boards) or x < 0:
                args.idlist.remove(x)
                print "checkerboard", x, "does not exist"
        if args.idlist == []:
            args.idlist = range(len(self.cur_proj.boards))
        else:
            args.boards = True

        if not args.boards:
            print \
                'name'.rjust(13),\
                'fps'.rjust(6),\
                'resolution'.rjust(12),\
                'bg color'.rjust(16),\
                'format'.rjust(7)
            print \
                ls_str(self.cur_proj.name).rjust(13),\
                ls_str(self.cur_proj.fps).rjust(6),\
                ls_str(self.cur_proj.res).rjust(12),\
                ls_str(self.cur_proj.bg).rjust(16),\
                ls_str(self.cur_proj.export_fmt).rjust(7)

        if not args.settings and not args.boards:
            print ''

        if not args.settings:
            print \
                'id'.rjust(2),\
                'dims'.rjust(10),\
                'init_unit'.rjust(14),\
                'end_unit'.rjust(14),\
                'position'.rjust(14)
            for n, board in zip(args.idlist, self.cur_proj.boards):
                print \
                    ls_str(n).rjust(2),\
                    ls_str(board.dims).rjust(10),\
                    ls_str(board.init_unit).rjust(14),\
                    ls_str(board.end_unit).rjust(14),\
                    ls_str(board.position).rjust(14)        
            print '\n',\
                'id'.rjust(2),\
                'colors'.rjust(27),\
                'origin'.rjust(12),\
                'freq'.rjust(6),\
                'phase'.rjust(7)
            for n, board in zip(args.idlist, self.cur_proj.boards):
                print \
                    ls_str(n).rjust(2),\
                    ls_str(board.cols).rjust(27),\
                    ls_str(board.origin).rjust(12),\
                    ls_str(board.freq).rjust(6),\
                    ls_str(board.phase).rjust(7)            

    display_parser = CmdParser(add_help=False, prog='display',
                               description='''Displays the animation in a
                                              window or in fullscreen.''')
    display_parser.add_argument('-f', '--fullscreen', action='store_true',
                                help='sets fullscreen mode, ESC to quit')

    def help_display(self):
        CkgCmd.display_parser.print_help()

    def do_display(self, line):
        """Displays the animation in window or in fullscreen"""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = CkgCmd.display_parser.parse_args(shlex.split(line))
        except (SyntaxError, InvalidOperation,
                argparse.ArgumentError, argparse.ArgumentTypeError):
            print "error:", str(sys.exc_info()[1])
            if sys.exc_info()[0] in (SyntaxError, argparse.ArgumentError):
                CkgCmd.display_parser.print_usage()
            return
        for thread in threading.enumerate():
            if thread.name == 'display_thread':
                print 'error: animation is already being displayed'
                return
        else:
            threading.Thread(target=display_anim, name='display_thread',
                             args=[copy.deepcopy(self.cur_proj),
                                   args.fullscreen]).start()

    export_parser = CmdParser(add_help=False, prog='export',
                              description='''Exports animation as an image
                                             sequence (in a folder) to the
                                             specified directory.''')
    export_parser.add_argument('dir', help='destination directory for export')
    export_parser.add_argument('--fmt', dest='export_fmt', choices=EXPORT_FMTS,
                               help='image format for export')
    export_parser.add_argument('-n','--nofolder', action='store_false',
                               help='''force images not to exported in 
                                       a containing folder''')


    def help_export(self):
        CkgCmd.export_parser.print_help()

    def do_export(self, line):
        """Exports animation an image sequence to the specified directory."""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = CkgCmd.export_parser.parse_args(shlex.split(line))
        except (SyntaxError, InvalidOperation,
                argparse.ArgumentError, argparse.ArgumentTypeError):
            print "error:", str(sys.exc_info()[1])
            if sys.exc_info()[0] in (SyntaxError, argparse.ArgumentError):
                CkgCmd.export_parser.print_usage()
            return
        export_anim(self.cur_proj, args.dir, args.export_fmt, args.nofolder)

    def do_quit(self, line):
        """Quits the program."""
        return True

    def do_EOF(self, line):
        """Typing Ctrl-D issues this command, which quits the program."""
        print '\r'
        return True

    def help_help(self):
        print 'Prints a list of commands.'
        print 'Type help <topic> for more details on each command.'
    
parser = argparse.ArgumentParser(
    description='''Generate flashing checkerboard patterns for display
                   or export as a series of images, intended for use in
                   psychophysics experiments. Enters interactive command
                   line mode if no options are specified.''')

parser.add_argument('-c', '--cmd', dest='cmd_mode', action='store_true',
                    help='enter command line mode regardless of other options')
parser.add_argument('-d', '--disp', dest='display_flag', action='store_true',
                    help='displays the animation on the screen')
parser.add_argument('-e', '--export', dest='export_dir', metavar='dir',
                    help='export the animation to the specified directory')
parser.add_argument('-f', '--fullscreen', action='store_true',
                    help='animation displayed in fullscreen mode')
parser.add_argument('--fmt', dest='export_fmt', choices=EXPORT_FMTS,
                    help='image format for animation to be exported as')
parser.add_argument('path', nargs='?', type=file,
                    help='checkergen project file to open')

args = parser.parse_args()

if args.export_dir != None:
    print args.export_dir
    args.export_flag = True
else:
    args.export_flag = False

if not args.display_flag and not args.export_flag:
    args.cmd_mode = True

if args.path != None:
    if not os.path.isfile(args.path):
        sys.exit("error: path specified is not a file")
    args.proj = CkgProj(path=args.path)
    os.chdir(os.path.dirname(os.path.abspath(args.path)))
else:
    args.proj = None
    if args.display_flag or args.export_flag:
        print "error: no project file specified for display or export"
        if not args.cmd_mode:
            sys.exit(1)

if args.display_flag:
    display_thread = threading.Thread(target=display_anim,
                                      name='display_thread',
                                      args=[copy.deepcopy(args.proj), 
                                            args.fullscreen])
    display_thread.start()
if args.export_flag:
    export_anim(copy.deepcopy(args.proj), args.export_dir, args.export_fmt)
if args.cmd_mode:
    mycmd = CkgCmd()
    mycmd.cur_proj = args.proj
    mycmd.prompt = '(ckg) '
    mycmd.intro = textwrap.dedent('''\
                                  Enter 'help' for a list of commands.
                                  Enter 'quit' or Ctrl-D to exit.''')
    mycmd.cmdloop()
