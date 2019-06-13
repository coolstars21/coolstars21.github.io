# -*- coding: utf-8 -*-
'''Compile CS20 abstract book

This script compiles the CS20 abstract book.
It uses Jinja2 templates. There is a general template in /templates

This script needs to be executed in the exact directory where it is now,
because it uses relative input paths.

'''
import argparse
import os
import shutil
import subprocess

from jinja2 import Environment, FileSystemLoader, select_autoescape

import pagepy.contributions

from script_helper import parser

args = parser.parse_args()

# Generate html
env = Environment(loader=FileSystemLoader(['templates']),
                  autoescape=select_autoescape(['html']))

if not os.path.exists(args.outpath):
    os.makedirs(args.outpath)

data = pagepy.contributions.data(**vars(args))

tex_templates = ['abstractbook-long.tex']
images = ['print_images/Logoround-04.png']

for tempfile in tex_templates:
    template = env.get_template(tempfile)
    with open(os.path.join(args.outpath, tempfile), "w") as tex_out:
        tex_out.write(template.render(**data))

for f in images:
    shutil.copy(f, args.outpath)

for template in tex_templates:
    out = 'Rerun'
    while 'Rerun' in str(out):
        latex = subprocess.Popen(['pdflatex', '-interaction=nonstopmode',
                                  os.path.join(args.outpath, template)],
                                 cwd=args.outpath,
                                 stdout=subprocess.PIPE)
        out, err = latex.communicate()
