"""Enable the Horizon FFmpeg configuration already supplied by the pinned SDK."""
import argparse
import pathlib

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('sdk', type=pathlib.Path)
args = parser.parse_args()
path = args.sdk/'thirdparty/FFmpeg/config.h'
text = path.read_text()
if '#include "config_switch_aarch64.h"' not in text:
    if not text.startswith('#if defined(WIN32)'): raise ValueError('Unexpected FFmpeg platform selector')
    text = '#if defined(__SWITCH__)\n#include "config_switch_aarch64.h"\n#elif'+text[3:]
if '#include "config_masseffect_wmv3.h"' not in text:
    text += '\n#include "config_masseffect_wmv3.h"\n'
path.write_text(text)
print('Horizon FFmpeg configuration ready')
