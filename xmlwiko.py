# Copyright (c) 2009 Dirk Baechle.
# www: http://www.mydarc.de/dl9obn/programming/python/xmlwiko
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
xmlwiko: This script generates XML files as input to ApacheForrest or Docbook from Wiki like input.
         Inspired by WiKo (the WikiCompiler, http://wiko.sf.net) it tries to simplify
         the setup and editing of web pages (for Forrest) or simple manuals and descriptions (Docbook).
"""
 
import glob
import os.path
import re
import sys
import subprocess
import urllib
import codecs

def processVerbatim(txt, language):
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

header = re.compile(r"^==(\+|-*|-?[0-9]+)\s*([^=]+)\s*=*\s*(.*)$")

# Regular expressions
em = re.compile(r"//([^/]*)//")
strong = re.compile(r"!!([^!]*)!!")
quote = re.compile(r"''([^']*)''")
code = re.compile(r"\$\$([^\$]*)\$\$")
url = re.compile(r"\[\[([^\s]*)\s+([^\]]*)\]\]")
anchor = re.compile(r"@@([^@]*)@@")
img = re.compile(r"<<([^>]*)>>")

li  = re.compile(r"^([*#~]+)(.*)")
var = re.compile(r"^@([^:]*): (.*)")

env = re.compile(r"^({*)([a-zA-Z]+):(-*|-?[0-9]+)\s*(.*)$");
closeenv = re.compile(r"^}}\s*$")

# Forrest output tags
envTagsForrest = {
           'Section' : ['<section id="%(id)s"><title>%(title)s</title>', '</section>', True],
           'Para' : ['<p>', '</p>', False],
           'Code' : ['<source xml:space="preserve">', '</source>', False],
           'Figure' : ['', '', False],           
           'Abstract' : ['<p><strong>Abstract:</strong></p>', '', True],
           'Remark'  : ['<p><strong>Remark:</strong></p>', '', True],
           'Note'  : ['<note>', '</note>', False],
           'Important'  : ['<p><strong>Important:</strong></p>', '', True],
           'Warning'  : ['<warning>', '</warning>', False],
           'Caution'  : ['<p><strong>Caution:</strong></p>', '', True],
           'Keywords' : ['<p><strong>Keywords:</strong></p>', '', True],
           'TODO'     : ['<p><strong>TODO:</strong></p>', '', True],
           'Definition'  : ['<p><strong>Definition:</strong></p>', '', True],
           'Lemma'    : ['<p><strong>Lemma:</strong></p>', '', True],
           'Proof'    : ['<p><strong>Proof:</strong></p>', '', True],
           'Theorem'  : ['<p><strong>Theorem:</strong></p>', '', True],
           'Corollary': ['<p><strong>Corollary:</strong></p>', '', True]
}
listTagsForrest = {'#' : ['<ol>', '</ol>'],
            '*' : ['<ul>', '</ul>'],
            '~' : ['<dl>', '</dl>'],
            'olItem' : ['<li>', '</li>'],
            'ulItem' : ['<li>', '</li>'],
            'dtItem' : ['<dt>', '</dt>'],
            'ddItem' : ['<dd>', '</dd>'],
           }
inlineTagsForrest = {'em' : ['<em>', '</em>'],
              'strong' : ['<strong>', '</strong>'],
              'quote' : ['&quot;', '&quot;'],
              'code' : ['<code>', '</code>'],
              'anchor' : ['<a id="', '"/>']}
dictTagsForrest = {'ulink' : '<a href="%(url)s"%(atts)s>%(linktext)s</a>',
                   'inlinemediaobject' : '<img src="%(fref)s"%(atts)s/>',
                   'mediaobject' : '<figure src="%(fref)s"%(atts)s/>',
                   'figure' : '<figure src="%(fref)s"%(atts)s/><p><strong>Figure</strong>: %(title)s</p>'
                  }

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
           'Section' : ['<section id="%(id)s"><title>%(title)s</title>', '</section>', True],
           'Para' : ['<para>', '</para>', False],
           'Code' : ['<screen xml:space="preserve">', '</screen>', False],
           'Figure' : ['', '', False],
           'Abstract' : ['<abstract>', '</abstract>', True],
           'Remark'  : ['<remark>', '</remark>', True],
           'Note'  : ['<note>', '</note>', True],
           'Important'  : ['<important>', '</important>', True],
           'Warning'  : ['<warning>', '</warning>', True],
           'Caution'  : ['<caution>', '</caution>', True],
           'Keywords': ['<remark><para>Keywords:</para>', '</remark>', True],
           'TODO': ['<remark><para>TODO:</para>', '</remark>', True],
           'Definition': ['<remark><para>Definition:</para>', '</remark>', True],
           'Lemma': ['<remark><para>Lemma:</para>', '</remark>', True],
           'Proof': ['<remark><para>Proof:</para>', '</remark>', True],
           'Theorem': ['<remark><para>Theorem:</para>', '</remark>', True],
           'Corollary': ['<remark><para>Corollary:</para>', '</remark>', True]
}
listTagsDocbook = {'#' : ['<orderedlist>', '</orderedlist>'],
            '*' : ['<itemizedlist>', '</itemizedlist>'],
            '~' : ['<variablelist>', '</variablelist>'],
            'olItem' : ['<listitem>', '</listitem>'],
            'ulItem' : ['<listitem>', '</listitem>'],
            'dtItem' : ['<varlistentry><term>', '</term>'],
            'ddItem' : ['<listitem>', '</listitem></varlistentry>'],
           }
inlineTagsDocbook = {'em' : ['<emphasis>', '</emphasis>'],
              'strong' : ['<emphasis role="bold">', '</emphasis>'],
              'quote' : ['<quote>', '</quote>'],
              'code' : ['<code>', '</code>'],
              'anchor' : ['<a id="', '"/>']}
dictTagsDocbook = {'ulink' : '<ulink url="%(url)s">%(linktext)s</ulink>',
                   'inlinemediaobject' : '<inlinemediaobject><imageobject><imagedata fileref="%(fref)s"%(atts)s/></imageobject></inlinemediaobject>',
                   'mediaobject' : '<mediaobject><imageobject><imagedata fileref="%(fileref)s"%(atts)s/></imageobject></mediaobject>',
                   'figure' : '<figure><title>%(title)s</title><mediaobject><imageobject><imagedata fileref="%(fref)s"%(atts)s/></imageobject></mediaobject></figure>'
                  }

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


def stripUtfMarker(content) :
    import codecs
    return content.replace( unicode(codecs.BOM_UTF8,"utf8"), "")

def readUtf8(filename) :
    print "Reading",filename
    return stripUtfMarker(codecs.open(filename,'r','utf8').read())

def loadOrDefault(filename, defaultContent) :
    try: return readUtf8(filename)
    except: return defaultContent

def writeUtf8(filename, content) :
    import codecs, os
    path = filename.split("/")[:-1]
    for i in range(len(path)) :
        try : os.mkdir("/".join(path[:i+1]))
        except: pass
    codecs.open(filename, "w",'utf8').write(content)

def tos(seq):
    if len(seq) > 0:
        return seq[-1]
    else:
        return ""

class WikiCompiler :

    def closeAllOpenedBlocks(self):
        while len(self.openBlocks):
            tos = self.openBlocks.pop()
            self.result += "%s\n" % self.envTags[tos][1]
            
    def closeOpenedBlocks(self, tag, num=1):
        cnt = 0
        while len(self.openBlocks):
            tos = self.openBlocks.pop()
            self.result += "%s\n" % self.envTags[tos][1]
            if tos == tag:
                cnt += 1
            if cnt == num:
                break
            
    def process(self, content) :
        self.itemLevel = ""
        self.closing=""
        self.result=""
        
        self.vars = {
            'title': '',
            'author': ''
        }
        # Collect simple blocks
        self.openBlocks = []
        currentBlock = []
        self.currentEnvironment = ""
        self.currentText = ""
        self.codeType = ""
        self.lastBlock = None
        self.sectionIndent = 0
        self.paraIndent = 0
        for line in content.splitlines():
            if line.strip() == "":
                # Line is empty
                if len(currentBlock):
                    # Current block was closed...so process it
                    self.processBlock(currentBlock)
                    currentBlock = []
            else:
                varMatch = var.match(line)
                if varMatch:
                    # Catch vars
                    key = varMatch.group(1)
                    if key in self.vars:
                        self.vars[key] = varMatch.group(2)
                else:
                    # Continue to collect lines
                    currentBlock.append(line)
                
        # Process the final block
        if len(currentBlock):
            self.processBlock(currentBlock)

        # Close all blocks that are still opened
        self.closeAllOpenedBlocks()

        self.vars["content"] = self.result
        
        return self.vars

    def processBlock(self, block):
        # Step 1: Identify block
        blockType = "None"
        addIndent = ""
        blockSpec = ""
        sectionTitle = ""
        sectionId = ""
        envMatch = env.match(block[0])
        envStarted = False
        envStopped = False
        if envMatch and envMatch.start() == 0:
            blockStart = envMatch.group(1)
            blockType = envMatch.group(2)
            addIndent = envMatch.group(3)
            blockSpec = envMatch.group(4)
            self.currentEnvironment = blockType
            if blockStart == "{{":
                envStarted = True
                # Does the env also end in this block?
                endMatch = closeenv.match(block[-1])
                if endMatch and endMatch.start() == 0:
                    # Yes
                    text = "\n".join(block[1:-1])
                    envStopped = True
                else:
                    text = "\n".join(block[1:])
            else:
                # Single block env
                envStarted = True
                envStopped = True
                text = "\n".join(block[1:])
        else:
            if len(self.currentEnvironment):
                # Does the env end in this block?
                endMatch = closeenv.match(block[-1])
                if endMatch and endMatch.start() == 0:
                    # Yes
                    text = "\n".join(block[1:-1])
                    envStopped = True
                else:
                    text = "\n".join(block)
            else:
                text = "\n".join(block)
        
        if blockType == "None":
            # Is it a list block?
            listMatch = li.match(text)
            if listMatch and listMatch.start() == 0:
                blockType = "List"
            else:
                varMatch = var.match(text)
                if varMatch and varMatch.start() == 0:
                    blockType = "Var"
                    for l in block:
                        varMatch = var.match(l)
                        if varMatch:
                            self.vars[varMatch.group(1)] = varMatch.group(2)
                    return
                else:
                    # Is it a section header?
                    headerMatch = header.match(block[0])
                    if headerMatch and headerMatch.start() == 0:
                        blockType = "Section"
                        addIndent = headerMatch.group(1)
                        sectionTitle = headerMatch.group(2).rstrip()
                        sectionId = headerMatch.group(3)
                        if sectionId.strip() == "":
                            sectionId = '_'.join([f.lower() for f in sectionTitle.split()])
        
        # Step 2: Close old envs, based on block type and current indents
        if blockType == "Section":
            # Normal indentation?
            if addIndent == "":
                # Yes
                self.closeOpenedBlocks(blockType)
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
                    self.closeOpenedBlocks(blockType, mcnt+1)
                    self.sectionIndent -= mcnt+1
                elif addIndent[0] != "+":
                    # Jump to given section depth
                    mcnt = self.sectionIndent - int(addIndent)
                    self.closeOpenedBlocks(blockType, mcnt)
                    self.sectionIndent -= mcnt
                                        
        # Step 3: Open new section
        if blockType == "Section":
            self.openBlocks.append('Section')
            self.sectionIndent += 1
            self.result += "%s\n" % (self.envTags['Section'][0] % {'title':sectionTitle, 'id':sectionId})
            return
        
        # Step 4: Process block=
        # Step 4a: Convert list items, if required
        if blockType == "List":
            text = self.processList(text)
        elif blockType == "Figure":
            fighref = blockSpec
            seppos = fighref.find("||")
            if seppos > 0:
                figatts = ' '+fighref[seppos+2:]
                fighref = fighref[:seppos]
            else:
                figatts = ' alt="'+fighref+'"'
             
            if text.strip() != "":
                # Figure with title
                text = self.dictTags['figure'] % {'fref' : fighref,
                                                  'atts' : figatts,
                                                  'title' : text}
            else:
                # No title
                text = self.dictTags['mediaobject'] % {'fref' : fighref,
                                                       'atts' : figatts}
        elif blockType != "Code":
            if blockType != "None":
                if self.envTags[blockType][2]:
                    # Wrap text in para
                    text = "%s%s%s\n" % (self.envTags['Para'][0], text, self.envTags['Para'][1])
            else:
                # Wrap text in para
                text = "%s%s%s\n" % (self.envTags['Para'][0], text, self.envTags['Para'][1])                
        else:
            text = processVerbatim(text, blockSpec)        
            
        # Step 4b: Replace inline expressions
        if blockType != "Code":
            text = self.inlineReplace(text)

        # Step 5: Wrap block in environment tags
        if envStarted:
            text = "%s\n%s" % (self.envTags[self.currentEnvironment][0],text)
            self.openBlocks.append(blockType)
        if envStopped:
            text = "%s\n%s\n" % (text, self.envTags[self.currentEnvironment][1])
            self.currentEnvironment = ""
            self.openBlocks.pop()
            
        # Step 6: Add text to result
        self.result += text

    def replaceAll(self, text, regex, starttag, endtag):
        match = regex.search(text)
        while match:
            text = text[:match.start()]+starttag+match.group(1)+endtag+text[match.end():]
            match = regex.search(text)
            
        return text
        
    def inlineReplace(self, text):
        # Find and replace URLs
        uMatch = url.search(text)
        while uMatch:
            href = uMatch.group(1)
            atxt = uMatch.group(2)
            urlatts = ""
            seppos = atxt.find("||")
            if seppos > 0:
                urlatts = ' '+atxt[:seppos]
                atxt = atxt[seppos+2:]
            text = (text[:uMatch.start()] + 
                    self.dictTags['ulink'] % {'url' : href,
                                              'atts' : urlatts,
                                              'linktext' : atxt} + 
                    text[uMatch.end():])
            uMatch = url.search(text)
            
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
        
        # Apply non-greedy inline substitutions to the joined block
        text = self.replaceAll(text, em, self.inlineTags["em"][0], self.inlineTags["em"][1])
        text = self.replaceAll(text, strong, self.inlineTags["strong"][0], self.inlineTags["strong"][1])
        text = self.replaceAll(text, quote, self.inlineTags["quote"][0], self.inlineTags["quote"][1])
        text = self.replaceAll(text, code, self.inlineTags["code"][0], self.inlineTags["code"][1])
        text = self.replaceAll(text, anchor, self.inlineTags["anchor"][0], self.inlineTags["anchor"][1])
        # Replace \blank escape sequences
        text = text.replace("\blank","")
        return text

    def getListItemText(self, lastItem, lastText):
        if lastItem == "":
            return lastItem
        
        if lastItem[-1] != '~':
            if lastItem[-1] == '#':
                return "%s%s%s\n" % (self.listTags['olItem'][0],
                                     lastText,
                                     self.listTags['olItem'][1])
            else:
                return "%s%s%s\n" % (self.listTags['ulItem'][0],
                                     lastText,
                                     self.listTags['ulItem'][1])                
        else:
            fpos = lastText.find('||')
            if fpos > 0:
                return "%s%s%s%s%s%s%s%s\n" % (self.listTags['dtItem'][0],
                                               lastText[:fpos],
                                               self.listTags['dtItem'][1],
                                               self.listTags['ddItem'][0],
                                               self.envTags['Para'][0],
                                               lastText[fpos+2:],
                                               self.envTags['Para'][1],
                                               self.listTags['ddItem'][1])
            else:
                return "%s%s%s%s%s\n" % (self.listTags['dtItem'][0],
                                         lastText,
                                         self.listTags['dtItem'][1],
                                         self.listTags['ddItem'][0],
                                         self.listTags['ddItem'][1])
        return ""
        
    def processList(self, txt):
        lines = txt.split('\n')
        listStack = []
        listIndent = 0
        ltxt = ""
        lastItem = ""
        lastText = ""
        curItem = ""
        curText = ""
        for l in lines:
            lMatch = li.match(l)
            if lMatch:
                curItem = lMatch.group(1)
                curText = lMatch.group(2)
                
                if lastText != "":
                    # Emit last item
                    ltxt += self.getListItemText(lastItem, lastText)
                # Close old list envs
                toclose = len(lastItem)-len(curItem)
                if toclose >= 0:
                    if lastItem.find(curItem) != 0:
                        toclose += 1 # Changed env
                while len(listStack) and toclose > 0:
                    ltxt += "%s\n" % self.listTags[listStack.pop()][1]
                    if len(listStack):
                        # Pop enclosing <li> item
                        ltxt += "%s\n" % self.listTags[listStack.pop()][1]                        
                    toclose -= 1
                    listIndent -= 1
                    
                # Open new list envs
                toopen = len(curItem)-listIndent
                print curItem, lastItem, listIndent
                if toopen > 0 and curItem != lastItem:
                    opencnt = listIndent
                    if len(curItem) > 1:
                        toopen += 1 # ugly hack
                    print "opencnt", opencnt, toopen
                    
                    while opencnt < toopen:
                        if opencnt > 0:
                            # Prepend <li> for list item
                            otag = 'olItem'
                            print "prepending"
                            if curItem[opencnt-1] == '*':
                                otag = 'ulItem'
                            ltxt += "%s" % self.listTags[otag][0]
                            listStack.append(otag)
                        ltxt += "%s\n" % self.listTags[curItem[opencnt]][0]
                        listStack.append(curItem[opencnt])
                        opencnt += 1
                        listIndent += 1
                    
                lastItem = curItem
                lastText = curText
            else:
                lastText += "\n%s" % l
        # Emit last
        if lastText != "":
            ltxt += self.getListItemText(lastItem, lastText)
                                                        
        # Close remaining envs
        while len(listStack):
            ltxt += "%s\n" % self.listTags[listStack.pop()][1]
        
        return ltxt

class ForrestCompiler(WikiCompiler):
    def __init__(self):
        self.envTags = envTagsForrest
        self.listTags = listTagsForrest
        self.inlineTags = inlineTagsForrest
        self.dictTags = dictTagsForrest

class DocbookCompiler(WikiCompiler):
    def __init__(self):
        self.envTags = envTagsDocbook
        self.listTags = listTagsDocbook
        self.inlineTags = inlineTagsDocbook
        self.dictTags = dictTagsDocbook

skeletonFileName = "skeleton.xml"
if len(sys.argv) > 1:
    skeleton = loadOrDefault(skeletonFileName, defaultSkeletonDocbook)
    hComp = DocbookCompiler()
else:
    skeleton = loadOrDefault(skeletonFileName, defaultSkeletonForrest)
    hComp = ForrestCompiler()

# Generate XML files from content files + skeleton
for path,dirs,files in os.walk('.'):
    for f in files:
        if f.endswith(".wiki"):
            contentFile = os.path.join(path, f)
            target = "".join(os.path.splitext(f)[0:-1])+".xml"
            target = os.path.join(path, target)
            content = readUtf8(contentFile)
            htmlResult = hComp.process(content)
            writeUtf8(target, skeleton%htmlResult)
