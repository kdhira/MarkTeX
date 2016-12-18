#!/usr/bin/env python3

import os
import sys
import re
import math
from collections import OrderedDict
VERSION='v0.2'
CONFIGEXT = '.mtconfig'

class MarkTex:
    def __init__(self):
        self.macros = OrderedDict()
        self.defaultvars = OrderedDict()
        # self.documents = []

        self.patterns = [];
        self.patterns.append((r'\[(.*?)\]\("(.*?)"\)', (('\\href{', '}'), ('{\\underline{', '}}')), False, [1, 0]))
        self.patterns.append((r'\[(.*?)\]', (('\\url{\\underline{', '}}'),), False, [0]))
        self.patterns.append((r'\*{3}(.*?)\*{3}', (('\\textbf{\\textit{', '}}'),), True, [0]))
        self.patterns.append((r'\*{2}(.*?)\*{2}', (('\\textbf{', '}'),), True, [0]))
        self.patterns.append((r'\*{1}(.*?)\*{1}', (('\\textit{', '}'),), True, [0]))
        self.patterns.append((r'_{3}(.*?)_{3}', (('\\textbf{\\textit{', '}}'),), True, [0]))
        self.patterns.append((r'_{2}(.*?)_{2}', (('\\textbf{', '}'),), True, [0]))
        self.patterns.append((r'_{1}(.*?)_{1}', (('\\textit{', '}'),), True, [0]))
        self.patterns.append((r'`{1}(.*?)`{1}', (('\\texttt{', '}'),), True, [0]))

        self.escapeChars = '[]()*_`'

        macrotypes = ['preamble', 'document']

        dir = os.path.expanduser('~/.MarkTeX/')
        if not os.path.exists(dir):
            os.makedirs(dir)

        for macrotype in macrotypes:
            self.macros[macrotype] = {}
            macromapfile = dir + macrotype + CONFIGEXT
            if os.path.isfile(macromapfile):
                with open(macromapfile, 'r') as fr:
                    for line in fr:
                        if line.startswith('#') or not ':' in line:
                            continue

                        key, val = line.split(':', 1)
                        key, val = key.strip(), val.strip()
                        if key != '':
                            self.macros[macrotype][key] = val
            elif not os.path.exists(macromapfile):
                open(macromapfile, 'x').close()


        defaultvarsfile = dir + 'defaults' + CONFIGEXT
        if os.path.isfile(defaultvarsfile):
            with open(defaultvarsfile, 'r') as fr:
                for line in fr:
                    if line.startswith('#') or not ':' in line:
                        continue

                    key, val = line.split(':', 1)
                    key, val = key.strip(), val.strip()
                    if key != '':
                        self.defaultvars[key] = val

    def generateDocument(self, file):
        newDoc = LatexDocument(file, self)
        # self.documents.append(newDoc)

        newDoc.readFrontMatter()
        newDoc.handleVariables()
        newDoc.writeContent()

        # Need to find a better place for this
        newDoc.fr.close()

        return newDoc


class LatexDocument:
    def __init__(self, inputFile, mtx):
        self.marktex = mtx
        self.content = ''
        self.preamble = ''
        self.vars = mtx.defaultvars.copy()
        self.inputFile = inputFile

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
        if self.fr.readline().rstrip() != '---':
            return

        while True:
            line = self.fr.readline();
            if line == '':
                return

            line = line.rstrip()
            if line == '---':
                break

            if not line.startswith('#') and ':' in line:
                key,val = line.split(':', 1)
                key = key.strip()
                val = val.strip()
                if key != '':
                    self.addVariable(key, val)



    def handleVariables(self):
        self.appendPreamble('\\documentclass[10pt,a4paper]{article}\n')
        self.appendPreamble('\\usepackage{hyperref}\n')

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

        line = self.fr.readline()
        while line != '':
            rawline = line
            line = line.rstrip()
            if line == '```' and not raw:
                code = not code
                self.appendContent('\\' + ('begin' if code else 'end') + '{verbatim}\n')
            elif line == '\\begin{latex}' and not code:
                raw = True
            elif line == '\\end{latex}' and not code:
                raw = False
            elif raw or code:
                self.appendContent(line + '\n')
            elif line == '---':
                self.appendContent('\\hrule\n')
            elif line.startswith('#'):
                self.addHeading(line)
            else:
                self.appendContent(self.parseText(rawline))

            line = self.fr.readline()

    def addHeading(self, line):
        depth = 0
        for i in range(3, 0, -1):
            if line.startswith(i*'#'):
                depth = i
                break

        self.appendContent('\\'+ (depth-1)*'sub' + 'section{' + self.parseText(line[depth:].lstrip()) + '}\n')

    def parseText(self, text):
        i = 0
        genOut = ''

        while i < len(text):
            if text[i] == '\\':
                if i+1 < len(text) and text[i+1] in self.marktex.escapeChars:
                    genOut += text[i+1]
                    i += 2
                else:
                    genOut += text[i]
                    i += 1
            else:
                matchFound = False
                for regex, wrappers, subparse, order in self.marktex.patterns:
                    match = re.match(regex, text[i:])
                    if match:
                        matchFound = True
                        assignOrder = order + [0]*(match.lastindex-len(order))
                        for j in range(match.lastindex):
                            genOut += wrappers[j][0] + self.recursionMap[subparse](match.group(assignOrder[j]+1)) + wrappers[j][1]
                        i += match.end()
                        break
                if not matchFound:
                    genOut += text[i]
                    i += 1

        return genOut

    def combineDocument(self):
        return self.preamble \
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

# Print start message.
print('MarkTeX ' + VERSION)

mtx = MarkTex()

verbose = False
for i in range(1, len(sys.argv)):
    arg = sys.argv[i]
    if arg == '-v':
        verbose = True
        continue
    if not os.path.isfile(arg):
        print(arg + ' does not exist.')
        continue

    print('Input file:' + arg)

    doc = mtx.generateDocument(arg)
    doc.writeToFile()

    if verbose:
        print(doc.combineDocument())
