#rgr.py

a graph database for Python, built on Redis

###Goal:

- Pythonic, simple, flexible, unassuming graph database. I think it's getting there.


###Prerequisites:

- Redis server
- redis.py

###Usage: 

```python
from rgr import Graph 

g = Graph()

jack = g.add_node(name='jack')
jill = g.add_node(name='jill', gender='female') #multiple properties

g.add_node(name='fred') #it's there even if you didn't keep the Node object

g.add_edge(jack, jill, rel='knows')
g.add_edge(jill, jack, rel='hates', weight=100) #set however many properties you want

fred = g.get_nodes(name='fred') #get nodes

haters = g.get_edges(rel='hates') #get edges
for h in haters:
  print h.in_node().prop.name #incoming node - 'name' property

jnodes = g.find_nodes(name="^[Jj]") #regex queries

jack.prop.on = 'the hill' #set and access properties by 'prop' object that manages properties
jill.prop.has = 'a pail'  #is this 'prop' Properties object a bad idea?
                          #maybe it should just act like a dict? idk

for node in jack.children():
    print node.properties() 

```
###Todo:

- make operations atomic - right now this library is NOT thread safe
- make code more idiomatic
- 

#####Misc:
- test, debug, standardize/cleanup

I'm open to suggestions, enjoy.
