#!/usr/bin/env python3

# MarkTeX: Markdown to LaTeX parser.
# Author: Kevin Hira, http://github.com/kdhira/MarkTeX

import os
import sys
import re
import math
from collections import OrderedDict

# Define global constants.
VERSION='v1.0'
CONFIGEXT = '.mtconfig'

class MarkTex:
    def __init__(self):
        # Set up dictionaries to store macros and variables from front matter.
        self.macros = OrderedDict()
        self.defaultvars = OrderedDict()

        # Build up pattern bank of parsable text.
        self.patterns = [];

        # Pattern for maths mode.
        self.patterns.append((r'\$\$(.*?)\$\$', (('$$', '$$'),), False, [0]))
        self.patterns.append((r'\$\$(.*?)\$\$', (('$$', '$$'),), False, [0]))

        # Patterns for images
        self.patterns.append((r'!\[(.*?)\]', (('\\includegraphics[width=\\textwidth]{', '}'),), False, [0]))

        # Patterns for links.
        self.patterns.append((r'\[([^\[]*?)\]\("(.*?)"\)', (('\\href{', '}'), ('{\\underline{', '}}')), False, [1, 0]))
        self.patterns.append((r'\[(.*?)\]', (('\\href{', '}'), ('{\\underline{', '}}')), False, [0, 0]))
        self.patterns.append((r'([a-z]+:\/\/[a-z]+.[a-z]+(?:.[a-z]+)*(?:\/\w+)*(?:\/|(?:\w+.[a-z0-9]+))?(?:\?=\S*)?)', (('\\href{', '}'), ('{', '}')), False, [0, 0] ))
        self.patterns.append((r"(?:mailto\:)?([a-zA-Z0-9!#\$%&'\*+\-\/=\?^_`\{|\}~]+(?:\.[a-zA-Z0-9!#\$%&'\*+\-\/=\?^_`\{|\}~]+)*@[a-zA-Z0-9][a-zA-Z0-9-]*(?:\.[a-zA-Z0-9]+)+)", (('\\href{mailto:', '}'), ('{', '}')), False, [0, 0] ))

        # Patterns for bold, italic, code.
        self.patterns.append((r'\*{3}(.*?)\*{3}', (('\\textbf{\\textit{', '}}'),), True, [0]))
        self.patterns.append((r'\*{2}(.*?)\*{2}', (('\\textbf{', '}'),), True, [0]))
        self.patterns.append((r'\*{1}(.*?)\*{1}', (('\\textit{', '}'),), True, [0]))
        self.patterns.append((r'_{3}(.*?)_{3}', (('\\underline{\\emph{', '}}'),), True, [0]))
        self.patterns.append((r'_{2}(.*?)_{2}', (('\\underline{', '}'),), True, [0]))
        self.patterns.append((r'_{1}(.*?)_{1}', (('\\emph{', '}'),), True, [0]))
        self.patterns.append((r'`{1}(.*?)`{1}', (('\\lstinline{', '}'),), True, [0]))

        # List of characters that will be escaped when preceeded with a backslash.
        self.escapeChars = '[]()*_`\\'

        # Define and start to read through default macros.
        macrotypes = ['preamble', 'document', 'defaults']

        dir = os.path.expanduser('~/.MarkTeX/')
        if not os.path.exists(dir):
            os.makedirs(dir)

        for macrotype in macrotypes:
            # Define sub-dictionary to store macros.
            self.macros[macrotype] = OrderedDict()

            # Build file path to the config file.
            macromapfile = dir + macrotype + CONFIGEXT

            # Check if this file exists.
            if os.path.isfile(macromapfile):
                # Open the file and start reading in lines.
                with open(macromapfile, 'r') as fr:
                    for line in fr:

                        # Check if the line is in the right format, ie doesn't start with a # (comments) and has a colon.
                        if line.startswith('#') or not ':' in line:
                            continue

                        # Split and retrieve key and value of the pair.
                        key, val = line.split(':', 1)
                        key, val = key.strip(), val.strip()

                        # Validate for a viable key.
                        if key != '':
                            self.macros[macrotype][key] = val

            # If the file doesn't exist, create one and don't do anything with it.
            elif not os.path.exists(macromapfile):
                open(macromapfile, 'x').close()

        # Set default variables dictionary for LatexDocuments to base off.
        self.defaultvars = self.macros['defaults']


    def generateDocument(self, file):
        """
        generateDocument() simply pieces the sub operations of compiling a document into one method.
        Some methods called could (maybe should) be chained or refactored into the LatexDocument itself.

        Process: Read front matter section, process front matter and write premable of document, parse content of document.
        """
        newDoc = LatexDocument(file, self)

        newDoc.readFrontMatter()
        newDoc.handleVariables()
        newDoc.writeContent()

        newDoc.fr.close()

        return newDoc


class LatexDocument:
    def __init__(self, inputFile, mtx):
        self.marktex = mtx
        self.documentclass = '\\documentclass[10pt,a4paper]{article}'
        self.content = ''
        self.preamble = ''
        self.customPreamble = ''
        self.vars = mtx.defaultvars.copy()
        self.inputFile = inputFile
        self.inputDir = os.path.dirname(os.path.realpath(self.inputFile))

        self.recursionMap = {
            True: lambda x: self.parseText(x),
            False: lambda x: x
        }

        try:
            self.fr = open(inputFile, 'r')
        except Exception as e:
            print(str(e))

    def addVariable(self, key, value):
        self.vars[key] = value

    def appendPreamble(self, text):
        self.preamble += text

    def appendContent(self, text):
        self.content += text

    def readFrontMatter(self):
        pos = self.fr.tell()
        if self.fr.readline().rstrip() != '---':
            self.fr.seek(pos)
            return

        while True:
            line = self.fr.readline();
            if line == '':
                return

            line = line.rstrip()
            if line == '---':
                break
            line = line.strip()

            if not line.startswith('#'):
                if line.startswith('\\documentclass'):
                    match = re.match(r'^\\documentclass(\[(.*?)\])?\{[a-z]+\}', line)
                    if match:
                        self.documentclass = line
                elif line.startswith('\\'):
                    self.customPreamble += line + '\n'
                elif ':' in line:
                    key,val = line.split(':', 1)
                    key = key.strip()
                    val = val.strip()
                    if key != '':
                        self.addVariable(key, val)



    def handleVariables(self):
        self.appendPreamble(self.documentclass + '\n')
        self.appendPreamble('\\usepackage{hyperref, listings, graphicx} \\lstset{breaklines=true, basicstyle={\\ttfamily}}\n')

        documentKeys = {k:v for k,v in self.vars.items() if k.startswith('document.')}

        for v in ['title', 'author', 'date']:
            if v in self.vars:
                self.appendPreamble('\\' + v + '{' + self.vars[v] + '}\n')

        map = {
            'preamble': self.appendPreamble,
            'document': self.appendContent
        }
        for m,f in map.items():
            for k in OrderedDict([(k,v) for k,v in self.vars.items() if k.startswith(m + '.') and v in ['1', 'True', 'true', 'yes', 'Yes']]):
                f(self.marktex.macros[m][k.partition('.')[2]] + '\n')

    def writeContent(self):
        raw = False
        code = False
        listHierarchy = []
        # codeEnv = 'verbatim'
        codeEnv = 'lstlisting'

        rawline = 'null'
        while rawline != '':
            line = self.fr.readline()
            rawline = line
            line = line.rstrip('\r\n')

            headingMatch = re.match(r'(#{1,3})(\*?)([ ]?)(.+)', line)
            listMatch = re.match(r'(\s*)(\d+\.|-)[ ]?(.+)', line)
            externalMatch = re.match(r'<<(.+)>>', line)
            if line.strip().startswith('<!--'):
                while line != '' and not line.strip().endswith('-->'):
                    line = self.fr.readline()
                continue
            elif line == '```' and not raw:
                code = not code
                self.appendContent('\\' + ('begin' if code else 'end') + '{'+ codeEnv +'}\n')
            elif line == '\\begin{latex}' and not code:
                raw = True
            elif line == '\\end{latex}' and not code:
                raw = False
            elif raw or code:
                self.appendContent(line + '\n')
            elif line == '---':
                self.appendContent('\\hrule\n')
            elif externalMatch and os.path.isfile(((self.inputDir + '/') if not externalMatch.group(1)[0] in '/~' else '') + externalMatch.group(1)):
                self.appendFile(((self.inputDir + '/') if not externalMatch.group(1)[0] in '/~' else '') + externalMatch.group(1))
            elif headingMatch:
                self.appendContent('\\' + (len(headingMatch.group(1))-1)*'sub' + 'section' + headingMatch.group(2) + '{' + self.parseText(headingMatch.group(4)) + '}\n')
            elif listMatch:
                depth = len(listMatch.group(1).replace('\t', '    '))//4 + 1
                listType = 'itemize' if listMatch.group(2) == '-' else 'enumerate'
                if depth > len(listHierarchy):
                    while len(listHierarchy) < depth:
                        self.appendContent('\\begin{' + listType + '}\n')
                        listHierarchy.append(listType)
                elif depth < len(listHierarchy):
                    while depth < len(listHierarchy):
                        self.appendContent('\\end{' + listHierarchy.pop() + '}\n')
                self.appendContent('\\item ' + self.parseText(listMatch.group(3))+ '\n')
            else:
                while len(listHierarchy) > 0:
                    self.appendContent('\\end{' + listHierarchy.pop() + '}\n')
                self.appendContent(self.parseText(line) + '\n')


        while len(listHierarchy) > 0:
            self.appendContent('\\end{' + listHierarchy.pop() + '}\n')

    def parseText(self, text):
        i = 0
        genOut = ''

        while i < len(text):
            if text[i] == '\\' and not re.match(r'\\\\\s*', text[i:]):
                if i+1 < len(text) and text[i+1] in self.marktex.escapeChars:
                    genOut += text[i+1]
                    i += 2
                else:
                    genOut += text[i]
                    i += 1
            else:
                for regex, wrappers, subparse, order in self.marktex.patterns:
                    match = re.match(regex, text[i:])
                    if match and not any(self.escapedClosing(match.group(i)) for i in range(1, match.lastindex+1)):
                        assignOrder = order + [0]*(match.lastindex-len(order))
                        for j in range(len(assignOrder)):
                            genOut += wrappers[j][0] + self.recursionMap[subparse](match.group(assignOrder[j]+1)) + wrappers[j][1]
                        i += match.end()
                        break
                else:
                    genOut += text[i]
                    i += 1

        return genOut

    def escapedClosing(self, text):
        match = re.match(r'^([^\\]+[\\]+)*([^\\]+([\\]+))$', text)
        if match and len(match.group(3))%2 == 1:
            return True
        return False

    def appendFile(self, filename):
        with open(filename, 'r') as extF:
            for line in extF:
                self.appendContent(line)

    def combineDocument(self):
        return self.preamble \
            + self.customPreamble \
            + '\n\\begin{document}\n\n' \
            + self.content \
            + '\n\\end{document}\n'

    def writeToFile(self):
        if not '.' in self.inputFile:
            newFile = self.inputFile + '.tex'
        else:
            newFile = self.inputFile.rsplit('.', 1)[0] + '.tex'


        with open(newFile, 'w') as fw:
            fw.write(self.combineDocument())


# print(os.path.realpath(__file__))
if len(sys.argv) < 2:
    print('Usage: MarkTeX <input mtex files>.')
    sys.exit(1)

verbose = False
toTerminal = False

for arg in [sys.argv[i] for i in range(1, len(sys.argv)) if sys.argv[i].startswith('-')]:
    if 'v' in arg:
        verbose = True
    if 't' in arg:
        toTerminal = True

# Print start message.
if not toTerminal:
    print('MarkTeX ' + VERSION)

mtx = MarkTex()

for i in range(1, len(sys.argv)):
    arg = sys.argv[i]
    if arg.startswith('-'):
        continue
    if not os.path.isfile(arg):
        if not toTerminal:
            print(arg + ' does not exist.')
        continue

    if not toTerminal:
        print('Input file:' + arg)

    doc = mtx.generateDocument(arg)

    if toTerminal:
        print(doc.combineDocument())
    else:
        doc.writeToFile()
