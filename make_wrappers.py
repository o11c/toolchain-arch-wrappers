#!/usr/bin/env python3

import argparse
import os
import pipes
import re
import shutil


TOOLS = ('''
accel-nvptx-none-gcc
addr2line
ar
as
c++filt
cpp
dwp
elfedit
g++
gappletviewer
gc-analyze
gcc
gcc-ar
gcc-nm
gcc-ranlib
gccbrig
gccgo
gcj
gcj-dbtool
gcj-wrapper
gcjh
gcov
gcov-dump
gcov-tool
gdc
gfortran
gij
gjar
gjarsigner
gjavah
gjdoc
gkeytool
gnat
gnatbind
gnatchop
gnatclean
gnatfind
gnatgcc
gnathtml
gnative2ascii
gnatkr
gnatlink
gnatls
gnatmake
gnatname
gnatprep
gnatxref
go
gofmt
gold
gorbd
gprof
grmic
grmid
grmiregistry
gserialver
gtnameserv
jcf-dump
jv-convert
ld
ld.bfd
ld.gold
nm
objcopy
objdump
pkg-config
ranlib
readelf
size
strings
strip
'''.split())

BLACKLIST = set('''
accel-nvptx-none-gcc
pkg-config
'''.split())

TOOL_FIXUPS = [
        # remove version numbers
        ('-[0-9.]\+$', ''),
        # TODO figure out if there's a way to remove leading g
        # (but only when it's not part of the real tool's name)

        ('^(gold|ld\.(bfd|gold))$', 'ld'),
        ('^gcc-(ar|nm|ranlib)$', lambda m: m.group(1)),
]

# None means "untested, may cause problems"
# '' means "nothing needed"
FLAGS_INFO = {
        'addr2line': '',
        'ar': '',
        'as': None, # definitely not safe
        'c++filt': '',
        'cpp': 'gcc_flags',
        'dwp': '',
        'elfedit': '',
        'g++': 'gcc_flags',
        'gappletviewer': None, # unknown
        'gc-analyze': None, # unknown
        'gcc': 'gcc_flags',
        'gcc-ar': '',
        'gcc-nm': '',
        'gcc-ranlib': '',
        'gccbrig': None, # unknown
        'gccgo': None, # unknown
        'gcj': None, # unknown
        'gcj-dbtool': None, # unknown
        'gcj-wrapper': None, # unknown
        'gcjh': None, # unknown
        'gcov': None, # unknown
        'gcov-dump': None, # unknown
        'gcov-tool': None, # unknown
        'gdc': 'gcc_flags',
        'gfortran': 'gcc_flags',
        'gij': None, # unknown
        'gjar': None, # unknown
        'gjarsigner': None, # unknown
        'gjavah': None, # unknown
        'gjdoc': None, # unknown
        'gkeytool': None, # unknown
        'gnat': None, # unknown
        'gnatbind': None, # unknown
        'gnatchop': None, # unknown
        'gnatclean': None, # unknown
        'gnatfind': None, # unknown
        'gnatgcc': None, # unknown
        'gnathtml': None, # unknown
        'gnative2ascii': None, # unknown
        'gnatkr': None, # unknown
        'gnatlink': None, # unknown
        'gnatls': None, # unknown
        'gnatmake': None, # unknown
        'gnatname': None, # unknown
        'gnatprep': None, # unknown
        'gnatxref': None, # unknown
        'go': None, # unknown
        'gofmt': None, # unknown
        'gorbd': None, # unknown
        'gprof': None, # unknown
        'grmic': None, # unknown
        'grmid': None, # unknown
        'grmiregistry': None, # unknown
        'gserialver': None, # unknown
        'gtnameserv': None, # unknown
        'jcf-dump': None, # unknown
        'jv-convert': None, # unknown
        'ld': None, # definitely not safe. But you should *really* be doing your linking via gcc
        'nm': '',
        'objcopy': None, # usually safe, but not always - see option -B
        'objdump': '',
        'ranlib': '',
        'readelf': '',
        'size': '',
        'strings': '',
        'strip': '',
}

ARCH_FIXUPS = [
        ('-pc-', '-'),
        ('-unknown-', '-'),
        # normalize i386 arches
        ('^i[456]86-', 'i386-'),
]

ARCHES = {
        'i386-linux-gnu': {
            'wraps': 'x86_64-linux-gnu',
            'gcc_flags': '-m32',
        },
        'x86_64-linux-gnux32': {
            'wraps': 'x86_64-linux-gnu',
            'gcc_flags': '-mx32',
        },
}


def safe_msg(tool):
    return '# tool "%s" is believed to be safe' % tool

def warning_msg(tool):
    msg = 'Warning: untested tool "%s". Please report your results to https://github.com/o11c/toolchain-arch-wrappers' % tool
    return 'echo %s >&2' % pipes.quote(msg)


def apply_fixups(string, fixups):
    for pattern, repl in fixups:
        string = re.sub(pattern, repl, string)
    return string


def wrap_tool(tool, config):
    filename = 'bin/%s-%s' % (config.prefix, tool)
    executable = '%s-%s' % (config.arch_info['wraps'], tool)
    tool = apply_fixups(tool, TOOL_FIXUPS)
    try:
        os.remove(filename)
    except FileNotFoundError:
        pass
    if tool in BLACKLIST:
        return

    flags_var = FLAGS_INFO.get(tool)
    if flags_var is not None:
        flags = flags_var and config.arch_info[flags_var]
        warning = safe_msg(tool)
    else:
        flags = ''
        warning = warning_msg(tool)

    if config.absolute or config.symlinks:
        executable = shutil.which(executable)

    if config.symlinks and not flags and flags_var is not None:
        os.symlink(executable, filename)
        return

    with open(filename, 'w') as script:
        os.chmod(filename, 0o111 | os.stat(filename).st_mode)
        script.write(
            '#!/bin/sh\n'
            '%s\n'
            'exec %s %s "$@"\n' % (warning, executable, flags)
        )


def wrap(config):
    config.prefix = config.arch
    config.arch = apply_fixups(config.arch, ARCH_FIXUPS)
    try:
        config.arch_info = ARCHES[config.arch]
    except KeyError:
        print('Arch %s not found' % config.arch)
        pass

    for tool in config.tools or TOOLS:
        wrap_tool(tool, config)


def make_parser():
    parser = argparse.ArgumentParser(description='create toolchain wrappers')
    parser.add_argument('arch', help='architecture (required)')
    parser.add_argument('tools', nargs='*', default=None, help='list of specific tools to wrap (default all)')
    parser.add_argument('--absolute', default=False, action='store_true', help='hard-code PATH lookup')
    parser.add_argument('--symlinks', default=False, action='store_true', help='when possible, use symlinks (implies --absolute)')
    return parser

def main():
    parser = make_parser()
    config = parser.parse_args()
    wrap(config)


if __name__ == '__main__':
    main()
