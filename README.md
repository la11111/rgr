#rgr.py

a graph database for Python, built on Redis

###Rationale:
- redis is cool and I wanted to learn it.
- I needed a graph database; neo4j is too heavy, where redis_wrap/redis_graph are a bit too light. I'm hoping that rgr will be just right :)
- I needed to start a project and actually finish it.

one, two, three, done :)

###Goal:

- Pythonic, simple, flexible, unassuming graph database. I think it's getting there.

This is the first project I've published on GitHub - It's still ugly, as I uploaded it as soon as it was bugfree*; If you find it useful and have suggestions, feel free to send them, post a patch, or whatever you do in git (I'm a git n00b as well ;P - I'll figure it out)

###Special thanks:

http://github.com/peta/redis-natives-py - this project would have been impossible to complete so rapidly without it. A nice implementation. :)

###Prerequisites:

- Redis server
- redis.py
- redis_natives

###The basics:

I borrowed some ideas from Bulbflow, which I think is pretty slick.

- all nodes, edges, indices, and properties are bound directly to Redis – when you add/change/remove a property/node/etc, it’s immediately reflected in the database.
- all properties are lists, but you can interact with them as if they are scalars if you like.
- as of the initial release, all properties and their values are fully indexed. I will probably change this in the future to allow for non-indexed properties.
- as in bulbs, Node/Edge properties are accessed by dot notation.
- node/edge data can be accessed as a property or as a callable, returning ID's only or objects, respectively.

###Usage: 
(subject to additions - full/current docs in the code / plain README:)

```python
from rgr import *

g = Graph()

jack = g.addn(name='jack')
jill = g.addn(name='jill')

g.addn(name='fred')

g.adde(jack, jill, rel='knows')
g.adde(jill, jack, rel='hates')

fred = g.getn(name='fred') #get nodes

haters = g.gete(rel='hates') #get edges
for h in haters:
  print h._in().name #incoming node - 'name' property

jack.on = 'the hill' #why node data names have underscores
jill.has = 'a pail'

jack._cn # set of jack's child node ID's
for node in jack._cn(): # properties are callable
  print node._properties # all node props stored here

```
###Todo:

#####Graph():
- query() related methods; get nodes by relationship, regexp, etc. 

#####Node/Edge(): 
- addn()
- adde()

#####Misc:
- test, debug, standardize/cleanup


I'm open to suggestions, enjoy.