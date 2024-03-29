# coding: latin-1
# Copyright (c) 2009,2010,2011,2012,2013,2014 Dirk Baechle.
# www: http://bitbucket.org/dirkbaechle/xmlwiko
# mail: dl9obn AT darc.de
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""
xmlwiko v1.7: This script generates XML files as input to ApacheForrest or Docbook from Wiki like input.
              Inspired by WiKo (the WikiCompiler, http://wiko.sf.net) it tries to simplify
              the setup and editing of web pages (for Forrest) or simple manuals and descriptions (Docbook).
"""

import glob
import os.path
import re
import sys
import codecs

def processVerbatim(txt, language):
    """
    Try to format the given code text with the pygments package. When this
    module can be successfully imported, use the syntax highlighting for the
    specified language. Else, return the text/code as is.
    """
    
    if language.strip() == "":
        return txt
    else:    
        try :
            from pygments import highlight
            from pygments.lexers import get_lexer_by_name
            from pygments.formatters import HtmlFormatter
        except:
            return txt
        file("style_code.css",'w').write(HtmlFormatter().get_style_defs('.code'))

        try:
            lexer = get_lexer_by_name(language, stripall=True)
            formatter = HtmlFormatter(linenos=False, cssclass="code")
        except:
            return txt
        return highlight(txt, lexer, formatter)

# Regular expressions
header = re.compile(r"^==(\+|-?[0-9]+|-*)\s*([^=]+)\s*=*\s*(.*)$")

em = re.compile(r"\\\\([^\\]*)\\\\")
strong = re.compile(r"!!([^!]*)!!")
quote = re.compile(r"''([^']*)''")
code = re.compile(r"\$\$([^\$]*)\$\$")
quotedcode = re.compile(r"%%([^\%]*)%%")
url = re.compile(r"\[\[([^\s]*)\s+([^\]]*)\]\]")
xref = re.compile(r"&&([^\s]*)\s+([^&]*)&&")
link = re.compile(r"\(\(([^\s]*)\s+([^\)]*)\)\)")
urls = re.compile(r"\[\[([^\s]*?)\]\]")
links = re.compile(r"\(\(([^\s]*?)\)\)")
anchor = re.compile(r"@@([^@]*)@@")
img = re.compile(r"<<([^>]*)>>")
filter = re.compile(r"\*\*([^\s]*)\s+([^\*]*)\*\*")

li  = re.compile(r"^({*)([*#~]+)(.*)")
var = re.compile(r"^@([^:]*): (.*)")

env = re.compile(r"^({*)([a-zA-Z]+):(-*|-?[0-9]+)\s*(.*)$")
closeenv = re.compile(r"^}}\s*$")

#
# Definition of output tags for the different formats
#
# Meaning of fields from left to right is: 
#   tagstart, tagend, wrap_in_para, add_newline_on_close
#

# Forrest output tags
envTagsForrest = {
           'Section' : ['<section id="%(id)s"><title>%(title)s</title>', '</section>', True, True],
           'Para' : ['<p>', '</p>', False, True],
           'Code' : ['<source xml:space="preserve">', '</source>', False, True],
           'Image' : ['<figure src="%(fref)s"%(atts)s>', '</figure>', False, True],
           'Figure' : ['<figure src="%(fref)s"%(atts)s/><p><strong>Figure</strong>: ', '</p></figure>', False, True], 
           'Abstract' : ['<p><strong>Abstract:</strong></p>', '', True, True],
           'Remark'  : ['<p><strong>Remark:</strong></p>', '', True, True],
           'Note'  : ['<note>', '</note>', False, True],
           'Important'  : ['<p><strong>Important:</strong></p>', '', True, True],
           'Warning'  : ['<warning>', '</warning>', False, True],
           'Caution'  : ['<p><strong>Caution:</strong></p>', '', True, True],
           'Keywords' : ['<p><strong>Keywords:</strong></p>', '', True, True],
           'TODO'     : ['<p><strong>TODO:</strong></p>', '', True, True],
           'Definition'  : ['<p><strong>Definition:</strong></p>', '', True, True],
           'Lemma'    : ['<p><strong>Lemma:</strong></p>', '', True, True],
           'Proof'    : ['<p><strong>Proof:</strong></p>', '', True, True],
           'Theorem'  : ['<p><strong>Theorem:</strong></p>', '', True, True],
           'Corollary': ['<p><strong>Corollary:</strong></p>', '', True, True],
           'Raw': ['', '', False, True],
            '#' : ['<ol>', '</ol>', False, True],
            '*' : ['<ul>', '</ul>', False, True],
            '~' : ['<dl>', '</dl>', False, True],
            'olItem' : ['<li>', '</li>', False, True],
            'ulItem' : ['<li>', '</li>', False, True],
            'vlEntry' : ['', '', False, True],
            'dtItem' : ['<dt>', '</dt>', False, True],
            'ddItem' : ['<dd>', '</dd>', False, True]
           }
inlineTagsForrest = {'em' : ['<em>', '</em>'],
              'strong' : ['<strong>', '</strong>'],
              'quote' : ['&quot;', '&quot;'],
              'code' : ['<code>', '</code>'],
              'quotedcode' : ['&quot;<code>', '</code>&quot;'],
              'anchor' : ['<anchor id="', '"/>']}
dictTagsForrest = {'ulink' : '<a href="%(url)s"%(atts)s>%(linktext)s</a>',
                   'link' : '<a href="#%(url)s">%(linktext)s</a>',
                   'xref' : '<a href="#%(url)s">%(linktext)s</a>',
                   'inlinemediaobject' : '<img src="%(fref)s"%(atts)s/>'
                  }
filterForrest = {'forrest' : '%(content)s'
                }

# Default template for a Forrest XML file
defaultSkeletonForrest = u"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE document PUBLIC "-//APACHE//DTD Documentation V2.0//EN" "http://forrest.apache.org/dtd/document-v20.dtd">
<document>
  <header>
    <title>%(title)s</title>
  </header>
  <body>
%(content)s
  </body>
</document>
"""

# Docbook output tags
envTagsDocbook = {
           'Section' : ['<section id="%(id)s"><title>%(title)s</title>', '</section>', True, True],
           'Para' : ['<para>', '</para>', False, True],
           'Code' : ['<screen>', '</screen>', False, True],
           'Image' : ['<mediaobject><imageobject><imagedata fileref="%(fref)s"%(atts)s/>', '</imageobject></mediaobject>', False, True],
           'Figure' : ['<figure><mediaobject><imageobject><imagedata fileref="%(fref)s"%(atts)s/></imageobject></mediaobject><title>', '</title></figure>', False, True],
           'Abstract' : ['<abstract>', '</abstract>', True, True],
           'Remark'  : ['<remark>', '</remark>', True, True],
           'Note'  : ['<note>', '</note>', True, True],
           'Important'  : ['<important>', '</important>', True, True],
           'Warning'  : ['<warning>', '</warning>', True, True],
           'Caution'  : ['<caution>', '</caution>', True, True],
           'Keywords': ['<remark><para>Keywords:</para>', '</remark>', True, True],
           'TODO': ['<remark><para>TODO:</para>', '</remark>', True, True],
           'Definition': ['<remark><para>Definition:</para>', '</remark>', True, True],
           'Lemma': ['<remark><para>Lemma:</para>', '</remark>', True, True],
           'Proof': ['<remark><para>Proof:</para>', '</remark>', True, True],
           'Theorem': ['<remark><para>Theorem:</para>', '</remark>', True, True],
           'Corollary': ['<remark><para>Corollary:</para>', '</remark>', True, True],
           'Raw': ['', '', False, True],
           '#' : ['<orderedlist>', '</orderedlist>', False, True],
           '*' : ['<itemizedlist>', '</itemizedlist>', False, True],
           '~' : ['<variablelist>', '</variablelist>', False, True],
           'olItem' : ['<listitem>', '</listitem>', True, True],
           'ulItem' : ['<listitem>', '</listitem>', True, True],
           'vlEntry' : ['<varlistentry>', '</varlistentry>', False, True],
           'dtItem' : ['<term>', '</term>', False, True],
           'ddItem' : ['<listitem>', '</listitem>', True, True]
           }
inlineTagsDocbook = {'em' : ['<emphasis>', '</emphasis>'],
              'strong' : ['<emphasis role="bold">', '</emphasis>'],
              'quote' : ['<quote>', '</quote>'],
              'code' : ['<literal>', '</literal>'],
              'quotedcode' : ['<quote><literal>', '</literal></quote>'],
              'anchor' : ['<anchor id="', '"/>']}
dictTagsDocbook = {'ulink' : '<ulink url="%(url)s"%(atts)s>%(linktext)s</ulink>',
                   'link' : '<link linkend="%(url)s"%(atts)s>%(linktext)s</link>',
                   'xref' : '<xref linkend="%(url)s"%(atts)s/>',
                   'inlinemediaobject' : '<inlinemediaobject><imageobject><imagedata fileref="%(fref)s"%(atts)s/></imageobject></inlinemediaobject>'
                  }
filterDocbook = {'docbook' : '%(content)s'
                }

# Default template for a Docbook XML file
defaultSkeletonDocbook = u"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE article PUBLIC "-//OASIS//DTD DocBook XML V4.2//EN"
"http://www.oasis-open.org/docbook/xml/4.1.2/docbookx.dtd">
<article>
  <title>%(title)s</title>
  <articleinfo>
    <author>
      <surname>%(author)s</surname>
    </author>
  </articleinfo>
%(content)s
</article>
"""

# Moin output tags
envTagsMoin = {
           'SectionTitleChar' : ['=', '=', False, False],
           'Section' : ['%(title)s', '', False, True],
           'Para' : ['', '', False, True],
           'Code' : ['{{{\n', '}}}\n', False, True],
           'Image' : ['{{attachment:%(fref)s}}', '\n', False, True],
           'Figure' : ['{{attachment:%(fref)s}}\n', '\n', False, True],
           'Abstract' : ['Abstract: ', '', False, True],
           'Remark'  : ['Remark: ', '', False, True],
           'Note'  : ['Note: ', '', False, True],
           'Important'  : ['Important: ', '', False, True],
           'Warning'  : ['Warning: ', '', False, True],
           'Caution'  : ['Caution: ', '', False, True],
           'Keywords': ['Keywords: ', '', False, True],
           'TODO': ['TODO: ', '', False, True],
           'Definition': ['Definition: ', '', False, True],
           'Lemma': ['Lemma: ', '', False, True],
           'Proof': ['Proof: ', '', False, True],
           'Theorem': ['Theorem: ', '', False, True],
           'Corollary': ['Corollary: ', '', False, True],
           'Raw': ['', '', False, True],
           '#' : ['', '', False, False],
           '*' : ['', '', False, False],
           '~' : ['', '', False, False],
           'olItem' : [' 1.', '', False, False],
           'ulItem' : [' *', '', False, False],
           'vlEntry' : [' ', '', False, False],
           'dtItem' : ['', ':: ', False, False],
           'ddItem' : ['', '', False, False]
           }
inlineTagsMoin = {'em' : ["''", "''"],
              'strong' : ["'''", "'''"],
              'quote' : ["'''''", "'''''"],
              'code' : ['`', '`'],
              'quotedcode' : ['"`', '`"'],
              'anchor' : ['<<Anchor(', ')>>']}
dictTagsMoin = {'ulink' : '[[%(url)s|%(linktext)s]]',
                'link' : '[[%(url)s|%(linktext)s]]',
                'xref' : '[[#%(url)s]]',
                'inlinemediaobject' : '{{attachment:%(fref)s}}'
               }
filterMoin = {'moin' : '%(content)s'
             }

# Default template for a MoinMoin Wiki file
defaultSkeletonMoin = u"""%(title)s

by %(author)s

%(content)s
"""

# reST output tags
envTagsRest = {
           'SectionTitleUnderlineChars' : ['=-+_~:<>', '', False, False],
           'Section' : ['%(title)s', '', False, True],
           'Para' : ['', '', False, True],
           'Code' : ['::\n\n', '\n', False, True],
           'Image' : ['.. Image:: %(fref)s', '\n', False, True],
           'Figure' : ['.. Image:: %(fref)s\n', '\n', False, True],
           'Abstract' : ['**Abstract**: ', '', False, True],
           'Remark'  : ['**Remark**: ', '', False, True],
           'Note'  : ['.. note:: ', '', False, True],
           'Important'  : ['.. important:: ', '', False, True],
           'Warning'  : ['.. warning:: ', '', False, True],
           'Caution'  : ['.. caution:: ', '', False, True],
           'Keywords': ['**Keywords**: ', '', False, True],
           'TODO': ['**TODO**: ', '', False, True],
           'Definition': ['**Definition**: ', '', False, True],
           'Lemma': ['**Lemma**: ', '', False, True],
           'Proof': ['**Proof**: ', '', False, True],
           'Theorem': ['**Theorem**: ', '', False, True],
           'Corollary': ['Corollary: ', '', False, True],
           'Raw': ['', '', False, True],
           '#' : ['', '', False, False],
           '*' : ['', '', False, False],
           '~' : ['', '', False, False],
           'olItem' : ['#. ', '', False, False],
           'ulItem' : ['* ', '', False, False],
           'vlEntry' : ['', '', False, False],
           'dtItem' : ['', ':: ', False, False],
           'ddItem' : ['\n  ', '', False, False]
           }
inlineTagsRest = {'em' : ["*", "*"],
              'strong' : ["**", "**"],
              'quote' : ['"', '"'],
              'code' : ['``', '``'],
              'quotedcode' : ['"``', '``"'],
              'anchor' : ['.. _', ':\n']}
dictTagsRest = {'ulink' : '`%(linktext)s <%(url)s/>`_',
                'link' : '`%(linktext)s <%(url)s/>`_',
                'xref' : '%(url)s_',
                'inlinemediaobject' : '\n.. Image:: %(fref)s\n'
               }
filterRest = {'rest' : '%(content)s'
             }

# Default template for a reStructuredText file
defaultSkeletonRest = u"""####################################
%(title)s
####################################

:Author: %(author)s

%(content)s
"""


def stripUtfMarker(content) :
    """
    Strip off an optional UTF8 marker from the start
    of the input file/content.
    """
    
    import codecs
    return content.replace( unicode(codecs.BOM_UTF8,"utf8"), "")

def readUtf8(filename, quiet=False) :
    """
    Read the contents of the given file filename in UTF8 encoding.
    """
    
    if not quiet:
        print "Reading",filename
    return stripUtfMarker(codecs.open(filename,'r','utf8').read())

def loadOrDefault(filename, defaultContent, quiet=False) :
    """
    Return the contents of the file filename, or the fallback
    text defaultContent.
    """
    
    try: return readUtf8(filename, quiet)
    except: return defaultContent

def writeUtf8(filename, content) :
    """
    Save the content to a file with the given filename in UTF8 encoding.
    """
    
    import codecs, os
    path = filename.split("/")[:-1]
    for i in range(len(path)) :
        try : os.mkdir("/".join(path[:i+1]))
        except: pass
    codecs.open(filename, "w",'utf8').write(content)

def tos(seq):
    """
    Return the top of stack (TOS) element for the sequence seq,
    or an empty string if seq holds no items.
    """
    
    if len(seq) > 0:
        return seq[-1]
    else:
        return ""

# Start mode at indent level 0, no paragraph has been opened yet
PM_VOID = 0
# Parse an opened paragraph (sequence of paragraphs) at the same indent level
PM_PARA = 1
# Parse a single paragraph with code, stop at first blank line
PM_CODEPARA = 2
# Parse a sequence of code paragraphs, separated by blank lines, stop at final }}
PM_CODE = 3
# Parse a single environment paragraph, stop at first blank line
PM_ENVPARA = 4
# Parse a sequence of list items
PM_LIST = 5

list_items = ['#','*','~','olItem','ulItem','dtItem','ddItem']

class WikiCompiler :
    """ The base class for compiling Wiki files to XML output.
    """
    
    def closeAllOpenedBlocks(self):
        """
        Purge all opened blocks or XML tags.
        """
        
        while len(self.openBlocks):
            tos = self.openBlocks.pop()
            self.result += "%s" % self.envTags[tos][1]
            if self.envTags[tos][3]:
                self.result += "\n"
            
    def closeOpenedBlocks(self, tag, num=1):
        """
        Close all opened XML tags, up to the nth occurence (num)
        of the given tag.
        """
        
        cnt = 0
        while len(self.openBlocks):
            tos = self.openBlocks.pop()
            self.result += "%s" % self.envTags[tos][1]
            if self.envTags[tos][3]:
                self.result += "\n"
            
            if tos == tag:
                cnt += 1
            if cnt == num:
                break

    def openEnv(self, tag, **kwargs):
        """
        Open the given environment tag, with the optional keywords kwargs.
        For this, write out the equivalent tags to the output file and
        mark the tag as opened by pushing it onto the openBlocks stack.
        """
         
        if len(kwargs):
            self.result += "%s" % (self.envTags[tag][0] % kwargs)
        else:
            self.result += "%s" % self.envTags[tag][0]
        self.openBlocks.append(tag)
         
        
    def closeEnv(self, tag, **kwargs):
        """
        Try to close the given tag, with the optional keywords kwargs.
        When the specified tag matches the TOS of openBlocks it is popped
        from the stack, else a warning about the unbalanced stack is issued.
        """
        
        if len(kwargs):
            self.result += "%s\n" % (self.envTags[tag][1] % kwargs)
        else:
            self.result += "%s\n" % self.envTags[tag][1]
        if tos(self.openBlocks) == tag:
            self.openBlocks.pop()
        else:
            print "Warning: unbalanced tag stack! Expected '%s' but found '%s'." % (tag, tos(self.openBlocks))

    def stackNewEnvironment(self, env):
        """
        Open a new environment (like Code, Note,...) by pushing the
        current parseMode and the new environment onto a stack each.
        """
        
        # Push current parse mode
        self.modeStack.append(self.parseMode)
        # Push new environment
        self.envStack.append(env)

    def closeLastEnvironment(self):
        """
        Close the outer environment (like Code, Note,...), if there
        is an opened one on the stack at all.
        """
        
        if len(self.envStack) > 0:
            cenv = self.envStack.pop()
            self.closeOpenedBlocks(cenv, 1)
            if len(self.modeStack) > 0:
                self.parseMode = self.modeStack.pop()
            else:
                self.parseMode = PM_VOID

    def process(self, content) :
        """
        Does the main work, by parsing the content as read from
        the current input file.
        """
        
        self.itemLevel = ""
        self.closing=""
        self.result=""
        
        self.vars = {
            'title': '',
            'author': ''
        }
        # Collect simple blocks
        self.openBlocks = []
        self.parseMode = 0
        self.codeType = ""
        self.lastBlock = None
        self.sectionIndent = 0
        # Collect list envs
        self.envStack = [] # keeps track of the opened envs
        self.modeStack = [] # keeps track of the parsing modes in the opened envs
        self.lastListItem = ""

        for line in content.splitlines():
            if line.strip() == "":
                self.processEmptyLine()
            else:
                if ((self.parseMode != PM_CODE) and
                    (self.parseMode != PM_CODEPARA)):
                    varMatch = var.match(line)
                    envMatch = env.match(line)
                    listMatch = li.match(line)
                    headerMatch = header.match(line)
                else:                    
                    varMatch = None
                    envMatch = None
                    listMatch = None
                    headerMatch = None
                # Always look for closing environments
                closeEnvMatch = closeenv.match(line)

                if varMatch:
                    # Catch vars
                    key = varMatch.group(1)
                    self.vars[key] = varMatch.group(2)
                elif closeEnvMatch:
                    # Close last environment
                    self.closeLastEnvironment()
                elif envMatch and (envMatch.group(2) in self.envTags):
                    self.processEnvironment(envMatch)
                elif listMatch and listMatch.start() == 0:
                    self.processList(listMatch)
                elif headerMatch and headerMatch.start() == 0:
                    self.processSection(headerMatch)
                else:
                    if self.parseMode == PM_VOID:
                        # Stack new para environment
                        self.openEnv('Para')
                        # Set para as current environment
                        self.parseMode = PM_PARA
                    # Continue to collect lines
                    self.processText(line, self.parseMode)
                        
                
        # Close all blocks that are still opened
        self.closeAllOpenedBlocks()

        self.vars["content"] = self.result
        
        return self.vars

    def processEmptyLine(self):
        """
        Decide what to do about the empty line that was encountered.
        Based on the internal state of the parsing machine/automaton,
        output is created or a change of state happens.
        """

        # Line is emtpy: Normal mode or code env?
        if self.parseMode == PM_CODE:
            self.result += "\n"
        elif self.parseMode == PM_CODEPARA or self.parseMode == PM_ENVPARA:
            # Current Code environment gets closed
            self.closeLastEnvironment()
        elif self.parseMode == PM_PARA:
            # Current Para block gets closed
            self.closeEnv('Para')
            self.parseMode = PM_VOID
        elif self.parseMode == PM_LIST:
            # closing list items
            if self.lastListItem != "":
                oil = self.lastListItem
                odl = list(oil)
                odl.reverse()
                for o in odl:
                    self.closeLists(o)

            self.lastListItem = ""
            self.parseMode = PM_VOID

    def escapeCodeText(self, text):
        """
        Used to replace special chars like <, with their
        XHTML equivalent &lt; for example.
        """
        return text

    def processText(self, text, mode=PM_VOID):
        """
        Process a normal line of text by replacing inline expressions
        and the blank marker.
        Note: For code environments, all inlines are kept as they are!
        """

        if mode != PM_CODE and mode != PM_CODEPARA:
            # Replace inline expressions
            text = self.inlineReplace(text)
        else:
            text = self.replaceBlanks(text)
            text = self.escapeCodeText(text)
            text = processVerbatim(text, self.codeType)
 
        # Add text to result
        self.result += "%s\n" % text

    def processSection(self, headerMatch):
        """
        Open and close sections, while keeping track of the indent level.
        """
        
        addIndent = headerMatch.group(1)
        sectionTitle = headerMatch.group(2).rstrip()
        sectionId = headerMatch.group(3)
        if sectionId.strip() == "":
            sectionId = '_'.join([f.lower().strip('"') for f in sectionTitle.split()])

        # Step 1: Close old envs, based on block type and current indents

        # Normal indentation?
        if addIndent == "":
            # Yes
            self.closeOpenedBlocks('Section')
            self.sectionIndent -= 1
        else:
            # No
            if addIndent[0] == "-":
                # Extract depth
                mcnt = 1
                if len(addIndent) > 1:
                    mcnt = addIndent.count('-')
                    if mcnt == 1:
                        # Based on number
                        mcnt = int(addIndent[1:])
                self.closeOpenedBlocks('Section', mcnt+1)
                self.sectionIndent -= mcnt+1
            elif addIndent[0] != "+":
                # Jump to given section depth
                mcnt = self.sectionIndent - int(addIndent)
                self.closeOpenedBlocks('Section', mcnt)
                self.sectionIndent -= mcnt

        # Step 2: Open new section
        self.openBlocks.append('Section')
        self.sectionIndent += 1
        if 'SectionTitleChar' in self.envTags:
            # Handling of section titles that get constructed by prepending
            # a number of chars to the title, representing the current indentation
            # depth, e.g. MoinMoin format
            newtitle = self.envTags['SectionTitleChar'][0]*(self.sectionIndent+1)
            newtitle += " %s " % sectionTitle
            newtitle += self.envTags['SectionTitleChar'][1]*(self.sectionIndent+1)
            sectionTitle = newtitle
        elif 'SectionTitleUnderlineChars' in self.envTags:
            # Handling reST style section titles, where the char for the
            # underline changes with the level of indent
            linechars = self.envTags['SectionTitleUnderlineChars'][0]
            tchar = linechars[self.sectionIndent % len(linechars)]
            sectionTitle += "\n"+len(sectionTitle)*tchar
        text = "%s\n" % (self.envTags['Section'][0] % {'title':sectionTitle, 'id':sectionId})
        self.result += self.inlineReplace(text)

    def processEnvironment(self, envMatch):
        """
        Start a new environment like Code, Note or Figure.
        """
        
        blockStart = envMatch.group(1)
        blockType = envMatch.group(2)
        addIndent = envMatch.group(3)
        self.codeType = envMatch.group(4)

        curParseMode = PM_ENVPARA
        self.stackNewEnvironment(blockType)
        if blockStart == "{{":
            curParseMode = PM_PARA
        if blockType == "Figure" or blockType == "Image":
            fighref = self.codeType
            seppos = fighref.find("||")
            if seppos > 0:
                figatts = ' '+self.applyFilters(fighref[seppos+2:])
                fighref = fighref[:seppos]
            else:
                figatts = ' alt="'+fighref+'"'
            self.openEnv(blockType, fref=fighref, atts=figatts)
            if self.envTags[blockType][2]:
                # Wrap text in para
                self.openEnv('Para')
        elif blockType != "Code":
            self.openEnv(blockType)
            if self.envTags[blockType][2]:
                # Wrap text in para
                self.openEnv('Para')
        else:
            self.openEnv(blockType)
            if blockStart == "{{":
                curParseMode = PM_CODE
            else:
                curParseMode = PM_CODEPARA
        self.parseMode = curParseMode

    def replaceLinks(self, text, rex, tkey):
        """
        Replace the URL link definitions, as defined by the regular
        expression rex, in the given text.
        """
        
        lMatch = rex.search(text)
        while lMatch:
            href = lMatch.group(1)
            atxt = lMatch.group(2)
            urlatts = ""
            seppos = atxt.find("||")
            if seppos > 0:
                urlatts = ' '+atxt[:seppos]
                atxt = atxt[seppos+2:]
            middle = self.dictTags[tkey] % {'url' : href,
                                           'atts' : urlatts,
                                           'linktext' : atxt}
            text = (text[:lMatch.start()] + middle + text[lMatch.end():])
            lMatch = rex.search(text, lMatch.start()+len(middle))
            
        return text

    def replaceSimpleLinks(self, text, rex, tkey):
        """
        Replace document-internal links, as defined by the regexp
        rex, in the given text.
        """
        
        lMatch = rex.search(text)
        while lMatch:
            href = lMatch.group(1)
            atxt = href
            urlatts = ""
            middle = self.dictTags[tkey] % {'url' : href,
                                           'atts' : urlatts,
                                           'linktext' : atxt}
            text = (text[:lMatch.start()] + middle + text[lMatch.end():])
            lMatch = rex.search(text, lMatch.start()+len(middle))
        
        return text

    def replaceAll(self, text, regex, starttag, endtag):
        """
        Replace all occurrences of regex in text, by wrapping them
        in a starttag/endtag pair of XML tags.
        """
        match = regex.search(text)
        while match:
            middle = starttag+match.group(1)+endtag
            text = text[:match.start()]+middle+text[match.end():]
            match = regex.search(text, match.start()+len(middle))
            
        return text

    def applyFilters(self, text):
        """
        Apply this WikiCompilers filter to the given text.
        Depending on the found filter directive (docbook|forrest), the according text
        is filtered out...or not.
        """
        
        match = filter.search(text)
        while match:
            fkey = match.group(1)
            if fkey in self.filters:
                text = (text[:match.start()]+
                        self.filters[fkey] % {'content' : match.group(2)} +
                        text[match.end():])
            else:
                text = (text[:match.start()]+
                        text[match.end():])
            match = filter.search(text)
            
        return text

    def replaceBlanks(self, text):
        """
        Replace the \blank escape sequences in the given text.
        """
        
        text = text.replace("\\blank","")
        return text
       
    def inlineReplace(self, text):
        """
        Apply all inline replacements (like links, images, filters,...)
        to the given text.
        """
        
        # Apply filters
        text = self.applyFilters(text)
        
        # Find and replace images
        iMatch = img.search(text)
        while iMatch:
            href = iMatch.group(1)
            urlatts = ""
            seppos = href.find("||")
            if seppos > 0:
                urlatts = ' '+href[seppos+2:]
                href = href[:seppos]
            else:
                urlatts = ' alt="'+href+'"'
            text = (text[:iMatch.start()] +
                    self.dictTags['inlinemediaobject'] % {'fref' : href,
                                                          'atts' : urlatts} +
                    text[iMatch.end():])
                
            iMatch = img.search(text)
        
        # Find and replace link tags
        text = self.replaceSimpleLinks(text, urls, 'ulink')
        text = self.replaceSimpleLinks(text, links, 'link')
        text = self.replaceLinks(text, url, 'ulink')
        text = self.replaceLinks(text, xref, 'xref')
        text = self.replaceLinks(text, link, 'link')
                        
        # Apply non-greedy inline substitutions to the joined block
        text = self.replaceAll(text, em, self.inlineTags["em"][0], self.inlineTags["em"][1])
        text = self.replaceAll(text, strong, self.inlineTags["strong"][0], self.inlineTags["strong"][1])
        text = self.replaceAll(text, quote, self.inlineTags["quote"][0], self.inlineTags["quote"][1])
        text = self.replaceAll(text, code, self.inlineTags["code"][0], self.inlineTags["code"][1])
        text = self.replaceAll(text, quotedcode, self.inlineTags["quotedcode"][0], self.inlineTags["quotedcode"][1])
        text = self.replaceAll(text, anchor, self.inlineTags["anchor"][0], self.inlineTags["anchor"][1])
        # Replace \blank escape sequences
        text = self.replaceBlanks(text)
        return text

    def openListItem(self, li):
        """
        Open a new listitem by stacking it as an environment.
        """
        
        if li == '*':
            li = 'ulItem'
        elif li == '#':
            li = 'olItem'
        self.openEnv(li)
        if self.envTags[li][2]:
            # Wrap item in para
            self.openEnv('Para')

    def openTextListItem(self, o, curText):
        """
        Open a new single list item o. The variable
        curText contains the rest of the text line
        after the item specification.
        It is skipped back for unordered or ordered lists
        (and then gets output in the calling routine),
        but gets processed for variable lists.
        """
        
        if o != '~':
            self.openListItem(o)
            return curText
        else:
            fpos = curText.find('||')
            if fpos > 0:
                self.openListItem('vlEntry')
                self.openListItem('dtItem')
                self.processText(curText[:fpos])
                self.closeListItem('dtItem')
                self.openListItem('ddItem')
                self.processText(curText[fpos+2:])
            else:
                self.openListItem('vlEntry')
                self.openListItem('dtItem')
                self.processText(curText)
                self.closeListItem('dtItem')
                self.openListItem('ddItem')
            return ""

    def openList(self, li):
        """
        Opens a new list environment by pushing
        env onto the stack of opened blocks.
        """
        self.openEnv(li)
        if self.envTags[li][2]:
            # Wrap item in para
            self.openEnv('Para')

    def closeListItem(self, li):
        """
        Close the given single list item li.
        """
        if li == '*':
            li = 'ulItem'
        elif li == '#':
            li = 'olItem'
        elif li == '~':
            li = 'vlEntry'
        self.closeOpenedBlocks(li, 1)
        
    def closeLists(self, li):
        """
        Pops environments from the stack of opened blocks,
        until the given list items li have been matched in
        reverse order.
        """
        oil = list(li)
        oil.reverse()
        if oil:
            for o in oil:
                self.closeOpenedBlocks(o, 1)

    def processList(self, lMatch):
        """
        Open a new list as an environment, or continue the current
        one by appending a new listitem.
        """
        
        blockStart = lMatch.group(1)
        curItem = lMatch.group(2)
        curText = lMatch.group(3)
        
        if self.parseMode != PM_LIST:
            # Open new list environment
            self.parseMode = PM_LIST
            
            # Open new lists
            for o in curItem:
                self.openList(o)
                curText = self.openTextListItem(o, curText)
        else:
            # Continue current list environment
            # Compare list indent
            commonPrefix = os.path.commonprefix([self.lastListItem, curItem])
            commonLength = len(commonPrefix)
            if self.lastListItem == curItem:
                # Close last item...
                self.closeListItem(curItem[-1])
                # and open a new one
                curText = self.openTextListItem(curItem[-1], curText)
            else:
                if (commonLength > 0) and (commonLength < len(self.lastListItem)):
                    # Close lists
                    oil = self.lastListItem[commonLength:]
                    if oil and (oil != ""):
                        odl = list(oil)
                        odl.reverse()
                        for o in odl:
                            self.closeLists(o)
                    # Close listitem
                    self.closeListItem(commonPrefix[-1])
                    # Open new listitem
                    self.openListItem(commonPrefix[-1])
                if len(curItem) > len(commonPrefix):
                    # Open new lists
                    oil = curItem[commonLength:]
                    for o in oil:
                        self.openList(o)
                        curText = self.openTextListItem(o, curText)

        if blockStart == "{{":
            c = curItem[-1]
            if c == '~':
                c = 'vlEntry'
            elif c == '*':
                c = 'ulItem'
            else:
                c = 'olItem'
            self.stackNewEnvironment(c)
            self.openEnv('Para')
            self.parseMode = PM_PARA
                        
        if curText != "":
            self.processText(curText)
        self.lastListItem = curItem

class ForrestCompiler(WikiCompiler):
    """
    The WikiCompiler for ApacheForrest XML output.
    """
    
    def __init__(self):
        self.envTags = envTagsForrest
        self.inlineTags = inlineTagsForrest
        self.dictTags = dictTagsForrest
        self.filters = filterForrest

    def escapeCodeText(self, text):
        """
        Used to replace special chars like <, with their
        XHTML equivalent &lt; for example.
        """
        text = text.replace("&","&amp;")
        text = text.replace("<","&lt;")
        text = text.replace(">","&gt;")
        return text

class DocbookCompiler(WikiCompiler):
    """
    The WikiCompiler for Docbook XML output.
    """

    def __init__(self):
        self.envTags = envTagsDocbook
        self.inlineTags = inlineTagsDocbook
        self.dictTags = dictTagsDocbook
        self.filters = filterDocbook

    def escapeCodeText(self, text):
        """
        Used to replace special chars like <, with their
        XHTML equivalent &lt; for example.
        """
        text = text.replace("&","&amp;")
        text = text.replace("<","&lt;")
        text = text.replace(">","&gt;")
        return text

class MoinCompiler(WikiCompiler):
    """
    The WikiCompiler for MoinMoin Wiki output.
    """

    def __init__(self):
        self.envTags = envTagsMoin
        self.inlineTags = inlineTagsMoin
        self.dictTags = dictTagsMoin
        self.filters = filterMoin

class RestCompiler(WikiCompiler):
    """
    The WikiCompiler for reST output.
    """

    def __init__(self):
        self.envTags = envTagsRest
        self.inlineTags = inlineTagsRest
        self.dictTags = dictTagsRest
        self.filters = filterRest

    def escapeCodeText(self, text):
        """
        Used to replace special chars like <, with their
        XHTML equivalent &lt; for example.
        """
        text = " "*4 + text
        return text


compiler_skeletons = {'db' : defaultSkeletonDocbook,
                      'moin' : defaultSkeletonMoin,
                      'rest' : defaultSkeletonRest,
                      'forrest' : defaultSkeletonForrest}

