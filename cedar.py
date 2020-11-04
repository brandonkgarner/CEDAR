#!/usr/bin/env python3
"""
The idea here is to have one demo of each common argparse format
type. This is useful for me to be able to copy/paste into a new
script and have something to quickly edit and trim down to get
the functionality I need.
Expect this file to grow/change as I need new options.
This is, however, a working example. I hate examples that don't
actually build/run, and this isn't one of them. Since there are
required argument types, some strings and numbers must be
provided.
Example (in your terminal):
    $ python3 argparse-template.py "hello" 123 --enable
Copyright (c) 2020, Alexander Hogen
"""
import sys
import argparse


def cmdline_args():
    # Make parser object

    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)

    p.add_argument("required_positional_arg",
                   help="desc")
    p.add_argument("required_int", type=int,
                   help="req number")
    p.add_argument("--on", action="store_true",
                   help="include to enable")
    p.add_argument("-v", "--verbosity", type=int, choices=[0, 1, 2], default=0,
                   help="increase output verbosity (default: %(default)s)")

    group1 = p.add_mutually_exclusive_group(required=True)
    group1.add_argument('--enable', action="store_true")
    group1.add_argument('--disable', action="store_false")

    return (p.parse_args())


# Try running with these args
#
# "Hello" 123 --enable
if __name__ == '__main__':

    if sys.version_info < (3, 5, 0):
        sys.stderr.write("You need python 3.5 or later to run this script\n")
        sys.exit(1)

    try:
        args = cmdline_args()
        print(args)
    except:
        print('Try $python <script_name> "Hello" 123 --enable')

    print()