#!/usr/bin/python

"""
WiKo: this script generates a web pages, PDF article or blog
considering the files found in the local directory.
See http://www.iua.upf.edu/~dgarcia/wiko/usage.html
"""

# Bugs: 
# * @cite:some at end of line, or @cite:some, something.
# * don't work with iso encoding only utf8
 
# TODOs:
# * refactor most behaviour to a base class (done in-flight and lost)
# * use @toc in the .wiki file
# * deactivate implicit <pre> mode when in explicit "{{{ }}}" <pre> mode
# * bullets should allow breaking line into a new line with spaces.

import glob
import os.path
import re
import sys
import subprocess
import urllib
import codecs

def formulaIdGen(): a=0; yield a; a+=1
def equationIdGen(): a=0; yield a; a+=1

class HtmlVerbatimProcessor :
	def __init__(self) :
		self.content=[]
	def __call__(self, line) :
		if line is None:
			return "\n".join(self.content).replace("%","%%")
		self.content.append(line)
		return ""

def formulaUri(latexContent) :
	if useRemoteFormulas :
		return "http://www.forkosh.dreamhost.com/mimetex.cgi?"+latexContent
	mimetex = subprocess.Popen(["mimetex","-d",latexContent], stdout=subprocess.PIPE)
	imageContent=mimetex.stdout.read()
	if embeddedFormulas :
		import base64
		url = "data:image/png;base64,"+ base64.b64encode(imageContent)
		return url
	if not os.access("formulas",os.F_OK) :
		os.mkdir("formulas")
	id = formulaIdGen().next()
	gifname = "formulas/eq%06i.gif"%id
	print "generating",gifname
	gif = open(gifname,'wb')
	gif.write(imageContent)
	gif.close()
	return gifname

class HtmlFormulaProcessor :
	def __init__(self, match) :
		self.content=[]
	def __call__(self, line) :
		if line is None:
			return '"'+formulaUri("\Large{"+"".join(self.content)+"}")+'"'
		self.content.append(line.strip())
		return ""

class HtmlCodeProcessor :
	def __init__(self, match) :
		self.content=[]
		self.language=match.group(1) or "javascript"
	def __call__(self, line) :
		if line is not None:
			self.content.append(line)
			return ""
		try :
			from pygments import highlight
			from pygments.lexers import get_lexer_by_name
			from pygments.formatters import HtmlFormatter
		except:
			print >> sys.stderr, "Warning: Pygments package not available. Generating code without syntax highlighting."
			return "\n".join(self.content)
		file("style_code.css",'w').write(HtmlFormatter().get_style_defs('.code'))

		lexer = get_lexer_by_name(self.language, stripall=True)
		formatter = HtmlFormatter(linenos=False, cssclass="code")
		return highlight("\n".join(self.content), lexer, formatter)

def htmlInlineFormula(match) :
	formula = match.group(1)
	return '<img class="inlineFormula" src="%s" alt="%s" />'%(formulaUri(formula), formula)

inlineHtmlSubstitutions = [  # the order is important
	(r"%%", r"%"),
	(r"%([^(])", r"%%\1"),
	(r"'''(([^']|'[^']|''[^'])*)'''", r"<b>\1</b>"),
	(r"''(([^']|'[^'])*)''", r"<em>\1</em>"),
	(r"\[\[(\S+)\s([^\]]+)\]\]", r"<a href='\1'>\2</a>"),
	(r"\[\[(\S+)\]\]", r"<a href='\1'>\1</a>"),
	(r"\[(http://\S+)\s([^\]]+)\]", r"<a href='\1'>\2</a>"),
	(r"\[(http://\S+)\]", r"<a href='\1'>\1</a>"),
	(r"\\ref{([-+_a-zA-Z0-9:]+)}", r"<a href='#\1'>\1</a>"), # TODO: numbered figures?
	(r"`([^`]+)`", htmlInlineFormula),
#	(r"{{{", r"<pre>"),
#	(r"}}}", r"</pre>"),
	(r"^@toc\s*$", r"%(toc)s"),
	(r"^BeginProof\n*$", r"<div class='proof'><b>Proof:</b>"),
	(r"^EndProof\n*$", r"</div>"),
	(r"^BeginDefinition\n*$", r"<div class='definition'><b>Definition:</b>"),
	(r"^EndDefinition\n*$", r"</div>"),
	(r"^BeginTheorem\n*$", r"<div class='theorem'><b>Theorem:</b>"),
	(r"^EndTheorem\n*$", r"</div>"),
]

header = re.compile(r"^(=+)([*]?)\s*([^=]+?)\s*\1\s*$")
headersHtml = [
	r"<section id='toc_%(n)s'><title>%(title)s</title>",
	r"<section id='toc_%(n)s'><title>%(title)s</title>",
	r"<section id='toc_%(n)s'><title>%(title)s</title>",
	r"<section id='toc_%(n)s'><title>%(title)s</title>",
	r"<section id='toc_%(n)s'><title>%(title)s</title>",
]

li  = re.compile(r"^([*#]+)(.*)")
quote = re.compile(r"^[ \t](.*)")
var = re.compile(r"^@([^:]*): (.*)")
fig = re.compile(r"^Figure:[\s]*([^\s]+)[\s]*([^\s]+)(.*)");
figs = re.compile(r"^Figures:[\s]*([^\s]+)[\s]*(.*)");
todo = re.compile(r"^TODO:[\s]*(.+)");
anno = re.compile(r"^:([^\s]+):[\s]*(.*)");
code = re.compile(r"^Code:[\s]*([^\s]+)?");
label = re.compile(r"^Label:[\s]*([^\s]+)");
div = re.compile(r"^([a-zA-Z0-9]+):$")
pre = re.compile(r"^{{{[\s]*([^\s])*")
close = re.compile(r"^---[\s]*([^\s]+)?");
dtdd = re.compile(r"^{{([^(\|])*\|\|[\s]}}")

divMarkersLatex = {
	'Abstract' : ('\\begin{abstract}', '\\end{abstract}'),
	'Keywords' : ('\\begin{keywords}', '\\end{keywords}'),
	'Equation' : ('\\begin{equation}', '\\end{equation}'),
#	'Math' : ('\\[', '\\]'),
	'Theorem': ('\\begin{thma}', '\\end{thma}'),
	'Lemma': ('\\begin{lem}', '\\end{lem}'),
	'Corollary': ('\\begin{cor}', '\\end{cor}'),
	'Proof': ('\\begin{pro}', '\\end{pro}'),
	'Definition': ('\\begin{defin}', '\\end{defin}'),
	#TODO: add new keys added in html
}

divMarkersHtml = {
	'Abstract' : ('<div class="abstract"><b>Abstract:</b>', '</div>'),
	'Keywords' : ('<div class="keywords"><b>Keywords:</b>', '</div>'),
	'Equation' : ("<div class='equation'><img src=", " /><!--<span class='eqnumber'>(123)</span>--></div>", HtmlFormulaProcessor),
	'Math'     : ("<div class='equation'><img src=", " /></div>", HtmlFormulaProcessor),
	'TODO'     : ('<div class="todo"><b>TODO:</b>', '</div>'),
	'Comment'  : ('<div class="comment"><b>Comment:</b>', '</div>'),
	'Definition'  : ('<div class="definition"><b>Definition:</b>', '</div>'),
	'Lemma'    : ('<div class="lemma"><b>Lemma:</b>', '</div>'),
	'Proof'    : ('<div class="proof"><b>Proof:</b>', '</div>'),
	'Theorem'  : ('<div class="theorem"><b>Theorem:</b>', '</div>'),
	'Corollary': ('<div class="corollary"><b>Corollary:</b>', '</div>'),
}

defaultForrestSkeleton = u"""<?xml version="1.0" encoding="utf-8"?>
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
	print "Generating",filename
	path = filename.split("/")[:-1]
	for i in range(len(path)) :
		try : os.mkdir("/".join(path[:i+1]))
		except: pass
	basepath='../'*len(path)
	content=content.replace('<!--base-->','<base href="%s" />'%basepath)
	codecs.open(filename, "w",'utf8').write(content)

class WikiCompiler :

	def compileInlines(self, inlines) :
		self.inlines = [ (re.compile(wikipattern), substitution) 
			for wikipattern, substitution in inlines  ]
	def substituteInlines(self, line) :
		for compiledPattern, substitution in self.inlines :
			line = compiledPattern.sub(substitution, line)
		return line

	def openDiv(self, markers, divMatch):
		divType = divMatch.group(1)
		try : divDef = list(markers[divType])
		except : return False
		if len(divDef) == 3 :
			divDef[2] = divDef[2](divMatch)
		self.openBlock(*divDef)
		return True
	def openBlock(self,opening,closing, processor=None):
		self.closeAnyOpen()
		self.result.append(opening)
		self.closing=closing	
		if processor :
			self.processor=processor
	def closeAnyOpen(self) :
		if self.closing == "" : return
		if self.processor : self.result.append(self.processor(None))
		self.processor=None
		self.result.append(self.closing)
		self.closing=""

	def addToc(self, level, title) :
		self.toc.append( (level, title) )
		return len(self.toc)
	def buildToc(self) :
		"""Default, empty toc"""
		return ""

	def process(self, content) :
		self.itemLevel = ""
		self.closing=""
		self.result=[]
		self.spanStack = []
		self.toc = []
		self.vars = {
			'title': '',
			'author': '',
		}
		for line in content.splitlines() :
			self.processLine(line)
		self.processLine("")

		self.vars["content"] = ("\n".join(self.result)) % {
			'toc': self.buildToc(),
		}
		return self.vars

class HtmlCompiler(WikiCompiler) :
	def __init__(self) :
		self.compileInlines(inlineHtmlSubstitutions)
		self.headerPatterns = headersHtml
		self.processor = None
	def buildToc(self) :
		result = []
		lastLevel = 0
		i=1
		result+=["<h2>Index</h2>"]
		result+=["<div class='toc'>"]
		for (level, item) in self.toc :
			while lastLevel < level :
				result += ["<ul>"]
				lastLevel+=1
			while lastLevel > level :
				result += ["</ul>"]
				lastLevel-=1
			result+=["<li><a href='#toc_%i'>%s</a></li>"%(i,item)]
			i+=1
		while lastLevel > 0 :
			result += ["</ul>"]
			lastLevel-=1
		result += ["</div>"]
		return "\n".join(result)

	def processLine(self, line) :
		newItemLevel = ""
		liMatch = li.match(line)
		quoteMatch = quote.match(line)
		headerMatch = header.match(line)
		varMatch = var.match(line)
		figMatch = fig.match(line)
		figsMatch = figs.match(line)
		todoMatch = todo.match(line)
		annoMatch = anno.match(line)
		labelMatch = label.match(line)
		codeMatch = code.match(line)
		divMatch = div.match(line)
		preMatch = pre.match(line)
		closeMatch = close.match(line)
		if self.closing == "</pre>" and line == "}}}" :
			self.closeAnyOpen()
			return
		elif line=="" :
			self.closeAnyOpen()
			return
		elif self.processor : 
			self.processor(line)
			return
		elif varMatch :
			self.vars[varMatch.group(1)] = varMatch.group(2)
			print "Var '%s': %s"%(varMatch.group(1),varMatch.group(2))
			return
		if liMatch :
			self.closeAnyOpen()
			newItemLevel = liMatch.group(1)
			line = "%s<li>%s</li>" %("\t"*len(newItemLevel), liMatch.group(2) )
		while len(newItemLevel) < len(self.itemLevel) or  \
				self.itemLevel != newItemLevel[0:len(self.itemLevel)]:
#			print "pop '"+self.itemLevel+"','"+newItemLevel+"' "+self.itemLevel[-1]
			if self.itemLevel[-1] == "*":
                            tag = "ul"
			else:
                            tag = "ol"
			self.result.append("%s</%s>"%("\t"*(len(self.itemLevel)-1),tag))
			self.itemLevel=self.itemLevel[0:-1]
		if quoteMatch:
			if self.closing != "</blockquote>" :
				self.openBlock("<blockquote>","</blockquote>")
			line=line[1:] # remove the quoting indicator space
		elif figMatch :
			self.closeAnyOpen()
			self.openBlock(
				"<div class='figure' id='%(id)s'><img src='%(img)s' alt='%(id)s'/><br />\n"%{
					'id':figMatch.group(1),
					'img': figMatch.group(2),
					},
				"</div>\n")
			return
		elif figsMatch :
			self.closeAnyOpen()
			self.openBlock(
				("<div class='figure' id='%(id)s'>\n"
				+"".join(["<img src='%s' alt='%%(id)s'/><br />\n"%image for image in figsMatch.group(2).split()]))
				%{
					'id':figsMatch.group(1),
					},
				"</div>\n")
			return
		elif codeMatch :
			self.closeAnyOpen()
			self.openBlock(
				"<code>",
				"</code>",
				HtmlCodeProcessor(codeMatch))
			return
		elif preMatch :
			self.closeAnyOpen()
			self.openBlock(
				"<pre>",
				"</pre>",
				HtmlVerbatimProcessor())
			return
		elif todoMatch :
			line=" <span class='todo'>TODO: %s</span> "%todoMatch.group(1)
		elif annoMatch :
			annotator = annoMatch.group(1)
			text = annoMatch.group(2)
			line=(" <a class='anno'><img alt='[Ann:%s]' src='stock_notes.png' />"+ 
				"<span class='tooltip'><b>%s:</b> %s</span></a> ")%(annotator,annotator,text)
		elif labelMatch :
			line=" <a name='#%s'></a>"%labelMatch.group(1)
		elif headerMatch :
			self.closeAnyOpen()
			title = headerMatch.group(3)
			level = len(headerMatch.group(1))
			n=self.addToc(level,title)
			line = self.headerPatterns[level-1]%{
				"title": title,
				"n": n,
				"level": level,
			}
		elif closeMatch :
			line="</%s>"%closeMatch.group(1)
		elif not liMatch : 
			if divMatch :
				if self.openDiv(divMarkersHtml, divMatch) :
					return
				print "Not supported block class '%s'" % divMatch.group(1)
			elif self.closing == "" :
				self.openBlock("<p>","</p>")
		# Equilibrate the item level
		while len(self.itemLevel) != len(newItemLevel) :
			self.closeAnyOpen()
#			print "push '"+self.itemLevel+"','"+newItemLevel+"'"
			levelToAdd = newItemLevel[len(self.itemLevel)]
			if levelToAdd == u"*":
                            tag = "ul"
                        else:
                            tag = "ol"
			self.result.append("%s<%s>"%("\t"*len(self.itemLevel),tag))
			self.itemLevel += levelToAdd
		if self.processor :
			self.processor(line)
		else :
			line = self.substituteInlines(line)	
			self.result.append(line)

skeletonFileName = "skeleton.xml"
skeleton = loadOrDefault(skeletonFileName, defaultForrestSkeleton)

# Generate XML files from content files + skeleton
for path,dirs,files in os.walk('.'):
    for f in files:
        if f.endswith(".wiki"):
	    contentFile = os.path.join(path, f)
	    target = "".join(os.path.splitext(f)[0:-1])+".xml"
            target = os.path.join(path, target)
	    content = readUtf8(contentFile)
            print "Generating", target, "from", contentFile, "..."
            htmlResult = HtmlCompiler().process(content)
            htmlResult['wikiSource']=contentFile;
            writeUtf8(target, skeleton%htmlResult)


