#!/usr/bin/env python3

import sys

if sys.version_info < (3, 8):
    print('Error: python 3.8 or higher is required. You are currently running:\n%s' % sys.version, file=sys.stderr)
    sys.exit(1)

if __name__ == '__main__':
    import commode
    commode.run()
